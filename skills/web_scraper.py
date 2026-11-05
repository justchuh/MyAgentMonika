"""
Скилл для запроса актуальных курсов валют и крипты.
Числа форматируются целыми рублями и копейками для четкого и красивого произношения Silero TTS.
"""

import requests
from core.engine import skill


@skill(
    name="custom_site_scraper",
    triggers=[
        "проверь сайт", "курс валют", "курс рубля", "курсы валют", "курс доллара", "курс евро",
        "курс биткоина", "крипта", "биткоин", "currency", "rates", "crypto", "курс"
    ],
    description="Парсер актуальных котировок валют и крипты"
)
def handle_custom_scraping(text: str, context: dict) -> str:
    display = context.get("display")
    clean = text.lower()

    try:
        if any(k in clean for k in ["биткоин", "крипт", "crypto", "bitcoin"]):
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            btc_price = int(float(data["price"]))
            return f"Курс биткоина сейчас {btc_price} долларов."

        # По умолчанию курсы ЦБ РФ
        url = "https://www.cbr-xml-daily.ru/daily_json.js"
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()

        usd_val = float(data["Valute"]["USD"]["Value"])
        eur_val = float(data["Valute"]["EUR"]["Value"])

        usd_rub = int(usd_val)
        usd_kop = int(round((usd_val - usd_rub) * 100))

        eur_rub = int(eur_val)
        eur_kop = int(round((eur_val - eur_rub) * 100))

        return f"По данным Центробанка, курс доллара {usd_rub} рублей {usd_kop} копеек, евро {eur_rub} рублей {eur_kop} копеек."

    except Exception as e:
        if display:
            display.log(f"Ошибка при парсинге: {e}", tag="ERROR")
        return "Не удалось получить актуальные курсы валют."
