"""
Модуль детекции ключевого слова (Wake Word) на базе Vosk (нативный русский) или Sherpa-ONNX.
Обеспечивает непрерывное фоновое прослушивание с минимальной нагрузкой на процессор (<0.5% CPU).
"""

import json
import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
import numpy as np

# Подключаем sherpa-onnx, если потребуется в режиме fallback
try:
    import sherpa_onnx
except ImportError:
    extra_path = "/home/armen/.hermes/tools/python-3.14.7+20260901-linux-x64/lib/python3.14/site-packages"
    if extra_path not in sys.path and os.path.exists(extra_path):
        sys.path.insert(0, extra_path)
    try:
        import sherpa_onnx
    except Exception:
        sherpa_onnx = None


class WakeWordDetector:
    def __init__(self, config: dict, display=None):
        self.config = config
        self.display = display
        wake_cfg = config.get("wake_word", {})
        
        self.enabled = wake_cfg.get("enabled", True)
        self.engine_type = wake_cfg.get("engine", "vosk").lower()
        self.phrase = wake_cfg.get("phrase", "моника").lower()
        self.phrases = wake_cfg.get("phrases", ["MONIKA", "MONICA"])
        self.threshold = float(wake_cfg.get("threshold", 0.25))
        
        # Модели
        self.vosk_model_dir = Path(wake_cfg.get("vosk_model_dir", "/home/armen/.local/share/vosk/vosk-model-small-ru-0.22"))
        self.sherpa_model_dir = Path(wake_cfg.get("sherpa_model_dir", "/home/armen/.local/share/sherpa-onnx/models/kws/zipformer"))
        
        self.vosk_recognizer = None
        self.sherpa_spotter = None
        self._sherpa_keywords_file = None

        if self.enabled:
            self._init_detector()

    def _init_detector(self):
        """Инициализация выбранного детектора ключевых слов."""
        if self.engine_type == "vosk":
            self._init_vosk()
            if not self.vosk_recognizer:
                # Если Vosk не смог запуститься, пробуем Sherpa
                if self.display:
                    self.display.log("Переключаюсь на Sherpa KWS...", tag="WARN")
                self.engine_type = "sherpa"
                self._init_sherpa()
        else:
            self._init_sherpa()

    def _init_vosk(self):
        """Инициализация русской модели Vosk с грамматикой ключевого слова."""
        try:
            import vosk
            vosk.SetLogLevel(-1)  # Отключаем технический шум в логах
            
            if not self.vosk_model_dir.exists():
                if self.display:
                    self.display.log(f"Каталог модели Vosk не найден: {self.vosk_model_dir}", tag="WARN")
                return

            model = vosk.Model(str(self.vosk_model_dir))
            # Грамматика задает только нужное ключевое слово + [unk] для всего остального шума
            grammar = json.dumps([self.phrase, "[unk]"], ensure_ascii=False)
            self.vosk_recognizer = vosk.KaldiRecognizer(model, 16000, grammar)
            self.vosk_recognizer.SetWords(True)  # Включаем расчет уверенности (confidence) для каждого слова
            
            if self.display:
                self.display.log(f"Русский детектор Wake Word (Vosk) активирован (имя: '{self.phrase}')", tag="SUCCESS")
        except Exception as e:
            if self.display:
                self.display.log(f"Ошибка инициализации Vosk: {e}", tag="ERROR")

    def _init_sherpa(self):
        """Инициализация Sherpa-ONNX KeywordSpotter."""
        if not sherpa_onnx or not self.sherpa_model_dir.exists():
            return

        tokens_path = self.sherpa_model_dir / "tokens.txt"
        bpe_path = self.sherpa_model_dir / "bpe.model"
        encoder_path = self.sherpa_model_dir / "encoder-epoch-12-avg-2-chunk-16-left-64.onnx"
        decoder_path = self.sherpa_model_dir / "decoder-epoch-12-avg-2-chunk-16-left-64.onnx"
        joiner_path = self.sherpa_model_dir / "joiner-epoch-12-avg-2-chunk-16-left-64.onnx"

        try:
            tokens = sherpa_onnx.text2token(
                self.phrases,
                tokens=str(tokens_path),
                tokens_type="bpe",
                bpe_model=str(bpe_path)
            )

            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="monika_kws_", delete=False) as f:
                for p, toks in zip(self.phrases, tokens):
                    f.write(" ".join(toks) + f" @{p}\n")
                self._sherpa_keywords_file = f.name

            self.sherpa_spotter = sherpa_onnx.KeywordSpotter(
                tokens=str(tokens_path),
                encoder=str(encoder_path),
                decoder=str(decoder_path),
                joiner=str(joiner_path),
                keywords_file=self._sherpa_keywords_file,
                keywords_threshold=self.threshold,
                num_threads=1
            )
            if self.display:
                self.display.log(f"Sherpa KWS инициализирована (триггеры: {', '.join(self.phrases)})", tag="SUCCESS")
        except Exception as e:
            if self.display:
                self.display.log(f"Ошибка инициализации Sherpa: {e}", tag="ERROR")

    @property
    def ready(self) -> bool:
        return (self.vosk_recognizer is not None) or (self.sherpa_spotter is not None)

    @property
    def spotter(self):
        """Алиас для обратной совместимости."""
        return self.vosk_recognizer or self.sherpa_spotter

    def wait_for_wake_word(self) -> bool:
        """
        Блокирующий метод: непрерывно слушает аудиопоток до обнаружения фразы пробуждения.
        Возвращает True при успешном распознавании.
        """
        if not self.ready:
            return False

        recorder = shutil.which("arecord") or shutil.which("pw-record")
        if not recorder:
            if self.display:
                self.display.log("Утилита arecord/pw-record не найдена для прослушивания", tag="ERROR")
            return False

        # 16-бит, 16000Гц, 1 канал (сырой поток PCM)
        if "arecord" in recorder:
            cmd = ["arecord", "-D", "default", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw", "-q"]
        else:
            cmd = ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", "-"]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        try:
            if self.engine_type == "vosk" and self.vosk_recognizer:
                # Чанки по 4000 байт (0.125 сек)
                chunk_bytes = 4000
                while True:
                    raw_bytes = proc.stdout.read(chunk_bytes)
                    if not raw_bytes or len(raw_bytes) < chunk_bytes:
                        break

                    if self.vosk_recognizer.AcceptWaveform(raw_bytes):
                        res = json.loads(self.vosk_recognizer.Result())
                        # Проверяем подтвержденные слова и уверенность распознавания
                        words = res.get("result", [])
                        for w in words:
                            if w.get("word") == self.phrase and w.get("conf", 0.0) >= 0.85:
                                conf_pct = round(w.get("conf", 1.0) * 100, 1)
                                if self.display:
                                    self.display.log(f"Услышано имя: '{self.phrase}' (Vosk, уверенность {conf_pct}%)", tag="AGENT")
                                return True

            elif self.sherpa_spotter:
                chunk_size = 1280
                bytes_to_read = chunk_size * 2
                stream = self.sherpa_spotter.create_stream()

                while True:
                    raw_bytes = proc.stdout.read(bytes_to_read)
                    if not raw_bytes or len(raw_bytes) < bytes_to_read:
                        break

                    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    stream.accept_waveform(16000, samples)

                    while self.sherpa_spotter.is_ready(stream):
                        self.sherpa_spotter.decode_stream(stream)
                        result = self.sherpa_spotter.get_result(stream)
                        if result:
                            if self.display:
                                self.display.log(f"Услышано имя: '{result}' (Sherpa)", tag="AGENT")
                            return True

        except KeyboardInterrupt:
            raise
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                proc.kill()

        return False

    def __del__(self):
        if self._sherpa_keywords_file and os.path.exists(self._sherpa_keywords_file):
            try:
                os.unlink(self._sherpa_keywords_file)
            except Exception:
                pass
