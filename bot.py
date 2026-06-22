# -*- coding: utf-8 -*-
import os
import sys
import io
import random
from datetime import datetime, timedelta, timezone

import requests
from PIL import Image, ImageDraw, ImageFont

from holidays import HOLIDAYS
from jokes import get_random_joke, get_random_fact

sys.stdout.reconfigure(encoding='utf-8')

# ─────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8802273997:AAGZCVZoXlpY5q5aGxIwQwejpVwyW5AYYGc")
CHANNEL_ID     = os.environ.get("CHANNEL_ID",     "-1003762687242")
UNSPLASH_KEY   = os.environ.get("UNSPLASH_KEY",   "wNkT39ct4eJRAA8hbANDLPcyFJmyVUgBq5kI-2cRzmo")
GEMINI_KEY     = os.environ.get("GEMINI_KEY",     "")
# Слот передаётся из GitHub Actions: morning/day/holiday1/joke/fact/afternoon/holiday2/evening/night
POST_SLOT      = os.environ.get("POST_SLOT", "auto")
# ─────────────────────────────────────────

MOSCOW_TZ = timezone(timedelta(hours=3))
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans-Bold.ttf")

MORNING_QUERIES   = ["sunrise morning golden light","morning coffee flowers","dawn nature peaceful","morning dew flowers garden","sunrise landscape beautiful","morning forest light mist"]
DAY_QUERIES       = ["sunny day flowers meadow","beautiful nature sunshine","spring flowers bright colorful","colorful flowers garden","cheerful nature sunshine warm","blue sky summer field"]
AFTERNOON_QUERIES = ["warm afternoon light nature","peaceful countryside sunshine","flowers field bright day"]
EVENING_QUERIES   = ["sunset golden hour calm","evening sky orange clouds","sunset over water peaceful","golden hour nature warm"]
NIGHT_QUERIES     = ["night stars peaceful sky","moon night cozy","night sky stars milky way","cozy evening candlelight warm"]
JOKE_QUERIES      = ["funny cute animal colorful","quirky cheerful illustration","playful bright colorful background"]
FACT_QUERIES      = ["curious nature macro colorful","interesting wildlife close up","amazing nature detail bright"]

IMAGE_TEXT = {
    "morning":   ["Доброе утро!", "Утро доброе!", "С добрым утром!"],
    "day":       ["Добрый день!", "Хорошего дня!", "Доброго дня!"],
    "afternoon": ["Хорошего полудня!", "Доброго времени!"],
    "evening":   ["Доброго вечера!", "Хорошего вечера!"],
    "night":     ["Спокойной ночи!", "Сладких снов!", "Доброй ночи!"],
    "joke":      ["Улыбнись!", "Юмор дня"],
    "fact":      ["А вы знали?", "Интересный факт"],
}

CAPTION_FALLBACK = {
    "morning": [
        "Пусть этот день принесёт вам радость и тепло. Улыбнитесь — всё будет хорошо! 🌸",
        "Новый день — новые возможности. Пусть всё получится! ✨",
        "Проснитесь с улыбкой — этот день будет вашим! ☕",
    ],
    "day": [
        "Пусть середина дня зарядит вас энергией и хорошим настроением 🌸",
        "Позвольте себе немного отдохнуть и зарядиться позитивом! ✨",
    ],
    "afternoon": [
        "Пусть остаток дня пройдёт легко и спокойно 🌼",
        "Самое время сделать паузу и улыбнуться 😊",
    ],
    "evening": [
        "Пусть вечер подарит уют и спокойствие после насыщенного дня 🌇",
        "Самое время остановиться и просто насладиться моментом 🍂",
    ],
    "night": [
        "Пусть ночь будет тихой, а сны — добрыми и светлыми ✨",
        "Отдохните и наберитесь сил для нового дня 😊",
    ],
}

HOLIDAY_CAPTION_FALLBACK = [
    "Сегодня особенный день! Поздравляем всех причастных и желаем отличного настроения 🎉",
    "Пусть праздник принесёт улыбки и радость в этот день! 🎊",
    "С праздником! Пусть день будет добрым и запоминающимся ✨",
]


