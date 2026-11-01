#!/usr/bin/env python3
"""
Скрипт тестирования микрофона и произношения ключевого слова "Моника".
1. Записывает 3 секунды аудио с вашего микрофона ALC897 Analog.
2. Проверяет уровень громкости сигнала.
3. Прогоняет запись через Faster-Whisper (CUDA/RTX 4060).
4. Прогоняет запись через нативный русский Vosk KWS (грамматика ["моника", "[unk]"]).
5. Прогоняет запись через Sherpa KWS на разных порогах.
"""

import os
import sys
import tempfile
import wave
import json
import subprocess
from pathlib import Path
import numpy as np

# Подключаем пути hermes для sherpa_onnx, если нужно
extra_path = "/home/armen/.hermes/tools/python-3.14.7+20260901-linux-x64/lib/python3.14/site-packages"
if extra_path not in sys.path and os.path.exists(extra_path):
    sys.path.insert(0, extra_path)

# Подгрузка CUDA библиотек для Whisper
try:
    import ctypes
    for d in [
        "/home/armen/.local/share/hyprwhspr/venv/lib/python3.14/site-packages/nvidia/cublas/lib",
        "/home/armen/.local/share/hyprwhspr/venv/lib/python3.14/site-packages/nvidia/cuda_nvrtc/lib"
    ]:
        if os.path.isdir(d):
            for lib in ["libcublasLt.so.12", "libcublas.so.12", "libnvrtc.so.12"]:
                p = os.path.join(d, lib)
                if os.path.exists(p):
                    try:
                        ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)
                    except Exception:
                        pass
except Exception:
    pass

# Патч PyAV для Whisper
try:
    import av
    _orig_av_open = av.open
    def _patched_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _patched_av_open
except Exception:
    pass


