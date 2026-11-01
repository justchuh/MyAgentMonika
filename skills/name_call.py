"""
Скилл управления обращением по имени (включение / отключение / смена имени).
Сохраняет настройки в character.yaml и обновляет текущую сессию PersonaManager.
"""
from core.constants import DEFAULT_USER_NAME
import re
from pathlib import Path
import yaml
from core.engine import skill

CHARACTER_FILE = Path(__file__).parent.parent / "character.yaml"


def _update_character_call_user(name: str):
    """Обновляет поле persona.call_user в character.yaml."""
    if not CHARACTER_FILE.exists():
        return
    try:
        with open(CHARACTER_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if "persona" not in data:
            data["persona"] = {}

        data["persona"]["call_user"] = name

        with open(CHARACTER_FILE, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"[name_call] Ошибка сохранения {CHARACTER_FILE}: {e}")


@skill(
    name="enable_name_call",
    triggers=[
        "включи обращение по имени",
        "включить обращение по имени",
        "обращайся ко мне по имени",
        "обращайся по имени",
        "называй меня по имени",
        "называй по имени",
        "запомни мое имя",
        "называй меня",
        "зови меня",
        "обращайся ко мне",
        "включи имя",
        "включить имя",
    ],
    description="Включает или обновляет персональное обращение к пользователю по имени"
)
def enable_name_call(text: str, context: dict) -> dict:
    persona = context.get("persona")

    # Проверяем, указал ли пользователь конкретное имя во фразе (например "называй меня Армен")
    clean = text.lower()
    custom_name = ""
    for prefix in ["называй меня", "обращайся ко мне как", "запомни мое имя", "по имени", "зови меня"]:
        if prefix in clean:
            after = clean.split(prefix, 1)[1].strip()
            # Берем первое слово после префикса
            words = [w for w in re.split(r"[\s,.-]+", after) if w]
            if words:
                custom_name = words[0].capitalize()
                break

    if not custom_name:
        # Если имя не названо в команде — берем существующее или дефолтное "Армен"
        if persona and persona.call_user:
            custom_name = persona.call_user
        else: 
            custom_name = DEFAULT_USER_NAME

    if persona:
        persona.call_user = custom_name

    _update_character_call_user(custom_name)

    return {
        "reply": f"Хорошо, {custom_name}, теперь буду обращаться к вам по имени.",
        "emotion": "smile"
    }


@skill(
    name="disable_name_call",
    triggers=[
        "выключи обращение по имени",
        "выключить обращение по имени",
        "отключи обращение по имени",
        "отключить обращение по имени",
        "не называй меня по имени",
        "без обращения",
        "убери обращение"
    ],
    description="Отключает обращение к пользователю по имени"
)
def disable_name_call(text: str, context: dict) -> dict:
    persona = context.get("persona")
    if persona:
        persona.call_user = ""

    _update_character_call_user("")

    return {
        "reply": "Обращение по имени отключено. Буду отвечать нейтрально.",
        "emotion": "neutral"
    }
