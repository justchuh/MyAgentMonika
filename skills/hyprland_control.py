"""
Скилл прямого управления окнами и рабочими столами Hyprland (с поддержкой Omarchy / Lua).
"""

import re
import subprocess
from core.engine import skill


def dispatch_lua(expression: str):
    """Выполняет команду диспетчера Hyprland через Lua (стандарт Omarchy)."""
    return subprocess.run(["hyprctl", "dispatch", expression], check=False)


@skill(
    name="hyprland_switch_workspace",
    triggers=[
        "переключи стол",
        "переключить стол",
        "смени стол",
        "сменить стол",
        "перейди на стол",
        "рабочий стол",
        "воркспейс",
        "стол номер",
        "переключи на стол",
        "перейти к столу",
        "перейти на рабочий стол",
        "стол",
        "switch workspace",
        "workspace"
    ],
    description="Переключение на указанный рабочий стол Hyprland"
)
def switch_workspace(text: str, context: dict) -> str:
    # Ищем число в команде (например, "переключи на рабочий стол 2" или "стол 3")
    match = re.search(r"\b(\d+)\b", text)
    ws_num = None
    if match:
        ws_num = match.group(1)
    else:
        # Текстовые числительные
        word_map = {
            "первый": "1", "один": "1",
            "второй": "2", "два": "2",
            "третий": "3", "три": "3",
            "четвертый": "4", "четвёртый": "4", "четыре": "4",
            "пятый": "5", "пять": "5",
            "шестой": "6", "шесть": "6",
            "седьмой": "7", "семь": "7",
            "восьмой": "8", "восемь": "8",
            "девятый": "9", "девять": "9",
            "десятый": "10", "десять": "10"
        }
        for word, num in word_map.items():
            if word in text.lower():
                ws_num = num
                break

    if ws_num:
        dispatch_lua(f'hl.dsp.focus({{ workspace = "{ws_num}" }})')
        return f"Переключила на рабочий стол {ws_num}."

    return "На какой стол?"


@skill(
    name="hyprland_close_active",
    triggers=[
        "закрой окно",
        "закрыть окно",
        "закрывай окно",
        "закрой текущее окно",
        "убей окно",
        "close window"
    ],
    description="Закрывает активное окно Hyprland"
)
def close_window(text: str, context: dict) -> str:
    dispatch_lua('hl.dsp.window.close()')
    return "Окно закрыто."


@skill(
    name="hyprland_fullscreen",
    triggers=[
        "на весь экран",
        "полный экран",
        "в полноэкранный режим",
        "полноэкранный режим",
        "включить полноэкранный",
        "разверни окно",
        "fullscreen"
    ],
    description="Переключает окно в полноэкранный режим (Super+F)"
)
def toggle_fullscreen(text: str, context: dict) -> str:
    dispatch_lua('hl.dsp.window.fullscreen({ mode = "fullscreen" })')
    return "Полноэкранный режим переключен."
