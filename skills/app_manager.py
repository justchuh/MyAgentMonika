"""
Скилл открытия и закрытия любого приложения по имени (с поддержкой русского и английского).
Поддерживает:
1. Базу популярных приложений с русскими/английскими синонимами и сленгом (Яндекс Музыка, ТГ, Код, ВК...).
2. Автоматическое сканирование всех .desktop файлов системы (/usr/share/applications и ~/.local/share/applications),
   благодаря чему можно открыть абсолютно любую установленную программу на компьютере.
3. Умное перемещение: если окно уже открыто на другом воркспейсе — переносит его на текущий экран.
4. Безопасное закрытие: если программа не была открыта — спокойно сообщает без ошибок.
"""

import configparser
import json
import re
import shutil
import subprocess
from pathlib import Path
from core.engine import skill

# База приоритетных приложений: алиасы (рус/англ), регулярка для поиска в Hyprland, и команда запуска
APP_REGISTRY = {
    "yandexmusic": {
        "aliases": ["яндекс музыка", "яндекс музыку", "яндекс", "музыка", "музыку", "yandex music", "yandexmusic", "yandex"],
        "class_regex": r"yandexmusic|yandex-music|yandex",
        "launch_cmd": '"/opt/yandex-music/yandexmusic" --gtk-version=3',
        "display_name": "Яндекс Музыка"
    },
    "code": {
        "aliases": ["код", "вскод", "vs code", "vscode", "code", "визуал студио"],
        "class_regex": r"com\.microsoft\.VSCode|code",
        "launch_cmd": "code",
        "display_name": "VS Code"
    },
    "telegram": {
        "aliases": ["телеграм", "телега", "тг", "telegram", "telegram desktop"],
        "class_regex": r"org\.telegram\.desktop|telegram",
        "launch_cmd": "Telegram",
        "display_name": "Telegram"
    },
    "obsidian": {
        "aliases": ["обсидиан", "заметки", "конспекты", "obsidian"],
        "class_regex": r"obsidian",
        "launch_cmd": "obsidian",
        "display_name": "Obsidian"
    },
    "throne": {
        "aliases": ["трон", "throne"],
        "class_regex": r"throne",
        "launch_cmd": "throne",
        "display_name": "Throne"
    },
    "antigravity": {
        "aliases": ["антигравити", "анти гравити", "antigravity"],
        "class_regex": r"^antigravity$",
        "launch_cmd": "antigravity",
        "display_name": "Antigravity"
    },
    "vk": {
        "aliases": ["вк", "вконтакте", "vk", "vkontakte"],
        "class_regex": r"vk\.ru|vk",
        "launch_cmd": 'omarchy-launch-webapp "https://vk.ru/im"',
        "display_name": "VK"
    },
    "discord": {
        "aliases": ["дискорд", "discord"],
        "class_regex": r"discord",
        "launch_cmd": 'omarchy-launch-webapp "https://discord.com/channels/@me"',
        "display_name": "Discord"
    },
    "youtube": {
        "aliases": ["ютуб", "youtube", "концентрация", "concentration"],
        "class_regex": r"youtube",
        "launch_cmd": 'omarchy-launch-webapp "https://www.youtube.com/watch?v=hG76BKNQQc4&t=8948s"',
        "display_name": "YouTube"
    },
    "terminal": {
        "aliases": ["терминал", "консоль", "alacritty", "terminal"],
        "class_regex": r"alacritty",
        "launch_cmd": "alacritty",
        "display_name": "Терминал"
    },
    "chrome": {
        "aliases": ["хром", "гугл хром", "chrome", "google chrome", "chromium"],
        "class_regex": r"google-chrome|chromium",
        "launch_cmd": "chromium",
        "display_name": "Chrome"
    },
    "firefox": {
        "aliases": ["фаерфокс", "лиса", "firefox"],
        "class_regex": r"firefox",
        "launch_cmd": "firefox",
        "display_name": "Firefox"
    },
    "steam": {
        "aliases": ["стим", "steam"],
        "class_regex": r"steam",
        "launch_cmd": "steam",
        "display_name": "Steam"
    }
}


def _get_active_workspace_id() -> int:
    """Возвращает ID текущего активного воркспейса Hyprland."""
    try:
        data = json.loads(subprocess.check_output(["hyprctl", "activeworkspace", "-j"]).decode())
        return int(data.get("id", 1))
    except Exception:
        return 1


def _find_windows(pattern: str):
    """Ищет окна в Hyprland по регулярному выражению (class / initialClass / title)."""
    try:
        clients = json.loads(subprocess.check_output(["hyprctl", "clients", "-j"]).decode())
        matches = []
        for c in clients:
            cls = c.get("class", "") or ""
            init_cls = c.get("initialClass", "") or ""
            title = c.get("title", "") or ""
            if (re.search(pattern, cls, re.I) or
                re.search(pattern, init_cls, re.I) or
                re.search(pattern, title, re.I)):
                matches.append(c)
        return matches
    except Exception:
        return []


