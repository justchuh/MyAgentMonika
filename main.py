#!/usr/bin/env python3
"""
My Custom Agent — Локальный голосовой ассистент для Linux Hyprland.
Точка входа и управление режимами работы (включая Wake Word детектор).
"""

import argparse
import sys
from pathlib import Path
import yaml

from core.persona import PersonaManager
from core.display import DisplayManager
from core.mouth import Speaker
from core.ears import Ears
from core.wake import WakeWordDetector
from core.engine import IntentEngine, load_all_skills

ROOT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = ROOT_DIR / "config.yaml"
CHARACTER_FILE = ROOT_DIR / "character.yaml"
SKILLS_DIR = ROOT_DIR / "skills"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"[!] Конфигурационный файл {CONFIG_FILE} не найден!")
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def init_agent():
    """Инициализация всех подсистем ассистента."""
    config = load_config()
    
    display = DisplayManager(config)
    persona = PersonaManager(CHARACTER_FILE)
    speaker = Speaker(config, display=display)
    ears = Ears(config, display=display)
    wake_detector = WakeWordDetector(config, display=display)
    
    display.log(f"Инициализация ассистента '{persona.name}'...", tag="INFO")
    
    # Загружаем все скиллы из каталога skills/
    load_all_skills(SKILLS_DIR, display=display)
    
    engine = IntentEngine(config, persona=persona, display=display, speaker=speaker)
    return config, display, persona, speaker, ears, engine, wake_detector


def interactive_mode(engine, persona, display, ears=None, speaker=None, wake_detector=None, mode="oneshot"):
    """Интерактивный текстовый режим для быстрой отладки всех команд."""
    display.log("Вход в интерактивный режим. Введите команду (или 'exit' для выхода, 'микрофон' для включения прослушивания):", tag="SUCCESS")
    print("-" * 60)
    
    while True:
        try:
            cmd = input(f"\n[{persona.name}] > ").strip()
            if not cmd:
                continue
            if cmd.lower() in ["exit", "quit", "выход"]:
                display.log("Завершение работы.", tag="INFO")
                break

            # Умное переключение в режим прослушивания прямо из текстового режима
            if ears and (cmd.lower() in ["listen", "--listen", "микрофон", "слушай"] or "--listen" in cmd.lower()):
                display.log("Переключаюсь в режим прослушивания (для выхода нажмите Ctrl+C)...", tag="INFO")
                listen_mode(engine, ears, display, persona=persona, speaker=speaker, wake_detector=wake_detector, mode=mode)
                continue
            
            engine.execute(cmd)
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            break


