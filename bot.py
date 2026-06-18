import os
import requests
from datetime import datetime
import random

TELEGRAM_TOKEN = "8802273997:AAGZCVZoXlpY5q5aGxIwQwejpVwyW5AYYGc"
CHANNEL_ID     = "-1003762687242"
UNSPLASH_KEY   = "wNkT39ct4eJRAA8hbANDLPcyFJmyVUgBq5kI-2cRzmo"
GEMINI_KEY     = "AQ.Ab8RN6KJz6Ap8BnPDzaJWb8Dbiso6tZq4r_n5IkHQBrd6pcK0g"

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

MORNING_QUERIES = ["sunrise morning golden light","morning coffee flowers","dawn nature peaceful","morning dew flowers garden","sunrise landscape beautiful"]
DAY_QUERIES     = ["sunny day flowers meadow","beautiful nature sunshine","spring flowers bright colorful","colorful flowers garden","cheerful nature sunshine warm"]
NIGHT_QUERIES   = ["night stars peaceful sky","moon night cozy","evening sunset calm","night sky stars","cozy evening candlelight warm"]

# Запасные тексты на русском (если Gemini недоступен)
FALLBACK = {
    "morning": [
        "\u0414\u043e\u0431\u0440\u043e\u0435 \u0443\u0442\u0440\u043e! \u2600\ufe0f\n\n\u041f\u0443\u0441\u0442\u044c \u044d\u0442\u043e\u0442 \u0434\u0435\u043d\u044c \u043f\u0440\u0438\u043d\u0435\u0441\u0451\u0442 \u0432\u0430\u043c \u0440\u0430\u0434\u043e\u0441\u0442\u044c \u0438 \u0442\u0435\u043f\u043b\u043e.\n\u0423\u043b\u044b\u0431\u043d\u0438\u0442\u0435\u0441\u044c \u2014 \u0432\u0441\u0451 \u0431\u0443\u0434\u0435\u0442 \u0445\u043e\u0440\u043e\u0448\u043e! \ud83c\udf38",
        "\u0414\u043e\u0431\u0440\u043e\u0435 \u0443\u0442\u0440\u043e! \ud83c\udf05\n\n\u041d\u043e\u0432\u044b\u0439 \u0434\u0435\u043d\u044c \u2014 \u043d\u043e\u0432\u044b\u0435 \u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0441\u0442\u0438.\n\u041f\u0443\u0441\u0442\u044c \u0432\u0441\u0451 \u043f\u043e\u043b\u0443\u0447\u0430\u0435\u0442\u0441\u044f! \u2728",
        "\u0423\u0442\u0440\u043e \u0434\u043e\u0431\u0440\u043e\u0435! \ud83c\udf24\ufe0f\n\n\u041f\u0440\u043e\u0441\u043d\u0438\u0442\u0435\u0441\u044c \u0441 \u0443\u043b\u044b\u0431\u043a\u043e\u0439 \u2014 \u044d\u0442\u043e\u0442 \u0434\u0435\u043d\u044c \u0431\u0443\u0434\u0435\u0442 \u0432\u0430\u0448\u0438\u043c! \u2615\ufe0f",
    ],
    "day": [
        "\u0414\u043e\u0431\u0440\u044b\u0439 \u0434\u0435\u043d\u044c! \u2600\ufe0f\n\n\u041f\u0443\u0441\u0442\u044c \u0441\u0435\u0440\u0435\u0434\u0438\u043d\u0430 \u0434\u043d\u044f \u0437\u0430\u0440\u044f\u0434\u0438\u0442 \u0432\u0430\u0441 \u044d\u043d\u0435\u0440\u0433\u0438\u0435\u0439.\n\u0412\u0441\u0451 \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u0441\u044f! \ud83c\udf38",
        "\u0414\u043e\u0431\u0440\u044b\u0439 \u0434\u0435\u043d\u044c! \ud83c\udf1e\n\n\u041f\u043e\u0437\u0432\u043e\u043b\u044c\u0442\u0435 \u0441\u0435\u0431\u0435 \u043d\u0435\u043c\u043d\u043e\u0433\u043e \u043e\u0442\u0434\u043e\u0445\u043d\u0443\u0442\u044c \u0438 \u0437\u0430\u0440\u044f\u0434\u0438\u0442\u044c\u0441\u044f \u043f\u043e\u0437\u0438\u0442\u0438\u0432\u043e\u043c! \u2728",
        "\u0414\u043e\u0431\u0440\u044b\u0439 \u0434\u0435\u043d\u044c! \ud83c\udf3c\n\n\u041f\u0443\u0441\u0442\u044c \u044d\u0442\u043e\u0442 \u0447\u0430\u0441 \u0431\u0443\u0434\u0435\u0442 \u043f\u0440\u043e\u0434\u0443\u043a\u0442\u0438\u0432\u043d\u044b\u043c \u0438 \u0440\u0430\u0434\u043e\u0441\u0442\u043d\u044b\u043c! \u2615\ufe0f",
    ],
    "night": [
        "\u0421\u043f\u043e\u043a\u043e\u0439\u043d\u043e\u0439 \u043d\u043e\u0447\u0438! \ud83c\udf19\n\n\u041f\u0443\u0441\u0442\u044c \u043d\u043e\u0447\u044c \u0431\u0443\u0434\u0435\u0442 \u0442\u0438\u0445\u043e\u0439, \u0430 \u0441\u043d\u044b \u2014 \u0434\u043e\u0431\u0440\u044b\u043c\u0438 \u0438 \u0441\u0432\u0435\u0442\u043b\u044b\u043c\u0438. \u2728",
        "\u0421\u043f\u043e\u043a\u043e\u0439\u043d\u043e\u0439 \u043d\u043e\u0447\u0438! \ud83c\udf20\n\n\u041e\u0442\u0434\u043e\u0445\u043d\u0438\u0442\u0435 \u0438 \u043d\u0430\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u0438\u043b \u0434\u043b\u044f \u043d\u043e\u0432\u043e\u0433\u043e \u0434\u043d\u044f. \ud83d\ude0a",
        "\u0421\u043f\u043e\u043a\u043e\u0439\u043d\u043e\u0439 \u043d\u043e\u0447\u0438! \ud83d\udecc\n\n\u041f\u0443\u0441\u0442\u044c \u0432\u0430\u043c \u043f\u0440\u0438\u0441\u043d\u0438\u0442\u0441\u044f \u0447\u0442\u043e-\u0442\u043e \u0442\u0451\u043f\u043b\u043e\u0435 \u0438 \u0441\u0432\u0435\u0442\u043b\u043e\u0435. \u2728",
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


def generate_caption_gemini(time_of_day, holiday_name=None):
    if time_of_day == "morning":
        prompt = "Напиши тёплое душевное пожелание «Доброе утро» для Telegram-канала. 2-3 строки, с эмодзи, как от близкого друга. Только текст поздравления."
    elif time_of_day == "night":
        prompt = "Напиши тёплое пожелание «Спокойной ночи» для Telegram-канала. 2-3 строки, уютное, с эмодзи. Только текст."
    elif holiday_name:
        prompt = "Напиши поздравление с праздником для Telegram-канала, праздник: " + holiday_name + ". 3-4 строки, тёплое, с эмодзи. Только текст."
    else:
        prompt = "Напиши тёплое пожелание доброго дня для Telegram-канала. 2-3 строки, позитивное, с эмодзи. Только текст."

    r = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_KEY,
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=15,
    )
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    return text


def generate_caption(time_of_day, holiday_name=None):
    try:
        text = generate_caption_gemini(time_of_day, holiday_name)
        print("Gemini OK")
        return text
    except Exception as e:
        print("Gemini error: " + str(e) + " — using fallback")
        return random.choice(FALLBACK.get(time_of_day, FALLBACK["day"]))


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

    print("Image: " + query)
    image_url = get_image_url(query)
    if not image_url:
        print("No image!")
        return

    caption = generate_caption(time_of_day, holiday_name)
    print("Caption: " + caption)
    send_photo(image_url, caption)


if __name__ == "__main__":
    main()
