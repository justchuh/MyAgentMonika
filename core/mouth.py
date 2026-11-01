"""
Модуль речевого вывода (TTS) на базе связки Silero TTS v4 + RVC v2/v1.
Обеспечивает естественный синтез русской речи с мгновенным RVC-преобразованием на GPU
и кэшированием фраз для нулевой задержки (0 мс) воспроизведения.
"""

import atexit
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path


class Speaker:
    def __init__(self, config: dict, display=None):
        self.tts_cfg = config.get("tts", {})
        self.enabled = self.tts_cfg.get("enabled", True)
        self.engine = self.tts_cfg.get("engine", "silero")
        self.speaker = self.tts_cfg.get("speaker", "baya")
        self.model_name = self.tts_cfg.get("model", "v4_ru")
        self.sample_rate = int(self.tts_cfg.get("sample_rate", 48000))
        self.device = self.tts_cfg.get("device", "cpu")
        self.speed = float(self.tts_cfg.get("speed", 1.0))
        self.cache_enabled = self.tts_cfg.get("cache_audio", True)
        self.display = display
        self.is_speaking = False

        # Определение активного пресета голоса
        self.active_preset = self.tts_cfg.get("active_preset", "nyamura_warm")
        self.presets = self.tts_cfg.get("presets", {})
        preset_cfg = self.presets.get(self.active_preset, {})

        # Базовый спикер Silero
        self.speaker = preset_cfg.get("speaker", self.tts_cfg.get("speaker", "baya"))

        # Параметры RVC для выбранного пресета
        self.rvc_cfg = preset_cfg.get("rvc", self.tts_cfg.get("rvc", {}))
        self.rvc_enabled = self.rvc_cfg.get("enabled", False)
        self.rvc_voice = self.active_preset
        self.rvc_model_path = self.rvc_cfg.get("model_path", "")
        self.rvc_index_path = self.rvc_cfg.get("index_path", "")
        self.rvc_version = self.rvc_cfg.get("version", "v1")
        self.rvc_index_rate = float(self.rvc_cfg.get("index_rate", 0.32))
        self.rvc_filter_radius = int(self.rvc_cfg.get("filter_radius", 7))
        self.rvc_rms_mix_rate = float(self.rvc_cfg.get("rms_mix_rate", 0.30))
        self.rvc_protect = float(self.rvc_cfg.get("protect", 0.50))
        self.rvc_f0up_key = int(self.rvc_cfg.get("f0up_key", 0))
        self.rvc_f0method = self.rvc_cfg.get("f0method", "rmvpe")
        self.rvc_python_bin = self.rvc_cfg.get(
            "python_bin",
            "/home/armen/.local/share/my_custom_agent/rvc_venv/bin/python"
        )
        self.rvc_worker_script = Path(__file__).parent / "rvc_worker.py"

        cache_dir = self.tts_cfg.get("cache_dir", "~/.cache/my_custom_agent/audio")
        self.cache_dir = Path(os.path.expanduser(cache_dir))
        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Путь к изолированному интерпретатору с PyTorch для Silero
        self.python_bin = self.tts_cfg.get(
            "python_bin",
            "/home/armen/.local/share/my_custom_agent/silero_venv/bin/python"
        )
        self.worker_script = Path(__file__).parent / "silero_worker.py"

        self._lock = threading.Lock()
        self._worker_proc = None
        self._rvc_proc = None
        self._check_audio_player()

        if self.enabled:
            self._start_workers()
            atexit.register(self.close)

    def _check_audio_player(self):
        """Определяет утилиту воспроизведения аудио в системе (pw-play или aplay)."""
        self.player = shutil.which("pw-play") or shutil.which("aplay") or shutil.which("paplay")

    def _start_workers(self):
        """Запускает постоянные фоновые воркеры Silero TTS и RVC."""
        self._start_silero_worker()
        if self.rvc_enabled:
            self._start_rvc_worker()

    def _start_silero_worker(self):
        """Запускает постоянный процесс worker'а Silero TTS."""
        if not os.path.exists(self.python_bin):
            if self.display:
                self.display.log(f"Интерпретатор Silero TTS не найден: {self.python_bin}", tag="ERROR")
            return

        try:
            cmd = [
                self.python_bin,
                str(self.worker_script),
                self.model_name,
                self.device
            ]
            self._worker_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            ready_line = self._worker_proc.stdout.readline()
            if ready_line:
                data = json.loads(ready_line)
                if data.get("status") == "ready":
                    if self.display:
                        self.display.log(
                            f"Silero TTS активен (база: '{self.speaker}', {self.model_name}, {self.sample_rate} Гц)",
                            tag="SUCCESS"
                        )
                    return

            if self.display:
                self.display.log("Не удалось подтвердить запуск Silero TTS воркера", tag="WARN")
        except Exception as e:
            if self.display:
                self.display.log(f"Ошибка запуска Silero TTS воркера: {e}", tag="ERROR")

    def _start_rvc_worker(self):
        """Запускает постоянный процесс RVC воркера на GPU."""
        if not os.path.exists(self.rvc_python_bin):
            if self.display:
                self.display.log(f"Интерпретатор RVC не найден: {self.rvc_python_bin}", tag="ERROR")
            return

        try:
            cmd = [
                self.rvc_python_bin,
                str(self.rvc_worker_script),
                self.rvc_model_path,
                self.rvc_index_path,
                self.rvc_version,
                "cuda:0"
            ]
            self._rvc_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )

            ready_line = self._rvc_proc.stdout.readline()
            if ready_line:
                data = json.loads(ready_line)
                if data.get("status") == "ready":
                    if self.display:
                        self.display.log(
                            f"RVC активен (голос: '{self.rvc_voice}', микс: {self.rvc_index_rate}, фильтр: {self.rvc_filter_radius})",
                            tag="SUCCESS"
                        )
                    return

            if self.display:
                self.display.log("Не удалось подтвердить запуск RVC воркера", tag="WARN")
        except Exception as e:
            if self.display:
                self.display.log(f"Ошибка запуска RVC воркера: {e}", tag="ERROR")

    def _ensure_workers(self):
        """Проверяет работоспособность воркеров и перезапускает их при сбое."""
        if self._worker_proc is None or self._worker_proc.poll() is not None:
            self._start_silero_worker()
        if self.rvc_enabled and (self._rvc_proc is None or self._rvc_proc.poll() is not None):
            self._start_rvc_worker()

    def _get_cache_path(self, text: str) -> Path:
        """Создает уникальный путь к файлу кэша с учётом активного пресета голоса."""
        key = f"{self.active_preset}_{self.sample_rate}_{text.strip().lower()}"
        file_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{file_hash}.wav"

    def set_preset(self, preset_name: str) -> bool:
        """Динамически переключает профиль голоса между избранными."""
        if preset_name not in self.presets:
            if self.display:
                self.display.log(f"Неизвестный пресет голоса: '{preset_name}'", tag="WARN")
            return False

        with self._lock:
            if self._rvc_proc and self._rvc_proc.poll() is None:
                try:
                    self._rvc_proc.stdin.write(json.dumps({"action": "exit"}) + "\n")
                    self._rvc_proc.stdin.flush()
                    self._rvc_proc.wait(timeout=1.0)
                except Exception:
                    pass
                self._rvc_proc = None

            self.active_preset = preset_name
            preset_cfg = self.presets[preset_name]
            self.speaker = preset_cfg.get("speaker", self.tts_cfg.get("speaker", "baya"))
            self.rvc_cfg = preset_cfg.get("rvc", {})
            self.rvc_enabled = self.rvc_cfg.get("enabled", False)
            self.rvc_voice = preset_name
            self.rvc_model_path = self.rvc_cfg.get("model_path", "")
            self.rvc_index_path = self.rvc_cfg.get("index_path", "")
            self.rvc_version = self.rvc_cfg.get("version", "v1")
            self.rvc_index_rate = float(self.rvc_cfg.get("index_rate", 0.32))
            self.rvc_filter_radius = int(self.rvc_cfg.get("filter_radius", 7))
            self.rvc_rms_mix_rate = float(self.rvc_cfg.get("rms_mix_rate", 0.30))
            self.rvc_protect = float(self.rvc_cfg.get("protect", 0.50))
            self.rvc_f0up_key = int(self.rvc_cfg.get("f0up_key", 0))
            self.rvc_f0method = self.rvc_cfg.get("f0method", "rmvpe")

            if self.rvc_enabled:
                self._start_rvc_worker()

            if self.display:
                self.display.log(f"Голос переключен на: '{preset_cfg.get('name', preset_name)}'", tag="SUCCESS")
            return True

    def speak(self, text: str, wait: bool = True):
        """Синтезирует и озвучивает переданный текст через связку Silero + RVC."""
        if not self.enabled or not text or not text.strip():
            return

        text = text.strip()
        cache_file = self._get_cache_path(text)

        # 1. Если фраза уже закэширована — мгновенный запуск звука (0 мс)
        if self.cache_enabled and cache_file.exists() and cache_file.stat().st_size > 0:
            self._play_wav(cache_file, wait=wait)
            return

        # 2. Иначе синтезируем
        target_wav = cache_file if self.cache_enabled else Path(f"/tmp/custom_voice_{time.time_ns()}.wav")
        base_wav = Path(f"/tmp/silero_base_{time.time_ns()}.wav") if self.rvc_enabled else target_wav

        with self._lock:
            self._ensure_workers()
            if not self._worker_proc or self._worker_proc.poll() is not None:
                if self.display:
                    self.display.log("Silero worker недоступен для синтеза", tag="ERROR")
                return

            try:
                # Шаг 1: Базовый синтез Silero
                req_silero = {
                    "action": "speak",
                    "text": text,
                    "speaker": self.speaker,
                    "sample_rate": self.sample_rate,
                    "output_path": str(base_wav)
                }
                self._worker_proc.stdin.write(json.dumps(req_silero) + "\n")
                self._worker_proc.stdin.flush()

                resp_line = self._worker_proc.stdout.readline()
                if not resp_line:
                    return

                res_silero = json.loads(resp_line)
                if res_silero.get("status") != "ok" or not base_wav.exists():
                    if self.display:
                        self.display.log(f"Ошибка Silero: {res_silero.get('message')}", tag="ERROR")
                    return

                # Шаг 2: Преобразование через RVC (если включено)
                if self.rvc_enabled:
                    if self._rvc_proc and self._rvc_proc.poll() is None:
                        req_rvc = {
                            "action": "convert",
                            "input_path": str(base_wav),
                            "output_path": str(target_wav),
                            "index_rate": self.rvc_index_rate,
                            "filter_radius": self.rvc_filter_radius,
                            "rms_mix_rate": self.rvc_rms_mix_rate,
                            "protect": self.rvc_protect,
                            "f0up_key": self.rvc_f0up_key,
                            "f0method": self.rvc_f0method
                        }
                        self._rvc_proc.stdin.write(json.dumps(req_rvc) + "\n")
                        self._rvc_proc.stdin.flush()

                        rvc_resp_line = self._rvc_proc.stdout.readline()
                        if rvc_resp_line:
                            res_rvc = json.loads(rvc_resp_line)
                            if res_rvc.get("status") != "ok":
                                if self.display:
                                    self.display.log(f"Ошибка RVC: {res_rvc.get('message')}", tag="ERROR")
                                # Fallback на базовый звук Silero
                                target_wav = base_wav
                    else:
                        target_wav = base_wav

                # Очистка временного промежуточного файла
                if self.rvc_enabled and base_wav != target_wav and base_wav.exists():
                    try:
                        base_wav.unlink()
                    except Exception:
                        pass

                # Шаг 3: Воспроизведение
                if target_wav.exists() and target_wav.stat().st_size > 0:
                    self._play_wav(target_wav, wait=wait)

            except Exception as e:
                if self.display:
                    self.display.log(f"Исключение при синтезе голоса: {e}", tag="ERROR")

    def _play_wav(self, wav_path: Path, wait: bool = True):
        """Воспроизводит аудиофайл через системный плеер с мьютексом активности речи."""
        if not self.player:
            if self.display:
                self.display.log("Плеер PipeWire (pw-play / aplay) не обнаружен", tag="WARN")
            return

        try:
            self.is_speaking = True
            if wait:
                subprocess.run(
                    [self.player, str(wav_path)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    [self.player, str(wav_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception as e:
            if self.display:
                self.display.log(f"Ошибка воспроизведения звука: {e}", tag="ERROR")
        finally:
            if wait:
                # Пауза 150мс для затухания комнатного эха, чтобы микрофон не подхватил хвост
                time.sleep(0.15)
                self.is_speaking = False

    def close(self):
        """Корректно останавливает фоновые воркеры."""
        if self._worker_proc and self._worker_proc.poll() is None:
            try:
                self._worker_proc.stdin.write(json.dumps({"action": "exit"}) + "\n")
                self._worker_proc.stdin.flush()
                self._worker_proc.wait(timeout=1.0)
            except Exception:
                try:
                    self._worker_proc.terminate()
                except Exception:
                    pass
            finally:
                self._worker_proc = None

        if self._rvc_proc and self._rvc_proc.poll() is None:
            try:
                self._rvc_proc.stdin.write(json.dumps({"action": "exit"}) + "\n")
                self._rvc_proc.stdin.flush()
                self._rvc_proc.wait(timeout=1.0)
            except Exception:
                try:
                    self._rvc_proc.terminate()
                except Exception:
                    pass
            finally:
                self._rvc_proc = None