def _scan_system_desktop_apps():
    """Динамически сканирует все .desktop файлы в системе."""
    dirs = [
        Path.home() / ".local/share/applications",
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications")
    ]
    apps = []
    seen = set()

    for folder in dirs:
        if not folder.exists():
            continue
        for f in folder.glob("*.desktop"):
            if f.name in seen:
                continue
            seen.add(f.name)

            try:
                cp = configparser.ConfigParser(interpolation=None)
                cp.read(f, encoding="utf-8")
                sec = "Desktop Entry"
                if not cp.has_section(sec):
                    continue
                if cp.getboolean(sec, "NoDisplay", fallback=False):
                    continue

                name = cp.get(sec, "Name", fallback="").strip()
                name_ru = cp.get(sec, "Name[ru]", fallback="").strip()
                exec_cmd = cp.get(sec, "Exec", fallback="").strip()
                wm_class = cp.get(sec, "StartupWMClass", fallback=f.stem).strip()

                if name and exec_cmd:
                    clean_exec = re.sub(r"\%[a-zA-Z]", "", exec_cmd).strip()
                    apps.append({
                        "name": name,
                        "name_ru": name_ru,
                        "stem": f.stem,
                        "exec_cmd": clean_exec,
                        "wm_class": wm_class
                    })
            except Exception:
                pass
    return apps


def _match_app_entry(text: str):
    """Ищет подходящее приложение сначала в реестре, затем по .desktop файлам системы."""
    clean = text.lower().strip()

    # 1. Поиск в явном реестре популярных приложений
    for key, info in APP_REGISTRY.items():
        for alias in sorted(info["aliases"], key=len, reverse=True):
            if re.search(r"\b" + re.escape(alias) + r"\b", clean) or alias in clean:
                return info

    # 2. Поиск по всем .desktop файлам ПК
    # Очищаем фразу от служебных слов
    target = clean
    for stop in ["открой приложение", "запусти приложение", "включи приложение",
                 "закрой приложение", "выключи приложение",
                 "открой", "запусти", "включи", "закрой", "выключи",
                 "open app", "close app", "open", "close", "launch", "пожалуйста"]:
        target = target.replace(stop, "").strip()

    target = re.sub(r"^[,\.!?\"'\-\s]+|[,\.!?\"'\-\s]+$", "", target).strip()
    if not target:
        return None

    desktop_apps = _scan_system_desktop_apps()
    for app in desktop_apps:
        names_to_check = [app["name"].lower(), app["stem"].lower()]
        if app["name_ru"]:
            names_to_check.append(app["name_ru"].lower())

        for n in names_to_check:
            if n == target or target in n or n in target:
                return {
                    "display_name": app["name_ru"] or app["name"],
                    "class_regex": re.escape(app["wm_class"]) if app["wm_class"] else re.escape(app["name"]),
                    "launch_cmd": app["exec_cmd"]
                }

    return None


@skill(
    name="app_open_by_name",
    triggers=[
        "открой приложение",
        "запусти приложение",
        "включи приложение",
        "открой программу",
        "запусти программу",
        "открой",
        "запусти",
        "open app",
        "launch app",
        "open",
        "launch"
    ],
    description="Открывает приложение по имени, либо перемещает уже запущенное на текущий стол"
)
def open_app(text: str, context: dict) -> dict:
    entry = _match_app_entry(text)

    if entry:
        display_name = entry["display_name"]
        class_regex = entry["class_regex"]
        launch_cmd = entry["launch_cmd"]

        current_ws = _get_active_workspace_id()
        existing_windows = _find_windows(class_regex)

        if existing_windows:
            win = existing_windows[0]
            win_ws = win.get("workspace", {}).get("id")
            addr = win.get("address")

            if win_ws == current_ws:
                subprocess.run(["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{addr}" }})'], check=False)
                return {
                    "reply": f"{display_name} уже открыт на этом рабочем столе.",
                    "emotion": "smile"
                }
            else:
                subprocess.run(["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{addr}" }})'], check=False)
                subprocess.run(["hyprctl", "dispatch", f'hl.dsp.window.move({{ workspace = "{current_ws}", follow = true }})'], check=False)
                return {
                    "reply": f"Переместила {display_name} с {win_ws} рабочего стола на текущий.",
                    "emotion": "happy"
                }
        else:
            subprocess.Popen(launch_cmd, shell=True)
            return {
                "reply": f"Открываю {display_name}.",
                "emotion": "smile"
            }

    # Попытка найти бинарник в PATH
    words = [w for w in re.split(r"[\s,.-]+", text.lower()) if w not in [
        "открой", "запусти", "включи", "open", "launch", "приложение", "программу", "пожалуйста"
    ]]
    if words:
        raw_name = words[0]
        if shutil.which(raw_name):
            subprocess.Popen([raw_name])
            return {
                "reply": f"Запускаю {raw_name}.",
                "emotion": "neutral"
            }

    return {
        "reply": "Не удалось определить, какое приложение нужно открыть.",
        "emotion": "confused"
    }


@skill(
    name="app_close_by_name",
    triggers=[
        "закрой приложение",
        "закрой программу",
        "выключи приложение",
        "закрой",
        "закрыть",
        "close app",
        "close"
    ],
    description="Закрывает приложение по имени без ошибок, если оно не было открыто"
)
def close_app(text: str, context: dict) -> dict:
    entry = _match_app_entry(text)

    if entry:
        display_name = entry["display_name"]
        class_regex = entry["class_regex"]

        existing_windows = _find_windows(class_regex)
        if not existing_windows:
            return {
                "reply": f"{display_name} сейчас не запущен.",
                "emotion": "neutral"
            }

        for win in existing_windows:
            addr = win.get("address")
            subprocess.run(["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{addr}" }})'], check=False)
            subprocess.run(["hyprctl", "dispatch", "hl.dsp.window.close()"], check=False)

        return {
            "reply": f"Закрыла {display_name}.",
            "emotion": "focused"
        }

    return {
        "reply": "Не поняла, какое приложение нужно закрыть.",
        "emotion": "confused"
    }
