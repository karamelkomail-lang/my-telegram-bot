# -*- coding: utf-8 -*-
import os
import sys
import requests
from datetime import datetime
import random

# stdout utf-8 for GitHub Actions
sys.stdout.reconfigure(encoding='utf-8')

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8802273997:AAGZCVZoXlpY5q5aGxIwQwejpVwyW5AYYGc")
CHANNEL_ID     = os.environ.get("CHANNEL_ID",     "-1003762687242")
UNSPLASH_KEY   = os.environ.get("UNSPLASH_KEY",   "wNkT39ct4eJRAA8hbANDLPcyFJmyVUgBq5kI-2cRzmo")
GEMINI_KEY     = os.environ.get("GEMINI_KEY",     "ВСТАВЬТЕ_КЛЮЧ_GEMINI")

HOLIDAYS = {
    (1,  1):  ("Новый год",           "new year celebration snow"),
    (1,  7):  ("Рождество",           "christmas cozy candles"),
    (2, 14):  ("День влюблённых",     "love hearts roses"),
    (2, 23):  ("День защитника",      "patriotic blue sky nature"),
    (3,  8):  ("8 Марта",             "spring flowers women"),
    (5,  1):  ("Праздник весны",      "spring nature flowers"),
    (5,  9):  ("День Победы",         "red carnations memorial"),
    (6,  1):  ("День защиты детей",   "children happy playground"),
    (6, 12):  ("День России",         "russia nature landscape"),
    (12, 31): ("Канун Нового года",   "new year eve fireworks"),
}

MORNING_QUERIES = ["sunrise morning golden light","morning coffee flowers","dawn nature peaceful","morning dew flowers garden","sunrise landscape beautiful"]
DAY_QUERIES     = ["sunny day flowers meadow","beautiful nature sunshine","spring flowers bright colorful","colorful flowers garden","cheerful nature sunshine warm"]
NIGHT_QUERIES   = ["night stars peaceful sky","moon night cozy","evening sunset calm","night sky stars","cozy evening candlelight warm"]

FALLBACK = {
    "morning": [
        "Доброе утро! ☀️\n\nПусть этот день принесёт вам радость и тепло.\nУлыбнитесь — всё будет хорошо! 🌸",
        "Доброе утро! 🌅\n\nНовый день — новые возможности.\nПусть всё получится! ✨",
        "Утро доброе! 🌤\n\nПроснитесь с улыбкой — этот день будет вашим! ☕",
    ],
    "day": [
        "Добрый день! ☀️\n\nПусть середина дня зарядит вас энергией.\nВсё получится! 🌸",
        "Добрый день! 🌞\n\nПозвольте себе немного отдохнуть и зарядиться позитивом! ✨",
        "Добрый день! 🌼\n\nПусть этот час будет продуктивным и радостным! ☕",
    ],
    "night": [
        "Спокойной ночи! 🌙\n\nПусть ночь будет тихой, а сны — добрыми и светлыми. ✨",
        "Спокойной ночи! 🌠\n\nОтдохните и наберитесь сил для нового дня. 😊",
        "Спокойной ночи! 🛋\n\nПусть вам приснится что-то тёплое и светлое. ✨",
    ],
}


def get_time_of_day():
    h = datetime.now().hour
    if 5 <= h < 12:    return "morning"
    elif 12 <= h < 18: return "day"
    else:              return "night"


def get_today_holiday():
    now = datetime.now()
    return HOLIDAYS.get((now.month, now.day))


def get_image_url(query):
    try:
        r = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": query, "orientation": "portrait", "content_filter": "high"},
            headers={"Authorization": "Client-ID " + UNSPLASH_KEY},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()["urls"]["regular"]
    except Exception as e:
        print("Unsplash error: " + str(e))
        return None


def generate_caption(time_of_day, holiday_name=None):
    if time_of_day == "morning":
        prompt = "Напиши тёплое душевное пожелание «Доброе утро» для Telegram-канала. 2-3 строки, с эмодзи, как от близкого друга. Только текст поздравления."
    elif time_of_day == "night":
        prompt = "Напиши тёплое пожелание «Спокойной ночи» для Telegram-канала. 2-3 строки, уютное, с эмодзи. Только текст."
    elif holiday_name:
        prompt = "Напиши поздравление с праздником «" + holiday_name + "» для Telegram-канала. 3-4 строки, тёплое, с эмодзи. Только текст."
    else:
        prompt = "Напиши тёплое пожелание доброго дня для Telegram-канала. 2-3 строки, позитивное, с эмодзи. Только текст."

    try:
        r = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_KEY,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15,
        )
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        print("Gemini OK")
        return text
    except Exception as e:
        print("Gemini unavailable, using fallback")
        return random.choice(FALLBACK.get(time_of_day, FALLBACK["day"]))


def send_photo(image_url, caption):
    try:
        r = requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendPhoto",
            data={"chat_id": CHANNEL_ID, "photo": image_url, "caption": caption},
            timeout=15,
        )
        r.raise_for_status()
        print("Published successfully!")
        return True
    except Exception as e:
        print("Telegram error: " + str(e))
        return False


def main():
    print("Bot started: " + datetime.now().strftime("%d.%m.%Y %H:%M"))
    time_of_day = get_time_of_day()
    holiday = get_today_holiday()
    print("Time: " + time_of_day)

    if holiday:
        query, holiday_name = holiday[1], holiday[0]
        print("Holiday: " + holiday_name)
    elif time_of_day == "morning":
        query, holiday_name = random.choice(MORNING_QUERIES), None
    elif time_of_day == "day":
        query, holiday_name = random.choice(DAY_QUERIES), None
    else:
        query, holiday_name = random.choice(NIGHT_QUERIES), None

    print("Image: " + query)
    image_url = get_image_url(query)
    if not image_url:
        print("No image!")
        return

    caption = generate_caption(time_of_day, holiday_name)
    print("Done, posting...")
    send_photo(image_url, caption)


if __name__ == "__main__":
    main()