def now_msk():
    return datetime.now(MOSCOW_TZ)


def get_today_holidays():
    """Возвращает список всех праздников на сегодня."""
    today = now_msk()
    return HOLIDAYS.get((today.month, today.day), [])


def pick_two_distinct_holidays():
    """Для двух праздничных слотов в день выбираем два разных праздника, если есть."""
    items = get_today_holidays()
    if not items:
        return None, None
    if len(items) == 1:
        return items[0], None
    chosen = random.sample(items, min(2, len(items)))
    return chosen[0], chosen[1] if len(chosen) > 1 else None


def get_image_bytes(query, attempts=3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(
                "https://api.unsplash.com/photos/random",
                params={"query": query, "orientation": "portrait", "content_filter": "high"},
                headers={"Authorization": "Client-ID " + UNSPLASH_KEY},
                timeout=25,
            )
            r.raise_for_status()
            img_url = r.json()["urls"]["regular"]
            img_r = requests.get(img_url, timeout=25)
            img_r.raise_for_status()
            print("Image source: Unsplash")
            return img_r.content
        except Exception as e:
            last_error = e
            print("Unsplash attempt " + str(attempt) + " failed: " + str(e))
    print("Unsplash error after " + str(attempts) + " attempts: " + str(last_error))

    # Фоллбэк: случайное фото с Picsum (без API ключа)
    print("Trying Picsum fallback...")
    for attempt in range(1, attempts + 1):
        try:
            # seed случайный, чтобы каждый раз было разное фото
            seed = random.randint(1, 1000)
            r = requests.get(
                "https://picsum.photos/seed/" + str(seed) + "/1080/1350",
                timeout=25,
                allow_redirects=True,
            )
            r.raise_for_status()
            print("Image source: Picsum (seed=" + str(seed) + ")")
            return r.content
        except Exception as e:
            print("Picsum attempt " + str(attempt) + " failed: " + str(e))

    print("All image sources failed.")
    return None


def draw_text_on_image(image_bytes, headline, font_path=FONT_PATH):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    target_w, target_h = 1080, 1350
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h
    if img_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * img_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / img_ratio)
    img = img.resize((new_w, new_h))
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    gradient_height = int(target_h * 0.42)
    for i in range(gradient_height):
        alpha = int(150 * (i / gradient_height))
        y = target_h - gradient_height + i
        draw_overlay.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    font_size = 78
    font = ImageFont.truetype(font_path, font_size)
    max_width = target_w - 120
    while True:
        bbox = draw.textbbox((0, 0), headline, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width or font_size <= 36:
            break
        font_size -= 4
        font = ImageFont.truetype(font_path, font_size)

    bbox = draw.textbbox((0, 0), headline, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (target_w - w) / 2
    y = target_h - gradient_height + (gradient_height - h) / 2 - 10

    draw.text((x + 4, y + 4), headline, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), headline, font=font, fill=(255, 255, 255, 255))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    out.seek(0)
    return out


def gemini_request(prompt):
    if not GEMINI_KEY:
        return None
    try:
        r = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_KEY,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print("Gemini unavailable: " + str(e))
        return None


def build_caption(slot, holiday_name=None):
    if holiday_name:
        prompt = ("Напиши короткое тёплое поздравление с праздником «" + holiday_name +
                   "» для Telegram-канала. 2-3 строки, искренне, с эмодзи. Только текст.")
        text = gemini_request(prompt)
        return text or random.choice(HOLIDAY_CAPTION_FALLBACK)

    if slot in ("morning", "day", "afternoon", "evening", "night"):
        prompts = {
            "morning": "Напиши тёплое пожелание доброго утра для Telegram-канала, 2 строки, с эмодзи. Только текст.",
            "day": "Напиши тёплое пожелание доброго дня для Telegram-канала, 2 строки, с эмодзи. Только текст.",
            "afternoon": "Напиши лёгкое пожелание хорошего полудня для Telegram-канала, 2 строки, с эмодзи. Только текст.",
            "evening": "Напиши тёплое пожелание доброго вечера для Telegram-канала, 2 строки, с эмодзи. Только текст.",
            "night": "Напиши тёплое пожелание спокойной ночи для Telegram-канала, 2 строки, с эмодзи. Только текст.",
        }
        text = gemini_request(prompts[slot])
        return text or random.choice(CAPTION_FALLBACK.get(slot, CAPTION_FALLBACK["day"]))

    if slot == "joke":
        return get_random_joke()
    if slot == "fact":
        return get_random_fact()

    return random.choice(CAPTION_FALLBACK["day"])


def send_photo(image_file, caption):
    try:
        r = requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendPhoto",
            data={"chat_id": CHANNEL_ID, "caption": caption},
            files={"photo": ("card.jpg", image_file, "image/jpeg")},
            timeout=30,
        )
        r.raise_for_status()
        print("Published successfully!")
        return True
    except Exception as e:
        print("Telegram error: " + str(e))
        return False


