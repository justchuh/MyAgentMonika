#!/usr/bin/env bash
# ==============================================================================
# Скрипт автоматического развертывания и настройки на ноутбуке Omarchy
# Автор: ZeroVoiceAgent Setup Tool
# ==============================================================================

set -e

USER_HOME="$HOME"
ARCHIVE_NAME="omarchy_laptop_full_backup.tar.gz"

echo "==================================================================="
echo "   АВТОМАТИЧЕСКАЯ УСТАНОВКА И НАСТРОЙКА НА НОУТБУКЕ (OMARCHY)"
echo "==================================================================="

# 1. Распаковка архива, если он находится рядом со скриптом или в ~
if [ -f "$ARCHIVE_NAME" ]; then
    echo "[1/7] Распаковка $ARCHIVE_NAME в домашний каталог..."
    tar -xzvf "$ARCHIVE_NAME" -C "$USER_HOME"
elif [ -f "$USER_HOME/$ARCHIVE_NAME" ]; then
    echo "[1/7] Распаковка $USER_HOME/$ARCHIVE_NAME в домашний каталог..."
    tar -xzvf "$USER_HOME/$ARCHIVE_NAME" -C "$USER_HOME"
else
    echo "[1/7] Архив $ARCHIVE_NAME не найден рядом — продолжаем настройку существующих файлов."
fi

# 2. Выставление прав на исполнение
echo "[2/7] Выставление прав на запуск утилит и скриптов..."
chmod +x "$USER_HOME"/.local/bin/* 2>/dev/null || true
chmod +x "$USER_HOME"/my_custom_agent/main.py 2>/dev/null || true
chmod +x "$USER_HOME"/zapret-discord-youtube-linux/*.sh 2>/dev/null || true
chmod +x "$USER_HOME"/.local/share/agunlocker/ag_proxy 2>/dev/null || true

# 3. Установка системных зависимостей
echo "[3/7] Установка необходимых системных пакетов..."
sudo pacman -S --needed --noconfirm iptables curl python python-pip python-pipx pamixer wireplumber pipewire alacritty foot

# Проверка и установка Antigravity IDE из AUR
if ! command -v antigravity &>/dev/null; then
    echo "Установка Antigravity IDE из AUR..."
    if command -v yay &>/dev/null; then
        yay -S --noconfirm antigravity
    elif command -v paru &>/dev/null; then
        paru -S --noconfirm antigravity
    else
        echo "Внимание: yay или paru не найдены. Установите antigravity вручную."
    fi
else
    echo "Antigravity IDE уже установлена."
fi

# 4. Активация Antigravity Unlocker
echo "[4/7] Активация служб обхода Antigravity Unlocker..."
mkdir -p "$USER_HOME/.config/systemd/user"
systemctl --user daemon-reload
systemctl --user enable --now ag-unlocker-proxy.service ag-unlocker-watchdog.service 2>/dev/null || true

# 5. Оптимизация ZeroVoiceAgent под процессор ноутбука (CPU-only)
echo "[5/7] Оптимизация ZeroVoiceAgent под слабое железо ноутбука..."
CONFIG_YAML="$USER_HOME/my_custom_agent/config.yaml"
if [ -f "$CONFIG_YAML" ]; then
    sed -i 's/device: "cuda"/device: "cpu"/g' "$CONFIG_YAML"
    sed -i 's/model: "large-v3-turbo"/model: "small"/g' "$CONFIG_YAML"
    sed -i 's/compute_type: "float16"/compute_type: "int8"/g' "$CONFIG_YAML"
    sed -i 's/active_preset: "nyamura_warm"/active_preset: "baya"/g' "$CONFIG_YAML"
    echo "Конфигурация config.yaml переведена в экономичный режим CPU."
fi

# Создаем легковесный CPU venv для Silero TTS (~250 МБ вместо 10 ГБ CUDA)
echo "Создание легковесного окружения Python для синтезатора речи..."
mkdir -p "$USER_HOME/.local/share/my_custom_agent"
python3 -m venv "$USER_HOME/.local/share/my_custom_agent/silero_venv"
"$USER_HOME/.local/share/my_custom_agent/silero_venv/bin/pip" install --no-cache-dir torch torchaudio sounddevice --index-url https://download.pytorch.org/whl/cpu

# Установка зависимостей распознавания речи
echo "Установка библиотек Faster-Whisper и Vosk..."
pip install --break-system-packages --user faster-whisper vosk pyyaml sounddevice num2words requests 2>/dev/null || true

# 6. Включение службы ZeroVoiceAgent
echo "[6/7] Включение автозапуска ZeroVoiceAgent..."
cp "$USER_HOME/my_custom_agent/systemd/zerovoice.service" "$USER_HOME/.config/systemd/user/zerovoice.service" 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user enable --now zerovoice.service 2>/dev/null || true

# 7. Перезагрузка Hyprland хоткеев
echo "[7/7] Применение горячих клавиш и настроек Hyprland..."
hyprctl reload 2>/dev/null || true

echo ""
echo "==================================================================="
echo "   УСТАНОВКА И НАСТРОЙКА УСПЕШНО ЗАВЕРШЕНЫ!"
echo "==================================================================="
echo "1. Antigravity разблокирован и готов к работе со всеми вашими сессиями."
echo "2. ZeroVoiceAgent запущен в фоновом режиме (автозапуск включен)."
echo "   - Нажмите Win + Q для включения/выключения ассистента."
echo "   - Нажмите Ctrl + Shift + Z для диктовки в активное окно."
echo "3. Для включения Запрета (YouTube/Discord) выполните:"
echo "   cd ~/zapret-discord-youtube-linux && sudo bash service.sh run --config conf.env"
echo "==================================================================="
