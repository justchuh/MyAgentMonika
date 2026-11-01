"""
Скилл макросов: загружает macros.yaml и выполняет пачки команд Hyprland.
Каждый макрос из macros.yaml автоматически становится доступной голосовой командой!
"""

import subprocess
import time
from pathlib import Path
import yaml
from core.engine import SKILLS_REGISTRY

MACROS_FILE = Path(__file__).parent.parent / "macros.yaml"

def _load_and_register_macros():
    """Считывает macros.yaml и регистрирует каждый макрос в реестре скиллов."""
    if not MACROS_FILE.exists():
        return

    try:
        with open(MACROS_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        macros = data.get("macros", {})
        for name, macro in macros.items():
            trigger = name.strip().lower()
            reply = macro.get("reply", "Макрос выполнен")
            emotion = macro.get("emotion", "happy")
            actions = macro.get("actions", [])

            # Создаем функцию-обработчик с замыканием на конкретные действия
            def make_handler(act_list, rep_text, emo):
                def handler(text: str, context: dict):
                    display = context.get("display")
                    for action in act_list:
                        try:
                            # Выполняем каждую команду через shell
                            subprocess.run(action, shell=True, check=False)
                            time.sleep(0.05) # Небольшая задержка между командами
                        except Exception as e:
                            if display:
                                display.log(f"Ошибка в действии '{action}': {e}", tag="ERROR")

                    return {
                        "reply": rep_text,
                        "emotion": emo
                    }
                return handler

            # Регистрируем в реестре
            SKILLS_REGISTRY.append({
                "name": f"macro_{trigger}",
                "triggers": [trigger],
                "description": macro.get("description", f"Макрос {trigger}"),
                "handler": make_handler(actions, reply, emotion)
            })

    except Exception as e:
        print(f"[workspace_macros] Ошибка загрузки {MACROS_FILE}: {e}")

# Загружаем при импорте модуля
_load_and_register_macros()