def main():
    print("=" * 65)
    print(" 🎙️ ТЕСТ МИКРОФОНА И ПРОИЗНОШЕНИЯ WAKE WORD ('МОНИКА')")
    print("=" * 65)
    
    input("\nНажмите [ENTER], чтобы начать запись, и скажите как обычно по-русски: «МОНИКА»...")

    temp_wav = "/tmp/test_monika.wav"
    if os.path.exists(temp_wav):
        os.remove(temp_wav)

    print("\n🔴 [ЗАПИСЬ 3 СЕКУНДЫ] Говорите: «Моника»...")
    
    # Запись
    cmd_arecord = ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "3", temp_wav]
    cmd_pw = ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", temp_wav]
    
    try:
        subprocess.run(cmd_arecord, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        try:
            p = subprocess.Popen(cmd_pw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import time
            time.sleep(3.2)
            p.terminate()
            p.wait()
        except Exception as e:
            print(f"❌ Ошибка захвата звука: {e}")
            return

    if not os.path.exists(temp_wav) or os.path.getsize(temp_wav) < 1000:
        print("❌ Аудиофайл не записался. Проверьте микрофон.")
        return

    # 1. Анализ громкости и формы сигнала
    with wave.open(temp_wav, "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        audio_data = np.frombuffer(frames, dtype=np.int16)

    max_val = np.max(np.abs(audio_data))
    rms = np.sqrt(np.mean(audio_data.astype(np.float64)**2))
    
    print("\n--- 1. Проверка уровня микрофона ---")
    print(f"Максимальная амплитуда: {max_val} / 32768 ({round(max_val/32768*100, 1)}%)")
    print(f"Средняя громкость (RMS): {round(rms, 1)}")
    
    if max_val < 500:
        print("⚠️ ВНИМАНИЕ: Записана тишина. Проверьте микрофон.")
    else:
        print("✅ Сигнал отличный.")

    # 2. Проверка распознавания через Faster-Whisper
    print("\n--- 2. Что услышал Faster-Whisper (CUDA / RTX 4060) ---")
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
        segments, info = model.transcribe(temp_wav, language="ru")
        recognized_text = " ".join([s.text for s in segments]).strip()
        print(f"Распознанный текст: «{recognized_text}» (уверенность: {round(info.language_probability*100, 1)}%)")
    except Exception as e:
        print(f"❌ Ошибка Whisper: {e}")

    # 3. Проверка русского детектора Vosk
    print("\n--- 3. Тест русского Wake Word детектора (Vosk) ---")
    try:
        import vosk
        vosk.SetLogLevel(-1)
        vosk_dir = "/home/armen/.local/share/vosk/vosk-model-small-ru-0.22"
        v_model = vosk.Model(vosk_dir)
        v_rec = vosk.KaldiRecognizer(v_model, 16000, '["моника", "[unk]"]')

        detected_vosk = False
        # Прогоняем чанками
        chunk = 4000
        for i in range(0, len(frames), chunk):
            data_part = frames[i:i+chunk]
            if v_rec.AcceptWaveform(data_part):
                res = json.loads(v_rec.Result())
                if "моника" in res.get("text", ""):
                    detected_vosk = True
                    break
            else:
                part = json.loads(v_rec.PartialResult())
                if "моника" in part.get("partial", ""):
                    detected_vosk = True
                    break

        if detected_vosk:
            print("🎯 РЕЗУЛЬТАТ VOSK: ✅ СРАБОТАЛ! Русское слово «Моника» распознано моментально!")
        else:
            final_res = json.loads(v_rec.FinalResult())
            if "моника" in final_res.get("text", ""):
                print("🎯 РЕЗУЛЬТАТ VOSK: ✅ СРАБОТАЛ (в конце фразы)!")
            else:
                print("❌ Vosk не засёк слово «моника».")
    except Exception as e:
        print(f"❌ Ошибка Vosk: {e}")

    # 4. Проверка Sherpa KWS (для сравнения)
    print("\n--- 4. Для сравнения: Тест Sherpa KWS ---")
    try:
        import sherpa_onnx
        model_dir = Path("/home/armen/.local/share/sherpa-onnx/models/kws/zipformer")
        tokens_path = model_dir / "tokens.txt"
        bpe_path = model_dir / "bpe.model"
        
        phrases = ["MONIKA", "MONICA", "MANIKA"]
        tokens = sherpa_onnx.text2token(phrases, tokens=str(tokens_path), tokens_type="bpe", bpe_model=str(bpe_path))
        
        kw_file = "/tmp/test_kws_keywords.txt"
        with open(kw_file, "w", encoding="utf-8") as f:
            for p, toks in zip(phrases, tokens):
                f.write(" ".join(toks) + f" @{p}\n")

        audio_samples = audio_data.astype(np.float32) / 32768.0

        spotter = sherpa_onnx.KeywordSpotter(
            tokens=str(tokens_path),
            encoder=str(model_dir / "encoder-epoch-12-avg-2-chunk-16-left-64.onnx"),
            decoder=str(model_dir / "decoder-epoch-12-avg-2-chunk-16-left-64.onnx"),
            joiner=str(model_dir / "joiner-epoch-12-avg-2-chunk-16-left-64.onnx"),
            keywords_file=kw_file,
            keywords_threshold=0.25,
            num_threads=1
        )
        stream = spotter.create_stream()
        stream.accept_waveform(16000, audio_samples)
        
        triggered_kw = None
        while spotter.is_ready(stream):
            spotter.decode_stream(stream)
            res = spotter.get_result(stream)
            if res:
                triggered_kw = res
                break

        if triggered_kw:
            print(f"  Sherpa (порог 0.25): 🎯 Сработал ({triggered_kw})")
        else:
            print("  Sherpa (порог 0.25): ❌ Не сработал (требует американский акцент)")

        if os.path.exists(kw_file):
            os.remove(kw_file)
    except Exception as e:
        print(f"❌ Ошибка Sherpa: {e}")

    print("\n" + "=" * 65)


if __name__ == "__main__":
    main()
