"""
Скилл управления звуком и медиаплеером (Яндекс.Музыка, Chromium, pamixer, MPRIS/busctl/playerctl).
"""

import re
import shutil
import subprocess
from core.engine import skill


def _send_mpris_action(action: str) -> bool:
    """
    Отправляет команду воспроизведения (PlayPause, Play, Pause).
    Если установлен playerctl — использует его.
    Иначе напрямую через системную шину DBus / busctl находит все запущенные медиаплееры.
    """
    if shutil.which("playerctl"):
        cmd_map = {"PlayPause": "play-pause", "Play": "play", "Pause": "pause"}
        subprocess.run(["playerctl", cmd_map.get(action, "play-pause")], check=False)
        return True

    # Нативный fallback через busctl (работает для Яндекс Музыки, браузеров и любых плееров)
    try:
        out = subprocess.check_output(["busctl", "--user", "list"]).decode()
        found = False
        for line in out.splitlines():
            parts = line.split()
            if parts and parts[0].startswith("org.mpris.MediaPlayer2."):
                found = True
                subprocess.run(
                    ["busctl", "--user", "call", parts[0], "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", action],
                    check=False
                )
        return found
    except Exception:
        return False


@skill(
    name="media_volume_control",
    triggers=[
        "выключи звук",
        "выключить звук",
        "включи звук",
        "включить звук",
        "верни звук",
        "разглуши",
        "полностью заглуши",
        "полную тишину",
        "заглуши",
        "без звука",
        "громче",
        "тише",
        "прибавь звук",
        "убавь звук",
        "увеличь громкость",
        "подними громкость",
        "уменьши громкость",
        "снизь громкость",
        "убавь громкость",
        "громкость",
        "volume up",
        "volume down",
        "unmute",
        "mute"
    ],
    description="Управление громкостью, mute и unmute через pamixer"
)
def control_volume(text: str, context: dict) -> str:
    has_pamixer = shutil.which("pamixer") is not None
    if not has_pamixer:
        return "Утилита pamixer не найдена в системе."

    clean = text.lower()

    # 1. Полное отключение звука (Mute)
    if any(k in clean for k in ["выключи звук", "выключить звук", "заглуши", "тишину", "без звука", "mute"]):
        subprocess.run(["pamixer", "--mute"], check=False)
        return "Звук полностью выключен."

    # 2. Включение звука обратно (Unmute)
    if any(k in clean for k in ["включи звук", "включить звук", "верни звук", "разглуши", "unmute"]):
        subprocess.run(["pamixer", "--unmute"], check=False)
        return "Звук включен."

    # 3. Установка точной громкости (например "громкость 40" или "установи громкость на 50")
    match_digits = re.search(r"\b(\d+)\b", clean)
    step = int(match_digits.group(1)) if match_digits else 10

    if ("установи" in clean or "поставь" in clean) and match_digits:
        subprocess.run(["pamixer", "--unmute"], check=False)
        subprocess.run(["pamixer", "--set-volume", str(step)], check=False)
        return f"Громкость установлена на {step} процентов."

    if clean.startswith("громкость") and match_digits and not any(k in clean for k in ["прибавь", "убавь", "увеличь", "уменьши"]):
        subprocess.run(["pamixer", "--unmute"], check=False)
        subprocess.run(["pamixer", "--set-volume", str(step)], check=False)
        return f"Громкость установлена на {step} процентов."

    # 4. Прибавление громкости
    if any(k in clean for k in ["громче", "прибавь", "увеличь", "подними", "volume up"]):
        subprocess.run(["pamixer", "--unmute"], check=False)
        subprocess.run(["pamixer", "-i", str(step)], check=False)
        try:
            cur = subprocess.check_output(["pamixer", "--get-volume"]).decode().strip()
            return f"Громкость {cur} процентов."
        except Exception:
            return f"Громкость увеличена на {step} процентов."

    # 5. Убавление громкости
    if any(k in clean for k in ["тише", "убавь", "уменьши", "снизь", "volume down"]):
        subprocess.run(["pamixer", "-d", str(step)], check=False)
        try:
            cur = subprocess.check_output(["pamixer", "--get-volume"]).decode().strip()
            return f"Громкость {cur} процентов."
        except Exception:
            return f"Громкость уменьшена на {step} процентов."

    return "Не поняла команду громкости."


@skill(
    name="media_playback",
    triggers=[
        "пауза",
        "плей",
        "поставь на паузу",
        "продолжи воспроизведение",
        "воспроизведение",
        "продолжить",
        "стоп музыка",
        "играй музыку",
        "включи музыку",
        "пауза музыка",
        "play",
        "pause"
    ],
    description="Управление плеером (Яндекс.Музыка и др.) через D-Bus/playerctl"
)
def control_playback(text: str, context: dict) -> str:
    clean = text.lower()

    if any(k in clean for k in ["пауза", "стоп", "pause"]):
        _send_mpris_action("Pause")
        return "Пауза."
    elif any(k in clean for k in ["плей", "продолжи", "играй", "play", "воспроизведение"]):
        _send_mpris_action("Play")
        return "Воспроизведение запущено."
    else:
        _send_mpris_action("PlayPause")
        return "Медиа переключено."
