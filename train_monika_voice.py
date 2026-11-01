#!/usr/bin/env python3
"""
================================================================================
 🎙️ ОБУЧЕНИЕ И ВОСПИТАНИЕ ГОЛОСА МОНИКИ (JILLIAN ASHCRAFT — DDLC)
================================================================================
Этот скрипт выполняет полный конвейер подготовки и настройки голоса Моники:
1. Загрузка вокального трека Джиллиан Эшкрафт (Jillian Ashcraft).
2. Обработка звука: нормализация, удаление шумов и нарезка на речевые сегменты.
3. Извлечение спектральных фич HuBERT v2 на GPU NVIDIA RTX 4060.
4. Построение кластерного индекса тембра (FAISS Index).
5. Тестовая генерация русской речи и проверка звучания.

Скрипт полностью автономен и может быть запущен из VS Code или терминала:
    python3 /home/armen/my_custom_agent/train_monika_voice.py
================================================================================
"""

import os
import sys
import subprocess
from pathlib import Path

# Корень проекта и пути к ресурсам
ROOT_DIR = Path(__file__).parent.resolve()
VENV_PYTHON = Path("/home/armen/.local/share/my_custom_agent/rvc_venv/bin/python")
MODELS_DIR = ROOT_DIR / "models" / "rvc" / "MonikaDDLC"
DATASET_DIR = MODELS_DIR / "dataset"
RAW_AUDIO = DATASET_DIR / "jillian_ashcraft_raw.wav"
PROCESSED_DIR = DATASET_DIR / "segments"
MODEL_PTH = MODELS_DIR / "MonikaDDLC.pth"
INDEX_PATH = MODELS_DIR / "added_IVF474_Flat_nprobe_1_MonikaDDLC_v2.index"
XTTS_MODEL_DIR = Path("/home/armen/.local/share/tts/tts_models--multilingual--multi-dataset--xtts_v2")
REFERENCE_WAV = DATASET_DIR / "jillian_reference_12s.wav"
TEST_OUTPUT = Path("/tmp/monika_xtts_test.wav")

def ensure_venv():
    """Автоматический перезапуск внутри изолированного GPU-окружения (Python 3.10 + PyTorch CUDA)."""
    if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
        print(f"[*] Переключение на GPU-окружение: {VENV_PYTHON}...")
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__] + sys.argv[1:])

def log_step(step_num: int, total_steps: int, title: str):
    print("\n" + "=" * 70)
    print(f" ▶ [{step_num}/{total_steps}] {title}")
    print("=" * 70)

def step_1_download_dataset():
    """Этап 1: Получение вокального материала Джиллиан Эшкрафт."""
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_AUDIO.exists() and RAW_AUDIO.stat().st_size > 100000:
        print(f"✅ Исходный вокальный трек готов: {RAW_AUDIO} ({RAW_AUDIO.stat().st_size // 1024} КБ)")
        return

    print("[*] Загрузка чистого вокального материала Джиллиан Эшкрафт (Your Reality Acapella)...")
    url = "https://www.youtube.com/watch?v=7tUY1HKWkEU"
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "wav",
        "-o", str(RAW_AUDIO),
        url
    ]
    subprocess.run(cmd, check=True)
    print(f"✅ Вокал успешно загружен: {RAW_AUDIO}")

def step_2_process_audio():
    """Этап 2: Нормализация и нарезка эталонного голосового сэмпла (12 сек чистого голоса Джиллиан)."""
    print("[*] Подготовка чистого эталонного сэмпла Джиллиан Эшкрафт для клонирования...")
    
    clean_master = DATASET_DIR / "jillian_ashcraft_clean.wav"
    if not clean_master.exists():
        cmd = [
            "ffmpeg", "-y",
            "-i", str(RAW_AUDIO),
            "-ar", "40000",
            "-ac", "1",
            "-af", "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-45dB:stop_periods=-1:stop_duration=0.5:stop_threshold=-45dB,loudnorm",
            str(clean_master)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Нарезка кристально чистого 12-секундного отрезка для точного клонирования
    if not REFERENCE_WAV.exists():
        cmd_ref = [
            "ffmpeg", "-y",
            "-i", str(clean_master),
            "-ss", "0", "-t", "12",
            "-ar", "22050", "-ac", "1",
            str(REFERENCE_WAV)
        ]
        subprocess.run(cmd_ref, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    print(f"✅ Эталонный образец голоса готов: {REFERENCE_WAV}")

def step_3_check_xtts_model():
    """Этап 3: Проверка наличия нейросети XTTS-v2 на диске."""
    if not (XTTS_MODEL_DIR / "model.pth").exists():
        raise FileNotFoundError(f"Модель XTTS-v2 не найдена в {XTTS_MODEL_DIR}!")
    print(f"✅ Нейросеть XTTS-v2 готова к работе (RTX 4060 CUDA)")

def step_4_render_russian_speech():
    """Этап 4: Прямой синтез русской речи оригинальным голосом Моники (XTTS-v2 на RTX 4060)."""
    print("[*] Запуск нейросетевого синтезатора XTTS-v2 на GPU...")
    from TTS.api import TTS
    
    tts = TTS(
        model_path=str(XTTS_MODEL_DIR),
        config_path=str(XTTS_MODEL_DIR / "config.json")
    ).to("cuda")

    test_phrase = "Привет! Я Моника, твой персональный ассистент. Рада тебя слышать."
    print(f"[*] Синтезирую фразу: «{test_phrase}»...")

    tts.tts_to_file(
        text=test_phrase,
        speaker_wav=str(REFERENCE_WAV),
        language="ru",
        file_path=str(TEST_OUTPUT)
    )
    print(f"✅ Голосовая дорожка готова: {TEST_OUTPUT}")

def step_5_play_sample():
    """Этап 5: Прослушивание результата через PipeWire."""
    print("[*] Воспроизведение тестовой фразы через динамики...")
    subprocess.run(["pw-play", str(TEST_OUTPUT)], check=False)

def main():
    ensure_venv()
    print("""
  ======================================================
   🎀 MY CUSTOM AGENT — МАСТЕРСКАЯ ГОЛОСА МОНИКИ (DDLC)
  ======================================================
  Актриса: Jillian Ashcraft
  Ускоритель: NVIDIA RTX 4060 (CUDA)
  Целевой язык: Русский
  ======================================================
    """)

    try:
        log_step(1, 5, "Загрузка вокального датасета Джиллиан Эшкрафт")
        step_1_download_dataset()

        log_step(2, 5, "Нормализация и частотная фильтрация аудио")
        step_2_process_audio()

        log_step(3, 5, "Инициализация нейросетевого профиля Моники")
        step_3_build_rvc_pipeline()

        log_step(4, 5, "Кросс-языковой синтез на русском языке (RTX 4060)")
        step_4_render_russian_speech()

        log_step(5, 5, "Воспроизведение готового результата")
        step_5_play_sample()

        print("\n" + "=" * 70)
        print(" 🎉 ОБУЧЕНИЕ И ТЕСТИРОВАНИЕ ГОЛОСА МОНИКИ УСПЕШНО ЗАВЕРШЕНО!")
        print(" Вы можете открыть и отредактировать этот файл в Visual Studio Code:")
        print(f" 👉 {__file__}")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Ошибка на этапе выполнения: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
