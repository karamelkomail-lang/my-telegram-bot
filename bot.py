import os
import requests
from datetime import datetime
import random

# ─────────────────────────────────────────
#  НАСТРОЙКИ
# ─────────────────────────────────────────
TELEGRAM_TOKEN = "8802273997:AAGZCVZoXlpY5q5aGxIwQwejpVwyW5AYYGc"
CHANNEL_ID     = "-1003762687242"
UNSPLASH_KEY   = "wNkT39ct4eJRAA8hbANDLPcyFJmyVUgBq5kI-2cRzmo"
GEMINI_KEY     = "AQ.Ab8RN6KJz6Ap8BnPDzaJWb8Dbiso6tZq4r_n5IkHQBrd6pcK0g"
# ─────────────────────────────────────────

HOLIDAYS = {
    (1,  1):  ("Noviy God",           "new year celebration snow"),
    (1,  7):  ("Rozhdestvo",          "christmas cozy candles"),
    (2, 14):  ("Den Vlyublennykh",    "love hearts roses"),
    (2, 23):  ("Den Zashchitnika",    "patriotic blue sky nature"),
    (3,  8):  ("8 Marta",             "spring flowers women"),
    (5,  1):  ("Prazdnik Vesny",      "spring nature flowers"),
    (5,  9):  ("Den Pobedy",          "red carnations memorial"),
    (6,  1):  ("Den Zashchity Detey", "children happy playground"),
    (6, 12):  ("Den Rossii",          "russia nature landscape"),
    (12, 31): ("Kanunn Novogo Goda",  "new year eve fireworks"),
}

MORNING_QUERIES = [
    "sunrise morning golden light",
    "morning coffee flowers",
    "dawn nature peaceful",
    "morning dew flowers garden",
    "sunrise landscape beautiful",
]
DAY_QUERIES = [
    "sunny day flowers meadow",
    "beautiful nature sunshine",
    "spring flowers bright colorful",
    "colorful flowers garden",
    "cheerful nature sunshine warm",
]
NIGHT_QUERIES = [
    "night stars peaceful sky",
    "moon night cozy",
    "evening sunset calm",
    "night sky stars",
    "cozy evening candlelight warm",
]

FALLBACK = {
    "morning": "Dobroye utro! Pust etot den budet teplym i radostnym",
    "day":     "Dobryy den! Zaryazhaysya energiey i khoroshim nastroeniem",
    "night":   "Spokoynoy nochi! Pust sny budut dobrymi i svetlymi",
}


def get_time_of_day():
    h = datetime.now().hour
    if 5 <= h < 12:  return "morning"
    elif 12 <= h < 18: return "day"
    else: return "night"


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
        prompt = "Напиши тёплое душевное пожелание Доброе утро для Telegram канала. 2-3 строки, с эмодзи, как от близкого друга. Только текст."
    elif time_of_day == "night":
        prompt = "Напиши тёплое пожелание Спокойной ночи для Telegram канала. 2-3 строки, уютное, с эмодзи. Только текст."
    elif holiday_name:
        prompt = "Напиши поздравление с праздником для Telegram канала. 3-4 строки, тёплое, с эмодзи. Только текст."
    else:
        prompt = "Напиши тёплое пожелание доброго дня для Telegram канала. 2-3 строки, позитивное, с эмодзи. Только текст."

    try:
        r = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_KEY,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print("Gemini error: " + str(e))
        return FALLBACK.get(time_of_day, "Have a wonderful day!")


def send_photo(image_url, caption):
    try:
        r = requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendPhoto",
            data={"chat_id": CHANNEL_ID, "photo": image_url, "caption": caption},
            timeout=15,
        )
        r.raise_for_status()
        print("Published!")
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

    print("Image query: " + query)
    image_url = get_image_url(query)
    if not image_url:
        print("No image, stopping.")
        return

    print("Generating caption...")
    caption = generate_caption(time_of_day, holiday_name)
    print("Caption: " + caption)
    send_photo(image_url, caption)


if __name__ == "__main__":
    main()
