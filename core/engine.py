"""
Ядро маршрутизации команд (Intent Router) и механизм плагинов.
Содержит декоратор @skill, автозагрузчик скиллов и диспетчер обработки текста.
"""

import importlib
import re
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional

# Глобальный реестр зарегистрированных скиллов
SKILLS_REGISTRY: List[Dict[str, Any]] = []

def skill(name: str, triggers: List[str], description: str = ""):
    """
    Декоратор для регистрации функций в качестве навыков ассистента.
    
    Пример:
    @skill(name="audio_mute", triggers=["выключи звук", "без звука"])
    def mute_sound(text: str, context: dict) -> str:
        ...
        return "Звук отключен"
    """
    def decorator(func: Callable):
        SKILLS_REGISTRY.append({
            "name": name,
            "triggers": [t.strip().lower() for t in triggers if t.strip()],
            "description": description,
            "handler": func
        })
        return func
    return decorator


def load_all_skills(skills_dir: Path, display=None):
    """
    Автоматически сканирует каталог skills/ и импортирует все модули .py.
    При импорте срабатывают декораторы @skill и регистрируют навыки.
    """
    if not skills_dir.exists():
        return

    loaded_count = 0
    for file_path in sorted(skills_dir.glob("*.py")):
        if file_path.name.startswith("__"):
            continue

        module_name = f"skills.{file_path.stem}"
        try:
            # Если модуль уже был импортирован, перезагружаем его
            if module_name in importlib.sys.modules:
                importlib.reload(importlib.sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            loaded_count += 1
        except Exception as e:
            if display:
                display.log(f"Ошибка загрузки скилла из {file_path.name}: {e}", tag="ERROR")

    if display:
        display.log(f"Загружено файлов скиллов: {loaded_count}, всего действий: {len(SKILLS_REGISTRY)}", tag="SUCCESS")


class IntentEngine:
    def __init__(self, config: dict, persona, display, speaker):
        self.config = config
        self.persona = persona
        self.display = display
        self.speaker = speaker
        
        system_cfg = config.get("system", {})
        self.name = system_cfg.get("name", "Моника").lower()
        self.wake_word = system_cfg.get("wake_word", "моника").lower()

    def clean_text(self, text: str) -> str:
        """Очищает входной текст от знаков препинания и убирает имя ассистента из начала фразы."""
        text = text.lower().strip()

        # Если пользователь случайно скопировал флаг --exec в интерактивный ввод
        if text.startswith("--exec") or text.startswith("-e"):
            text = re.sub(r"^--?exec\s*[\"']?", "", text)
            text = re.sub(r"[\"']+$", "", text).strip()

        # Убираем знаки препинания и кавычки по краям
        text = re.sub(r"^[,\.!?\"'\-\s]+|[,\.!?\"'\-\s]+$", "", text)
        
        # Убираем вводные приветствия и обращение к имени (например: "эй моника", "слушай, моника", "моника")
        text = re.sub(r"^(?:эй|слушай|привет|пожалуйста)?[\s,.-]*(?:моник[а-я]*|маник[а-я]*)[\s,.-]*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^[,\.!?\"'\-\s]+|[,\.!?\"'\-\s]+$", "", text)

        # Резервная проверка по self.wake_word и self.name
        for trigger in [self.wake_word, self.name]:
            if text.startswith(trigger):
                text = text[len(trigger):].strip()
                text = re.sub(r"^[,\.!?\"'\-\s]+", "", text)
                break
        return text.strip()

    def execute(self, raw_text: str) -> Optional[str]:
        """
        Главный метод обработки команды:
        1. Очистка текста
        2. Поиск подходящего скилла
        3. Выполнение обработчика
        4. Озвучка и уведомление
        """
        if not raw_text or not raw_text.strip():
            return None

        clean_cmd = self.clean_text(raw_text)
        self.display.log(f"Команда к исполнению: '{clean_cmd}' (исходный: '{raw_text}')", tag="INFO")

        if not clean_cmd:
            # Пользователь просто назвал имя ("Моника")
            reply = self.persona.get_phrase("on_wake", fallback="Слушаю вас.")
            self.display.show_notification(reply, title=self.persona.name)
            self.speaker.speak(reply)
            return reply

        # Контекст, передаваемый в каждый скилл
        context = {
            "raw_text": raw_text,
            "clean_text": clean_cmd,
            "persona": self.persona,
            "display": self.display,
            "speaker": self.speaker,
            "config": self.config
        }

        # Ищем скилл с наилучшим совпадением (сначала более длинные триггеры)
        best_skill = None
        matched_trigger = None

        # Сортируем скиллы по длине совпавшего триггера, чтобы "режим работы" матчился раньше, чем просто "режим"
        candidates = []
        for item in SKILLS_REGISTRY:
            for trig in item["triggers"]:
                # Точное совпадение или подстрока
                if trig == clean_cmd or trig in clean_cmd:
                    candidates.append((len(trig), item, trig))

        if candidates:
            # Берем совпадение с максимальной длиной триггера
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_skill = candidates[0][1]
            matched_trigger = candidates[0][2]

        if best_skill:
            self.display.log(f"Сработал скилл '{best_skill['name']}' по триггеру '{matched_trigger}'", tag="SUCCESS")
            try:
                result = best_skill["handler"](clean_cmd, context)
                
                reply_text = ""
                emotion = "happy"

                if isinstance(result, str):
                    reply_text = result
                elif isinstance(result, dict):
                    reply_text = result.get("reply", "")
                    emotion = result.get("emotion", "happy")

                if reply_text:
                    self.display.trigger_waifuland_emotion(emotion)
                    self.display.show_notification(reply_text, title=self.persona.name)
                    self.speaker.speak(reply_text)
                return reply_text

            except Exception as e:
                self.display.log(f"Ошибка внутри скилла {best_skill['name']}: {e}", tag="ERROR")
                err_reply = self.persona.get_phrase("on_error", fallback="Произошла ошибка при выполнении.")
                self.display.show_notification(err_reply, title=self.persona.name, urgency="critical")
                self.speaker.speak(err_reply)
                return err_reply

        # Если ни один скилл не подошел
        unknown_reply = self.persona.get_phrase("on_unknown", fallback="Команда не распознана.")
        self.display.log(f"Не найден подходящий скилл для: '{clean_cmd}'", tag="WARN")
        self.display.trigger_waifuland_emotion("confused")
        self.display.show_notification(unknown_reply, title=self.persona.name)
        self.speaker.speak(unknown_reply)
        return unknown_reply