def listen_mode(engine, ears, display, persona=None, speaker=None, wake_detector=None, mode="oneshot"):
    """
    Режимы постоянного прослушивания:
    1. 'oneshot' (По умолчанию) — Бесшовный режим на базе Silero VAD v6 + Faster-Whisper (RTX 4060):
       - Поддерживает как слитные команды («Моника, сколько времени»),
         так и естественные паузы («Моника... [думаем до 5 сек]... сколько времени»).
       - При одном лишь имени активирует окно ожидания команды на 5 секунд.
       - Любая посторонняя речь без обращения тихо игнорируется.
    2. 'dialog' — Классический двухэтапный диалог (Wake Word -> "Слушаю вас" -> запись команды).
    """
    import re
    import time

    if mode == "oneshot":
        wake_pattern = re.compile(r'\b(моник[а-я]*|маник[а-я]*)\b', re.IGNORECASE)
        active_window_sec = float(engine.config.get("vad", {}).get("active_window_sec", 5.0))
        active_until = [0.0]

        display.log("Включен бесшовный режим One-Shot (Silero VAD + Faster-Whisper).", tag="SUCCESS")
        display.log(f"Говорите слитно («Моника, сколько времени») или скажите «Моника» и думайте до {int(active_window_sec)} сек.", tag="INFO")

        def on_phrase(text: str):
            now = time.time()
            raw = text.strip()
            if not raw:
                return

            is_wake = bool(wake_pattern.search(raw))
            is_active = now < active_until[0]

            if not is_wake and not is_active:
                # Посторонняя речь без обращения — тихо игнорируем
                return

            if is_wake:
                clean_cmd = engine.clean_text(raw)
                if not clean_cmd:
                    # Пользователь назвал только имя «Моника» и замолчал -> включаем окно ожидания
                    active_until[0] = time.time() + active_window_sec
                    wake_reply = persona.get_phrase("on_wake", fallback="Слушаю вас.") if persona else "Слушаю вас."
                    display.log(f"Моника слушает... ({wake_reply})", tag="AGENT")
                    display.show_notification(wake_reply, title=persona.name if persona else "Моника")
                    if speaker:
                        speaker.speak(wake_reply, wait=True)
                    return
                else:
                    # Названы имя + команда сразу в одной фразе
                    active_until[0] = 0.0
                    display.log(f"Услышано: «{raw}»", tag="SUCCESS")
                    engine.execute(raw)
                    return

            if is_active:
                # Команда произнесена внутри активного окна без повторения имени
                active_until[0] = 0.0
                display.log(f"Команда: «{raw}»", tag="SUCCESS")
                engine.execute(raw)

        is_muted = (lambda: speaker.is_speaking) if speaker else None

        try:
            ears.listen_vad_stream(on_phrase, is_muted_func=is_muted)
        except KeyboardInterrupt:
            display.log("Прослушивание остановлено пользователем.", tag="INFO")
        return

    # Режим dialog (двухэтапный)
    if wake_detector and wake_detector.enabled and wake_detector.ready:
        display.log("Ассистент находится в режиме двухэтапного ожидания. Скажите 'Моника' для активации (Ctrl+C для выхода)...", tag="SUCCESS")
        while True:
            try:
                # 1. Ждем пробуждения по ключевому слову через Vosk/Sherpa
                woken = wake_detector.wait_for_wake_word()
                if woken:
                    # 2. Озвучиваем отклик на имя
                    reply = persona.get_phrase("on_wake", fallback="Слушаю вас.") if persona else "Слушаю вас."
                    display.show_notification(reply, title=persona.name if persona else "Моника")
                    if speaker:
                        speaker.speak(reply)
                    
                    # 3. Слушаем команду через Faster-Whisper на RTX 4060
                    text = ears.record_and_transcribe(duration_sec=4)
                    if text:
                        display.log(f"Распознано: '{text}'", tag="INFO")
                        engine.execute(text)
                    else:
                        display.log("Команда не услышана, возврат в ожидание.", tag="WARN")
            except KeyboardInterrupt:
                display.log("Прослушивание остановлено пользователем.", tag="INFO")
                break
    else:
        # Fallback-режим циклической записи
        display.log("Запущен циклический режим прослушивания микрофона (Wake Word выключен). Нажмите Ctrl+C для выхода.", tag="INFO")
        while True:
            try:
                text = ears.record_and_transcribe(duration_sec=4)
                if text:
                    display.log(f"Услышано: {text}", tag="INFO")
                    engine.execute(text)
            except KeyboardInterrupt:
                display.log("Прослушивание остановлено.", tag="INFO")
                break


def main():
    parser = argparse.ArgumentParser(description="My Custom Agent — Ассистент управления ПК")
    parser.add_argument("--exec", type=str, help="Выполнить одну команду и сразу выйти (для хоткеев/hyprwhspr)")
    parser.add_argument("--listen", action="store_true", help="Запустить режим непрерывного прослушивания микрофона")
    parser.add_argument("--dialog", action="store_true", help="Принудительно использовать двухэтапный режим (Wake Word -> Слушаю -> Команда)")
    parser.add_argument("--voice", type=str, choices=["nyamura_warm", "nyamura_smooth", "baya"], help="Временно выбрать голос (nyamura_warm, nyamura_smooth, baya)")
    args = parser.parse_args()

    config, display, persona, speaker, ears, engine, wake_detector = init_agent()
    if args.voice and speaker:
        speaker.set_preset(args.voice)
    mode = "dialog" if args.dialog else config.get("system", {}).get("mode", "oneshot")

    if args.exec:
        # Выполнение одиночной команды из аргументов
        engine.execute(args.exec)
        sys.exit(0)

    if args.listen:
        # Режим микрофона
        listen_mode(engine, ears, display, persona=persona, speaker=speaker, wake_detector=wake_detector, mode=mode)
    else:
        # По умолчанию — интерактивный терминальный режим
        interactive_mode(engine, persona, display, ears=ears, speaker=speaker, wake_detector=wake_detector, mode=mode)


if __name__ == "__main__":
    main()
