"""
Модуль аудиоввода (Уши).
Интеграция с Faster-Whisper (CUDA) и потоковым распознаванием речи через Silero VAD v6.
"""

import ctypes
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import numpy as np

# 1. Автоподгрузка CUDA-библиотек (libcublas.so.12, libcublasLt.so.12, libnvrtc.so)
def _preload_cuda_libs():
    search_dirs = [
        "/home/armen/.local/share/hyprwhspr/venv/lib/python3.14/site-packages/nvidia/cublas/lib",
        "/home/armen/.local/share/hyprwhspr/venv/lib/python3.14/site-packages/nvidia/cudnn/lib",
        "/home/armen/.local/share/hyprwhspr/venv/lib/python3.14/site-packages/nvidia/cuda_nvrtc/lib",
        "/usr/local/lib/ollama/cuda_v12",
        "/opt/cuda/lib64"
    ]
    libs_to_load = [
        "libcublasLt.so.12",
        "libcublas.so.12",
        "libnvrtc.so.12",
        "libcudnn.so.8",
        "libcudnn.so.9"
    ]
    for d in search_dirs:
        if os.path.isdir(d):
            for lib in libs_to_load:
                p = os.path.join(d, lib)
                if os.path.exists(p):
                    try:
                        ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)
                    except Exception:
                        pass

_preload_cuda_libs()

# 2. Патч совместимости для PyAV 19+ и Python 3.14 (устраняет ошибку metadata_errors в faster_whisper)
try:
    import av
    _orig_av_open = av.open

    def _patched_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _patched_av_open
except Exception:
    pass


