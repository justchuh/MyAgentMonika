"""
Модуль управления личностью и репликами ассистента.
Загружает character.yaml, подбирает случайные реплики и форматирует обращения.
"""

import random
from pathlib import Path
import yaml


class PersonaManager:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.name = "Моника"
        self.call_user = ""
        self.dialogue = {}
        self.emotions = {}
        self.load()

    def load(self):
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            persona = data.get("persona", {})
            self.name = persona.get("name", "Моника")
            self.call_user = persona.get("call_user", "").strip()

            self.dialogue = data.get("dialogue", {})
            self.emotions = data.get("emotions", {})
        except Exception as e:
            print(f"[PersonaManager] Ошибка чтения {self.config_path}: {e}")

    def get_phrase(self, event_name: str, fallback: str = "") -> str:
        """Возвращает случайную реплику для указанного события."""
        phrases = self.dialogue.get(event_name, [])
        if not phrases:
            phrase = fallback
        else:
            phrase = random.choice(phrases)

        # Обращение по имени: 100% при оклике без команды (on_wake)
        if self.call_user and event_name == "on_wake":
            clean_name = self.call_user.strip()
            if not phrase.lower().startswith(clean_name.lower()):
                punct = "?" if phrase.endswith("?") else "."
                base = phrase.rstrip(".!? ")
                phrase = f"{base}, {clean_name}{punct}"

        return phrase

    def get_emotion(self, event_name: str, default: str = "neutral") -> str:
        """Возвращает эмоцию для Live2D/Waifuland."""
        return self.emotions.get(event_name, default)
