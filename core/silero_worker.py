"""
Фоновый постоянный воркер Silero TTS.
Работает в изолированном Python окружении с PyTorch.
Получает JSON-запросы на синтез через stdin, генерирует WAV и возвращает статус через stdout.
"""

import json
import os
import re
import sys
import time
import torch

try:
    import num2words
except ImportError:
    num2words = None


def normalize_text_for_speech(text: str) -> str:
    """
    Преобразует арабские цифры, проценты и спецсимволы в слова на русском языке,
    так как Silero TTS v4 не озвучивает сырые цифры 0-9.
    """
    if not text:
        return ""

    # 1. Замена спецсимволов и валют
    text = re.sub(r'(\d+)\s*%', r'\1 процентов', text)
    text = re.sub(r'(\d+)\s*\$', r'\1 долларов', text)
    text = re.sub(r'(\d+)\s*€', r'\1 евро', text)
    text = re.sub(r'(\d+)\s*₽', r'\1 рублей', text)

    if not num2words:
        return text

    # 2. Время вида 14:05 -> 14 часов 5 минут
    def replace_time(m):
        h = int(m.group(1))
        mn = int(m.group(2))
        try:
            h_word = num2words.num2words(h, lang="ru")
            mn_word = num2words.num2words(mn, lang="ru")
            return f"{h_word} часов {mn_word} минут"
        except Exception:
            return m.group(0)

    text = re.sub(r'\b(\d{1,2}):(\d{2})\b', replace_time, text)

    # 3. Числа с плавающей точкой и целые числа
    def replace_num(match):
        s = match.group(0).replace(',', '.').replace(' ', '')
        try:
            if '.' in s:
                parts = s.split('.')
                i_val = int(parts[0])
                d_val = int(parts[1])
                i_word = num2words.num2words(i_val, lang="ru")
                d_word = num2words.num2words(d_val, lang="ru")
                return f"{i_word} и {d_word}"
            else:
                val = int(s)
                return num2words.num2words(val, lang="ru")
        except Exception:
            return match.group(0)

    text = re.sub(r'\b\d+(?:[\.,]\d+)?\b', replace_num, text)
    return text


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "v4_ru"
    device_name = sys.argv[2] if len(sys.argv) > 2 else "cpu"
    device = torch.device(device_name)

    try:
        # 1. Загрузка модели Silero
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language="ru",
            speaker=model_name
        )
        model.to(device)

        # 2. Прогрев JIT и звукового энкодера
        warmup_path = "/tmp/silero_warmup.wav"
        try:
            model.save_wav(text="Тест.", speaker="baya", sample_rate=48000, audio_path=warmup_path)
            if os.path.exists(warmup_path):
                os.remove(warmup_path)
        except Exception:
            pass

        # Сообщаем родительскому процессу о готовности
        ready_payload = {
            "status": "ready",
            "model": model_name,
            "device": str(device),
            "speakers": getattr(model, "speakers", [])
        }
        print(json.dumps(ready_payload), flush=True)

    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Init error: {e}"}), flush=True)
        sys.exit(1)

    # 3. Цикл обработки запросов на синтез
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
            action = req.get("action", "speak")

            if action == "exit":
                break

            text = req.get("text", "")
            speaker = req.get("speaker", "baya")
            sample_rate = int(req.get("sample_rate", 48000))
            audio_path = req.get("output_path", "")

            if not text or not audio_path:
                print(json.dumps({"status": "error", "message": "Missing text or output_path"}), flush=True)
                continue

            # Обеспечиваем наличие целевой папки
            os.makedirs(os.path.dirname(os.path.abspath(audio_path)), exist_ok=True)

            # Нормализация чисел и спецсимволов для чистой русской речи
            speech_text = normalize_text_for_speech(text)

            t0 = time.time()
            model.save_wav(
                text=speech_text,
                speaker=speaker,
                sample_rate=sample_rate,
                audio_path=audio_path,
                put_accent=True,
                put_yo=True
            )
            elapsed = time.time() - t0

            print(json.dumps({"status": "ok", "path": audio_path, "elapsed": round(elapsed, 4)}), flush=True)

        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}), flush=True)


if __name__ == "__main__":
    main()
