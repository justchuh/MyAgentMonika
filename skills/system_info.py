"""
Скилл информации о системе (память, диск, время, дата).
"""

import datetime
import shutil
from core.engine import skill

DAYS_ORDINAL = {
    1: "первое", 2: "второе", 3: "третье", 4: "четвёртое", 5: "пятое",
    6: "шестое", 7: "седьмое", 8: "восьмое", 9: "девятое", 10: "десятое",
    11: "одиннадцатое", 12: "двенадцатое", 13: "тринадцатое", 14: "четырнадцатое", 15: "пятнадцатое",
    16: "шестнадцатое", 17: "семнадцатое", 18: "восемнадцатое", 19: "девятнадцатое", 20: "двадцатое",
    21: "двадцать первое", 22: "двадцать второе", 23: "двадцать третье", 24: "двадцать четвёртое",
    25: "двадцать пятое", 26: "двадцать шестое", 27: "двадцать седьмое", 28: "двадцать восьмое",
    29: "двадцать девятое", 30: "тридцатое", 31: "тридцать первое"
}

@skill(
    name="system_time",
    triggers=[
        "который час", "сколько времени", "точное время", "время",
        "какое число", "число", "какой сегодня день", "дата",
        "what time", "time", "date"
    ],
    description="Сообщает текущее время или дату"
)
def report_time(text: str, context: dict) -> str:
    now = datetime.datetime.now()
    clean = text.lower()
    if any(k in clean for k in ["число", "день", "дата", "date"]):
        months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                  "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        day_str = DAYS_ORDINAL.get(now.day, str(now.day))
        month_str = months[now.month - 1]
        return f"Сегодня {day_str} {month_str} {now.year} года."
    else:
        return f"Сейчас {now.hour} часов {now.minute:02d} минут."


@skill(
    name="system_resources",
    triggers=[
        "свободное место", "место на диске", "сколько места",
        "память", "оперативная память", "статус системы", "нагрузка", "ресурсы",
        "system status", "system info"
    ],
    description="Сообщает статус свободного места и оперативной памяти"
)
def report_resources(text: str, context: dict) -> str:
    total, used, free = shutil.disk_usage("/")
    free_gb = free // (2**30)

    try:
        mem_available_bytes = 0
        mem_total_bytes = 0
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total_bytes = int(line.split()[1]) * 1024
                elif line.startswith("MemAvailable:"):
                    mem_available_bytes = int(line.split()[1]) * 1024

        avail_ram_gb = round(mem_available_bytes / (1024**3), 1)
        total_ram_gb = int(round(mem_total_bytes / (1024**3), 0))
        return f"Свободно {free_gb} гигабайт на диске. Доступно {avail_ram_gb} из {total_ram_gb} гигабайт оперативной памяти."
    except Exception:
        return f"На основном диске свободно {free_gb} гигабайт."
