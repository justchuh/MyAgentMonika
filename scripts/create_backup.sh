#!/usr/bin/env bash
# ==============================================================================
# Скрипт создания полного архива системы для переноса на ноутбук (Omarchy)
# ==============================================================================

set -e

BACKUP_DIR="${1:-$HOME}"
ARCHIVE_NAME="omarchy_laptop_full_backup.tar.gz"
DEST_PATH="$BACKUP_DIR/$ARCHIVE_NAME"

echo "==================================================================="
echo "   СОЗДАНИЕ ПОЛНОГО РЕЗЕРВНОГО АРХИВА ДЛЯ НОУТБУКА"
echo "==================================================================="
echo "В архив включаются:"
echo " - Все Documents (включая 'с_пк' 12 ГБ, конспекты Obsidian, код, курсы)"
echo " - Все видеофайлы (~/Videos 3.2 ГБ)"
echo " - Игры (~/.minecraft и ~/.tlauncher 1.1 ГБ)"
echo " - Все конфиги системы ~/.config (Hyprland, Omarchy, Antigravity, Code, Obsidian)"
echo " - Antigravity Unlocker и службы (~/.local/share/agunlocker)"
echo " - Модели речи (~/.local/share/vosk), Telegram сессии"
echo " - Проекты: my_custom_agent и zapret-discord-youtube-linux"
echo " - Установочный скрипт setup_laptop.sh"
echo ""
echo "Исключается только системный мусор:"
echo " - ~/.cache (временный кэш)"
echo " - ~/.local/share/Trash (корзина)"
echo " - Replay (кэш видеозаписей)"
echo " - Тяжелые библиотеки NVIDIA CUDA (~10 ГБ) — на ноутбуке установится CPU-версия"
echo "==================================================================="
echo "Упаковка может занять 2-4 минуты..."

cd "$HOME"

tar -czvf "$DEST_PATH" \
    --exclude='.cache' \
    --exclude='.local/share/Trash' \
    --exclude='.local/share/my_custom_agent' \
    --exclude='.local/share/tts' \
    --exclude='.config/Replay' \
    --exclude='armen' \
    --exclude='.hermes' \
    --exclude='*Cache*' \
    --exclude='__pycache__' \
    .config \
    .local/bin \
    .local/lib \
    .local/share/agunlocker \
    .local/share/vosk \
    .local/share/TelegramDesktop \
    .minecraft \
    .tlauncher \
    .gemini \
    .ssh \
    .gitconfig \
    .bashrc \
    Documents \
    Pictures \
    Wallpapers \
    Videos \
    my_custom_agent \
    zapret-discord-youtube-linux \
    setup_laptop.sh

echo ""
echo "==================================================================="
echo "   АРХИВ УСПЕШНО СОЗДАН!"
echo "==================================================================="
ls -lh "$DEST_PATH"
echo ""
echo "Что делать дальше:"
echo "1. Скопируйте файл '$ARCHIVE_NAME' и 'setup_laptop.sh' на флешку."
echo "2. На ноутбуке вставьте флешку и запустите:"
echo "   bash setup_laptop.sh"
echo "==================================================================="
