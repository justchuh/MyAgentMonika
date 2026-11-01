"""
Скилл системной блокировки и скринсейвера (нативно для Omarchy / Hyprland).
"""

import subprocess
from core.engine import skill


@skill(
    name="system_lock_pc",
    triggers=[
        "запереть компьютер",
        "заблокировать компьютер",
        "заблокировать экран",
        "заблокируй пк",
        "заблокируй",
        "запретить доступ",
        "lock in",
        "лок ин",
        "локин",
        "локын",
        "локынн",
        "логин",
        "лок",
        "залочь пк",
        "залочь",
        "lock pc",
        "lock screen"
    ],
    description="Блокирует экран системы с окном ввода пароля (omarchy-system-lock)"
)
def lock_pc(text: str, context: dict) -> dict:
    subprocess.Popen(["omarchy-system-lock"])
    return {
        "reply": "Блокирую компьютер.",
        "emotion": "focused"
    }


@skill(
    name="system_screensaver",
    triggers=[
        "включи скринсейвер",
        "запусти скринсейвер",
        "включить скринсейвер",
        "запусти заставку",
        "включи заставку",
        "начни защиту экрана",
        "скринсейвер",
        "screensaver",
        "start screensaver"
    ],
    description="Запускает заставку / скринсейвер системы Omarchy"
)
def start_screensaver(text: str, context: dict) -> dict:
    subprocess.Popen(["omarchy-launch-screensaver"])
    return {
        "reply": "Запускаю скринсейвер.",
        "emotion": "smile"
    }
