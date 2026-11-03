"""
Скилл голосовой диктовки (интеграция с Hyprwhspr / Ctrl+Shift+Z).
Позволяет голосом запускать и останавливать диктовку текста прямо в активное окно.
"""

import subprocess
import time
from core.engine import skill


def _get_hyprwhspr_status() -> str:
    """Возвращает статус Hyprwhspr: 'recording', 'idle' или 'unknown'."""
    try:
        res = subprocess.run(
            ["hyprwhspr", "record", "status"],
            capture_output=True,
            text=True,
            timeout=2
        )
        out = (res.stdout + res.stderr).lower()
        if "recording" in out:
            return "recording"
        return "idle"
    except Exception:
        return "unknown"


@skill(
    name="dictation_toggle",
    triggers=[
        "включи диктовку",
        "начни диктовку",
        "начать диктовку",
        "запусти диктовку",
        "голосовой ввод",
        "включи голосовой ввод",
        "начни писать",
        "начни печатать", 
        "диктовка",
        "диктуй",
        "гипервиспер",
        "хайпервиспер",
        "hyperwhisper",
        "hyprwhspr",
        "вставь текст",
        "останови диктовку",
        "закончи диктовку",
        "выключи диктовку",
        "заверши диктовку",
        "стоп диктовка"
    ],
    description="Управление диктовкой Hyprwhspr (вставка распознанного текста в активное окно)"
)
def handle_dictation(text: str, context: dict) -> dict:
    display = context.get("display")
    clean = text.lower()
    status = _get_hyprwhspr_status()

    # Проверяем, просит ли пользователь остановить диктовку
    stop_words = ["останови", "закончи", "выключи", "заверши", "вставь", "стоп"]
    is_stop_cmd = any(w in clean for w in stop_words)

    if status == "recording" or is_stop_cmd:
        # Останавливаем запись — Hyprwhspr автоматически транскрибирует и вставляет текст
        try:
            subprocess.run(["hyprwhspr", "record", "stop"], check=False)
        except Exception as e:
            if display:
                display.log(f"[dictation] Ошибка остановки: {e}", tag="ERROR")

        if display:
            display.show_notification("Диктовка завершена. Вставляю текст...", title="Hyprwhspr")

        return {
            "reply": "Текст готов, вставляю.",
            "emotion": "happy"
        }

    # Иначе — запускаем диктовку
    # Чтобы голос Моники не попал в записываемый текст, мы делаем запуск тихим
    try:
        subprocess.run(["hyprwhspr", "record", "start"], check=False)
    except Exception as e:
        if display:
            display.log(f"[dictation] Ошибка запуска: {e}", tag="ERROR")

    if display:
        display.show_notification("Слушаю для диктовки... Говорите текст.", title="Hyprwhspr")

    # Возвращаем пустую реплику, чтобы синтезатор речи не засорял микрофон своими фразами
    return {
        "reply": "",
        "emotion": "smile"
    }
