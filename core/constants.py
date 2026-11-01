"""
Системные константы и глобальные пути ZeroVoiceAgent.
Централизованное хранилище постоянных параметров системы.
"""

from pathlib import Path

# Базовые директории проекта
ROOT_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = ROOT_DIR / "core"
SKILLS_DIR = ROOT_DIR / "skills"
MODELS_DIR = ROOT_DIR / "models"

# Конфигурационные файлы
CONFIG_FILE = ROOT_DIR / "config.yaml"
CHARACTER_FILE = ROOT_DIR / "character.yaml"

# Домашняя директория и внешние утилиты
USER_HOME = Path.home()
DEFAULT_USER_NAME = "Армен"

ZAPRET_DIR = USER_HOME / "zapret-discord-youtube-linux"
ZAPRET_SCRIPT = ZAPRET_DIR / "service.sh"

# Кэширование аудио Silero / RVC
CACHE_BASE_DIR = USER_HOME / ".cache" / "my_custom_agent"
AUDIO_CACHE_DIR = CACHE_BASE_DIR / "audio"

# Служебные имена событий для реплик и эмоций (character.yaml / Live2D)
EVENT_ON_WAKE = "on_wake"
EVENT_ON_SUCCESS = "on_success"
EVENT_ON_ERROR = "on_error"
EVENT_ON_UNKNOWN = "on_unknown"

# Системные тайминги по умолчанию
DEFAULT_ACTIVE_WINDOW_SEC = 5.0
DEFAULT_VAD_THRESHOLD = 0.50
DEFAULT_SILENCE_LIMIT_SEC = 1.0
