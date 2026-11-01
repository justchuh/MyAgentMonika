"""
Модуль вывода информации:
- Консольный вывод с цветовой разметкой
- Всплывающие уведомления notify-send (Wayland/Hyprland)
- Передача эмоций в окно Waifuland (Live2D)
"""

import os
import socket
import subprocess
from pathlib import Path

class DisplayManager:
    def __init__(self, config: dict):
        self.output_cfg = config.get("output", {})
        self.console_enabled = self.output_cfg.get("console_logs", True)
        self.notifications_enabled = self.output_cfg.get("desktop_notifications", True)
        self.timeout_ms = self.output_cfg.get("notification_timeout_ms", 3000)
        self.app_name = self.output_cfg.get("notification_app_name", "Моника")
        
        self.waifuland_enabled = self.output_cfg.get("waifuland_bridge", False)
        self.waifuland_socket = self.output_cfg.get("waifuland_socket", "/tmp/waifuland.sock")

    def log(self, text: str, tag: str = "INFO"):
        """Печатает форматированное сообщение в консоль."""
        if not self.console_enabled:
            return
        
        colors = {
            "INFO": "\033[94m",     # Синий
            "SUCCESS": "\033[92m",  # Зеленый
            "WARN": "\033[93m",     # Желтый
            "ERROR": "\033[91m",    # Красный
            "AGENT": "\033[95m",    # Пурпурный
            "RESET": "\033[0m"
        }
        color = colors.get(tag, colors["INFO"])
        reset = colors["RESET"]
        print(f"{color}[{tag}]{reset} {text}")

    def show_notification(self, message: str, title: str = None, urgency: str = "normal"):
        """Показывает уведомление на рабочем столе через notify-send."""
        if not self.notifications_enabled:
            return

        title = title or self.app_name
        try:
            subprocess.run(
                [
                    "notify-send",
                    "-a", self.app_name,
                    "-t", str(self.timeout_ms),
                    "-u", urgency,
                    title,
                    message
                ],
                check=False
            )
        except Exception as e:
            self.log(f"Не удалось отправить уведомление: {e}", tag="WARN")

    def trigger_waifuland_emotion(self, emotion: str):
        """Отправляет команду смены эмоции в сокет Waifuland (если включено)."""
        if not self.waifuland_enabled or not os.path.exists(self.waifuland_socket):
            return

        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(self.waifuland_socket)
            payload = f'{{"action":"set_emotion","emotion":"{emotion}"}}\n'
            client.sendall(payload.encode("utf-8"))
            client.close()
        except Exception as e:
            self.log(f"Ошибка связи с сокетом Waifuland: {e}", tag="WARN")
