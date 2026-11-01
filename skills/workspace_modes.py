"""
Скилл режимов рабочих пространств.
Каждый режим открывает нужные приложения на нужных workspace.

Реализует недублирующееся поведение:
- Если приложение уже открыто на нужном воркспейсе — оставляет его на месте.
- Если приложение открыто на другом воркспейсе — перемещает его на нужный воркспейс.
- Если не открыто — запускает.
- Для закрытия режима — закрывает только реально открытые приложения без ошибок.
"""

import json
import re
import subprocess
import time
from core.engine import skill


# ─────────────────────────────────────────────
# Вспомогательные функции Hyprland
# ─────────────────────────────────────────────

def _dispatch(cmd: str):
    """Выполняет hyprctl dispatch команду (стиль Omarchy)."""
    subprocess.run(["hyprctl", "dispatch", cmd], check=False)


def _focus_workspace(ws: int):
    """Переключиться на указанный workspace."""
    _dispatch(f'hl.dsp.focus({{ workspace = "{ws}" }})')
    time.sleep(0.2)


def _get_open_windows():
    """Получить список всех открытых окон из Hyprland."""
    try:
        raw = subprocess.check_output(["hyprctl", "clients", "-j"]).decode()
        return json.loads(raw)
    except Exception:
        return []


def _find_window_by_pattern(clients, pattern: str):
    """Найти окно по регулярке в class, initialClass или title."""
    for c in clients:
        cls = c.get("class", "") or ""
        init_cls = c.get("initialClass", "") or ""
        title = c.get("title", "") or ""
        if (re.search(pattern, cls, re.I) or
            re.search(pattern, init_cls, re.I) or
            re.search(pattern, title, re.I)):
            return c
    return None


def _ensure_app_on_workspace(pattern: str, target_ws: int, launch_cmd: str, delay: float = 1.0):
    """
    Умное размещение приложения на воркспейсе:
    1. Если уже на target_ws -> оставляем.
    2. Если на другом воркспейсе -> перемещаем на target_ws.
    3. Если не открыто -> фокусируем target_ws и запускаем.
    """
    clients = _get_open_windows()
    win = _find_window_by_pattern(clients, pattern)

    if win:
        current_ws = win.get("workspace", {}).get("id")
        addr = win.get("address")
        if current_ws != target_ws and addr:
            _dispatch(f'hl.dsp.focus({{ window = "address:{addr}" }})')
            _dispatch(f'hl.dsp.window.move({{ workspace = "{target_ws}", follow = false }})')
            time.sleep(0.1)
    else:
        _focus_workspace(target_ws)
        subprocess.Popen(launch_cmd, shell=True)
        time.sleep(delay)


def _close_app_by_pattern(pattern: str):
    """Закрывает окно приложения по паттерну, если оно открыто."""
    clients = _get_open_windows()
    for c in clients:
        cls = c.get("class", "") or ""
        init_cls = c.get("initialClass", "") or ""
        title = c.get("title", "") or ""
        if (re.search(pattern, cls, re.I) or
            re.search(pattern, init_cls, re.I) or
            re.search(pattern, title, re.I)):
            addr = c.get("address")
            if addr:
                _dispatch(f'hl.dsp.focus({{ window = "address:{addr}" }})')
                _dispatch('hl.dsp.window.close()')
                time.sleep(0.1)


# ─────────────────────────────────────────────
# Управление Zapret (тихий фоновый демон)
# ─────────────────────────────────────────────

ZAPRET_DIR = "/home/armen/zapret-discord-youtube-linux"
ZAPRET_SCRIPT = f"{ZAPRET_DIR}/service.sh"


def _zapret_is_running() -> bool:
    """Проверяет, запущен ли процесс zapret (nfqws)."""
    result = subprocess.run(["pgrep", "-f", "nfqws"], capture_output=True)
    return result.returncode == 0


def _start_zapret():
    """Запускает zapret в фоне с настроенной стратегией general_alt11.bat."""
    if _zapret_is_running():
        return

    # Запускаем через service.sh в фоновом режиме демона
    subprocess.Popen(
        f"cd {ZAPRET_DIR} && sudo bash service.sh run --config conf.env >/dev/null 2>&1 &",
        shell=True
    )
    time.sleep(0.5)


# ─────────────────────────────────────────────
# 1. Режим разработки
# ─────────────────────────────────────────────

@skill(
    name="mode_dev",
    triggers=[
        "хочу кодить",
        "включи режим разработки",
        "режим разработки",
        "режим работы",
        "рабочий режим",
        "i want to code",
        "dev mode",
        "coding mode",
    ],
    description="Открывает рабочее пространство разработчика (WS5: Zapret, Unlocker, YT; WS1: Code, Antigravity)"
)
def mode_dev(text: str, context: dict) -> dict:
    # ── Workspace 5 ─────────────────────────────
    _focus_workspace(5)
    _start_zapret()
    _ensure_app_on_workspace(r"antigravity\s*unlocker", 5, 'bash "/home/armen/.local/share/ag-unlocker/launch.sh"', delay=2.5)
    _ensure_app_on_workspace(r"youtube", 5, 'omarchy-launch-webapp "https://www.youtube.com/watch?v=hG76BKNQQc4&t=8948s"', delay=1.0)

    # ── Workspace 1 ─────────────────────────────
    _focus_workspace(1)
    _ensure_app_on_workspace(r"com\.microsoft\.VSCode|code", 1, "code", delay=1.5)
    _ensure_app_on_workspace(r"^antigravity$", 1, "antigravity", delay=1.5)

    return {
        "reply": "Режим разработки включён.",
        "emotion": "focused"
    }