class Ears:
    def __init__(self, config: dict, display=None):
        self.config = config
        self.stt_cfg = config.get("stt", {})
        self.enabled = self.stt_cfg.get("enabled", True)
        self.model_name = self.stt_cfg.get("model", "large-v3-turbo")
        self.device = self.stt_cfg.get("device", "cuda")
        self.compute_type = self.stt_cfg.get("compute_type", "float16")
        self.language = self.stt_cfg.get("language", "ru")
        self.display = display
        
        # Параметры VAD
        vad_cfg = config.get("vad", {})
        self.vad_threshold = float(vad_cfg.get("threshold", 0.50))
        self.silence_limit_sec = float(vad_cfg.get("silence_limit_sec", 1.0))
        
        self._whisper_model = None
        self._vad_model = None

    def _get_model(self):
        """Ленивая инициализация модели faster-whisper с fallback на CPU при ошибках CUDA."""
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            
            # Попытка инициализации на CUDA
            if self.device == "cuda":
                try:
                    if self.display:
                        self.display.log(f"Загрузка модели Faster-Whisper '{self.model_name}' на {self.device}...", tag="INFO")
                    self._whisper_model = WhisperModel(
                        self.model_name,
                        device="cuda",
                        compute_type=self.compute_type
                    )
                    if self.display:
                        self.display.log("Модель Whisper успешно инициализирована на GPU (CUDA)", tag="SUCCESS")
                    return self._whisper_model
                except Exception as e:
                    if self.display:
                        self.display.log(f"Не удалось запустить Whisper на CUDA ({e}). Переключаюсь на CPU...", tag="WARN")
                    self.device = "cpu"
                    self.compute_type = "int8"

            # Инициализация на CPU (fallback)
            if self.display:
                self.display.log(f"Загрузка модели Faster-Whisper '{self.model_name}' на CPU...", tag="INFO")
            self._whisper_model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8"
            )
            if self.display:
                self.display.log("Модель Whisper успешно инициализирована на CPU", tag="SUCCESS")

        return self._whisper_model

    def _get_vad_model(self):
        """Инициализация нейросетевого детектора голоса Silero VAD v6."""
        if self._vad_model is None:
            import faster_whisper
            from faster_whisper.vad import SileroVADModel
            vad_path = os.path.join(os.path.dirname(faster_whisper.__file__), "assets", "silero_vad_v6.onnx")
            self._vad_model = SileroVADModel(vad_path)
        return self._vad_model

    def transcribe_array(self, audio_array: np.ndarray) -> str:
        """Распознает речь напрямую из numpy-массива в оперативной памяти (без записи на диск)."""
        if len(audio_array) == 0:
            return ""

        model = self._get_model()
        segments, _ = model.transcribe(
            audio_array,
            language=self.language,
            beam_size=5,
            vad_filter=False  # Аудио уже отфильтровано нашим потоковым VAD
        )
        text = " ".join([seg.text for seg in segments]).strip()
        return text

    def transcribe_file(self, audio_path: str) -> str:
        """Распознает речь из аудиофайла."""
        if not os.path.exists(audio_path):
            return ""

        model = self._get_model()
        segments, _ = model.transcribe(
            audio_path,
            language=self.language,
            beam_size=5,
            vad_filter=True
        )
        text = " ".join([seg.text for seg in segments]).strip()
        return text

    def record_and_transcribe(self, duration_sec: int = 4) -> str:
        """Записывает звук с микрофона фиксированное время и транскрибирует его."""
        recorder = shutil.which("arecord") or shutil.which("pw-record")
        if not recorder:
            if self.display:
                self.display.log("Утилита записи звука (arecord / pw-record) не найдена", tag="ERROR")
            return ""

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            if self.display:
                self.display.log(f"Слушаю {duration_sec} сек...", tag="INFO")
            
            if "arecord" in recorder:
                cmd = ["arecord", "-D", "default", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(duration_sec), tmp_path]
            else:
                cmd = ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", tmp_path]

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            text = self.transcribe_file(tmp_path)
            return text
        except Exception as e:
            if self.display:
                self.display.log(f"Ошибка записи/распознавания: {e}", tag="ERROR")
            return ""
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @staticmethod
    def _flush_pipe(pipe):
        """Очищает накопленные в пайпе байты микрофона, предотвращая попадание звука динамиков."""
        import fcntl, os
        try:
            fd = pipe.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            try:
                while True:
                    data = os.read(fd, 8192)
                    if not data:
                        break
            except BlockingIOError:
                pass
            finally:
                fcntl.fcntl(fd, fcntl.F_SETFL, fl)
        except Exception:
            pass

    def listen_vad_stream(self, on_phrase_callback, is_muted_func=None):
        """
        Непрерывный бесшовный слушатель микрофона с детекцией речи Silero VAD.
        Вызывает on_phrase_callback(text) сразу при окончании фразы.
        is_muted_func: функция-флаг (возвращает True, пока ассистент говорит сам).
        """
        recorder = shutil.which("arecord") or shutil.which("pw-record")
        if not recorder:
            if self.display:
                self.display.log("Утилита arecord/pw-record не найдена", tag="ERROR")
            return

        vad = self._get_vad_model()
        # Предзагружаем модель Whisper перед входом в цикл
        self._get_model()

        # Поток PCM 16000 Гц, 16 бит моно
        if "arecord" in recorder:
            cmd = ["arecord", "-D", "default", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw", "-q"]
        else:
            cmd = ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", "-"]

        frame_samples = 512
        frame_bytes = frame_samples * 2  # 1024 байта (32 мс)

        # Буфер перед началом фразы (~250 мс, 8 фреймов), чтобы не съедался первый звук
        max_pre_frames = 8
        pre_buffer = []

        speaking = False
        phrase_frames = []
        silence_counter = 0
        silence_limit_frames = int(self.silence_limit_sec / 0.032)
        max_phrase_frames = int(15.0 / 0.032)  # Максимум 15 секунд непрерывной фразы

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        try:
            while True:
                # Если ассистент сейчас говорит через динамики — сбрасываем и очищаем очередь
                if is_muted_func and is_muted_func():
                    self._flush_pipe(proc.stdout)
                    speaking = False
                    phrase_frames.clear()
                    pre_buffer.clear()
                    silence_counter = 0
                    continue

                raw_bytes = proc.stdout.read(frame_bytes)
                if not raw_bytes or len(raw_bytes) < frame_bytes:
                    break

                chunk_samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                prob = float(vad(chunk_samples)[0])

                if not speaking:
                    pre_buffer.append(chunk_samples)
                    if len(pre_buffer) > max_pre_frames:
                        pre_buffer.pop(0)

                    if prob >= self.vad_threshold:
                        speaking = True
                        phrase_frames = list(pre_buffer)
                        phrase_frames.append(chunk_samples)
                        silence_counter = 0
                else:
                    phrase_frames.append(chunk_samples)
                    force_end = len(phrase_frames) >= max_phrase_frames

                    if prob < 0.35 or force_end:
                        silence_counter += 1
                        if silence_counter >= silence_limit_frames or force_end:
                            # Фраза завершилась!
                            full_audio = np.concatenate(phrase_frames)
                            speaking = False
                            phrase_frames.clear()
                            pre_buffer.clear()
                            silence_counter = 0

                            # Игнорируем слишком короткие случайные звуки (< 0.4 сек)
                            if len(full_audio) >= 16000 * 0.4:
                                text = self.transcribe_array(full_audio)
                                if text:
                                    try:
                                        on_phrase_callback(text)
                                    except Exception as e:
                                        if self.display:
                                            self.display.log(f"Ошибка обработки команды: {e}", tag="ERROR")
                                    # Очищаем буфер после ответа ассистента
                                    self._flush_pipe(proc.stdout)
                                    pre_buffer.clear()
                                    phrase_frames.clear()
                                    speaking = False
                                    silence_counter = 0
                    else:
                        silence_counter = 0

        except KeyboardInterrupt:
            raise
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                proc.kill()