def send_text(text):
    """Отправка текстового поста без фото — последний резерв."""
    try:
        r = requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage",
            data={"chat_id": CHANNEL_ID, "text": text},
            timeout=30,
        )
        r.raise_for_status()
        print("Text-only post sent!")
        return True
    except Exception as e:
        print("Telegram text error: " + str(e))
        return False


def main():
    today = now_msk()
    print("Bot started (MSK): " + today.strftime("%d.%m.%Y %H:%M"))
    slot = POST_SLOT
    print("Slot: " + slot)

    holiday_name = None

    if slot in ("holiday1", "holiday2"):
        h1, h2 = pick_two_distinct_holidays()
        chosen = h1 if slot == "holiday1" else h2
        if not chosen:
            print("No holiday for this slot today, skipping.")
            return
        holiday_name, _, query = chosen
        headline = holiday_name
        print("Holiday post: " + holiday_name)

    elif slot == "joke":
        query = random.choice(JOKE_QUERIES)
        headline = random.choice(IMAGE_TEXT["joke"])

    elif slot == "fact":
        query = random.choice(FACT_QUERIES)
        headline = random.choice(IMAGE_TEXT["fact"])

    elif slot == "morning":
        query = random.choice(MORNING_QUERIES)
        headline = random.choice(IMAGE_TEXT["morning"])

    elif slot == "day":
        query = random.choice(DAY_QUERIES)
        headline = random.choice(IMAGE_TEXT["day"])

    elif slot == "afternoon":
        query = random.choice(AFTERNOON_QUERIES)
        headline = random.choice(IMAGE_TEXT["afternoon"])

    elif slot == "evening":
        query = random.choice(EVENING_QUERIES)
        headline = random.choice(IMAGE_TEXT["evening"])

    elif slot == "night":
        query = random.choice(NIGHT_QUERIES)
        headline = random.choice(IMAGE_TEXT["night"])

    else:
        # auto-fallback по часу, на случай ручного теста
        hour = today.hour
        if 6 <= hour < 10:
            slot, query, headline = "morning", random.choice(MORNING_QUERIES), random.choice(IMAGE_TEXT["morning"])
        elif 10 <= hour < 14:
            slot, query, headline = "day", random.choice(DAY_QUERIES), random.choice(IMAGE_TEXT["day"])
        elif 14 <= hour < 18:
            slot, query, headline = "afternoon", random.choice(AFTERNOON_QUERIES), random.choice(IMAGE_TEXT["afternoon"])
        elif 18 <= hour < 21:
            slot, query, headline = "evening", random.choice(EVENING_QUERIES), random.choice(IMAGE_TEXT["evening"])
        else:
            slot, query, headline = "night", random.choice(NIGHT_QUERIES), random.choice(IMAGE_TEXT["night"])

    print("Image query: " + query)
    image_bytes = get_image_bytes(query)

    caption = build_caption(slot, holiday_name)
    print("Caption: " + caption)

    if not image_bytes:
        # Последний резерв — отправить пост текстом без фото
        print("No image available, sending text-only post.")
        send_text(headline + "\n\n" + caption)
        return

    print("Drawing headline: " + headline)
    final_image = draw_text_on_image(image_bytes, headline)

    send_photo(final_image, caption)


if __name__ == "__main__":
    main()