@skill(
    name="close_mode_dev",
    triggers=[
        "закрой режим разработки",
        "закрыть режим разработки",
        "закрой режим работы",
        "закрыть режим работы",
        "выключи режим разработки"
    ],
    description="Закрывает приложения режима разработки"
)
def close_mode_dev(text: str, context: dict) -> dict:
    _close_app_by_pattern(r"com\.microsoft\.VSCode|code")
    _close_app_by_pattern(r"^antigravity$")
    _close_app_by_pattern(r"antigravity\s*unlocker")
    _close_app_by_pattern(r"youtube")

    return {
        "reply": "Режим разработки закрыт.",
        "emotion": "neutral"
    }


# ─────────────────────────────────────────────
# 2. Режим учёбы
# ─────────────────────────────────────────────

@skill(
    name="mode_study",
    triggers=[
        "включи учёбу",
        "включи учебу",
        "хочу учиться",
        "режим учебы",
        "режим учёбы",
        "study mode",
    ],
    description="Открывает рабочее пространство для учёбы (WS1: Obsidian; WS2: Telegram, VK; WS5: Zapret, Throne)"
)
def mode_study(text: str, context: dict) -> dict:
    # ── Workspace 1 ─────────────────────────────
    _focus_workspace(1)
    _ensure_app_on_workspace(r"obsidian", 1, "obsidian", delay=1.5)

    # ── Workspace 2 ─────────────────────────────
    _focus_workspace(2)
    _ensure_app_on_workspace(r"org\.telegram\.desktop|telegram", 2, "Telegram", delay=1.0)
    _ensure_app_on_workspace(r"vk\.ru|vk", 2, 'omarchy-launch-webapp "https://vk.ru/im"', delay=1.0)

    # ── Workspace 5 ─────────────────────────────
    _focus_workspace(5)
    _start_zapret()
    _ensure_app_on_workspace(r"throne", 5, "throne", delay=1.5)

    # Возвращаемся на рабочий стол 1 (Obsidian)
    _focus_workspace(1)

    return {
        "reply": "Режим учёбы готов.",
        "emotion": "focused"
    }


@skill(
    name="close_mode_study",
    triggers=[
        "закрой режим учёбы",
        "закрой режим учебы",
        "закрыть режим учёбы",
        "закрыть режим учебы",
        "выключи режим учёбы"
    ],
    description="Закрывает приложения режима учёбы"
)
def close_mode_study(text: str, context: dict) -> dict:
    _close_app_by_pattern(r"obsidian")
    _close_app_by_pattern(r"org\.telegram\.desktop|telegram")
    _close_app_by_pattern(r"vk\.ru|vk")
    _close_app_by_pattern(r"throne")

    return {
        "reply": "Приложения режима учёбы закрыты.",
        "emotion": "neutral"
    }


# ─────────────────────────────────────────────
# 3. Ежедневный режим
# ─────────────────────────────────────────────

@skill(
    name="mode_daily",
    triggers=[
        "начало дня",
        "открой заметки",
        "daily mode",
        "ежедневный режим",
        "утренний режим",
        "доброе утро",
        "good morning",
    ],
    description="Открывает ежедневное рабочее пространство (WS1: Obsidian; WS2: Telegram; WS5: Zapret, Throne)"
)
def mode_daily(text: str, context: dict) -> dict:
    # ── Workspace 1 ─────────────────────────────
    _focus_workspace(1)
    _ensure_app_on_workspace(r"obsidian", 1, "obsidian", delay=1.5)

    # ── Workspace 2 ─────────────────────────────
    _focus_workspace(2)
    _ensure_app_on_workspace(r"org\.telegram\.desktop|telegram", 2, "Telegram", delay=1.0)

    # ── Workspace 5 ─────────────────────────────
    _focus_workspace(5)
    _start_zapret()
    _ensure_app_on_workspace(r"throne", 5, "throne", delay=1.5)

    # Возвращаемся на стол 1
    _focus_workspace(1)

    return {
        "reply": "Доброе утро! Все приложения для начала дня готовы.",
        "emotion": "smile"
    }


@skill(
    name="close_mode_daily",
    triggers=[
        "закрой ежедневный режим",
        "закрыть ежедневный режим",
        "выключи ежедневный режим"
    ],
    description="Закрывает приложения ежедневного режима"
)
def close_mode_daily(text: str, context: dict) -> dict:
    _close_app_by_pattern(r"obsidian")
    _close_app_by_pattern(r"org\.telegram\.desktop|telegram")
    _close_app_by_pattern(r"throne")

    return {
        "reply": "Ежедневный режим завершён.",
        "emotion": "neutral"
    }
