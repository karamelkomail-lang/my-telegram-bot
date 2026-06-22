# -*- coding: utf-8 -*-
import os
import sys
import io
import random
import urllib.parse
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
PEXELS_KEY     = os.environ.get("PEXELS_KEY",     "")
GEMINI_KEY     = os.environ.get("GEMINI_KEY",     "")
# Слот передаётся из GitHub Actions: morning/day/holiday1/joke/fact/afternoon/holiday2/evening/night
POST_SLOT      = os.environ.get("POST_SLOT", "auto")
# ─────────────────────────────────────────

MOSCOW_TZ = timezone(timedelta(hours=3))
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans-Bold.ttf")

# Слоты, для которых используем рисованные иллюстрации (Pollinations.ai)
ILLUSTRATED_SLOTS = {"evening", "night", "joke", "holiday1", "holiday2"}
# Остальные слоты (morning, day, afternoon, fact) — фотографии (Pexels/Unsplash/Picsum)

MORNING_QUERIES   = ["sunrise morning golden light","morning coffee flowers","dawn nature peaceful","morning dew flowers garden","sunrise landscape beautiful","morning forest light mist"]
DAY_QUERIES       = ["sunny day flowers meadow","beautiful nature sunshine","spring flowers bright colorful","colorful flowers garden","cheerful nature sunshine warm","blue sky summer field"]
AFTERNOON_QUERIES = ["warm afternoon light nature","peaceful countryside sunshine","flowers field bright day"]
FACT_QUERIES       = ["curious nature macro colorful","interesting wildlife close up","amazing nature detail bright"]

# Промпты для рисованных иллюстраций (стиль как у популярных открыточных каналов)
EVENING_ART_QUERIES = [
    "cozy watercolor illustration good evening, warm sunset colors, flowers, soft pastel art style, greeting card",
    "cute cartoon illustration evening cottage, warm lights, flowers, digital art greeting card style",
    "whimsical illustration evening tea time, cozy house, soft glowing lights, pastel colors",
]
NIGHT_ART_QUERIES = [
    "cute cartoon illustration good night, moon and stars, cozy bedroom, soft pastel colors, greeting card art",
    "whimsical fairytale illustration sleeping moon, stars, lavender purple tones, digital art",
    "cozy watercolor illustration night sky, stars, sleeping animals, soft glowing colors",
]
JOKE_ART_QUERIES = [
    "cute cartoon illustration funny animal, bright colors, playful digital art style, greeting card",
    "whimsical illustration cheerful character smiling, bright pastel colors, digital art",
]

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
    today = now_msk()
    return HOLIDAYS.get((today.month, today.day), [])


def pick_two_distinct_holidays():
    items = get_today_holidays()
    if not items:
        return None, None
    if len(items) == 1:
        return items[0], None
    chosen = random.sample(items, min(2, len(items)))
    return chosen[0], chosen[1] if len(chosen) > 1 else None


# ───────────────────────── Источники картинок ─────────────────────────

def get_illustration_bytes(prompt, attempts=3):
    """Рисованная иллюстрация через Pollinations.ai (без ключа, без оплаты)."""
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999999)
    url = ("https://image.pollinations.ai/prompt/" + encoded +
           "?width=1080&height=1350&model=flux&nologo=true&seed=" + str(seed))
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=40)
            r.raise_for_status()
            if len(r.content) > 1000:  # отбрасываем пустые/ошибочные ответы
                print("Image source: Pollinations (illustration)")
                return r.content
            print("Pollinations returned suspiciously small response, retrying...")
        except Exception as e:
            print("Pollinations attempt " + str(attempt) + " failed: " + str(e))
    print("Pollinations failed after " + str(attempts) + " attempts.")
    return None


def get_photo_bytes(query, attempts=3):
    """Фотография: Pexels → Unsplash → Picsum, в порядке приоритета."""
    if PEXELS_KEY:
        for attempt in range(1, attempts + 1):
            try:
                r = requests.get(
                    "https://api.pexels.com/v1/search",
                    params={"query": query, "orientation": "portrait", "per_page": 15},
                    headers={"Authorization": PEXELS_KEY},
                    timeout=20,
                )
                r.raise_for_status()
                photos = r.json().get("photos", [])
                if photos:
                    img_url = random.choice(photos)["src"]["large2x"]
                    img_r = requests.get(img_url, timeout=20)
                    img_r.raise_for_status()
                    print("Image source: Pexels")
                    return img_r.content
            except Exception as e:
                print("Pexels attempt " + str(attempt) + " failed: " + str(e))
        print("Pexels failed after " + str(attempts) + " attempts.")

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
            print("Unsplash attempt " + str(attempt) + " failed: " + str(e))
    print("Unsplash failed after " + str(attempts) + " attempts.")

    for attempt in range(1, 3):
        try:
            seed = random.randint(1, 1000)
            r = requests.get(
                "https://picsum.photos/seed/" + str(seed) + "/1080/1350",
                timeout=20,
                allow_redirects=True,
            )
            r.raise_for_status()
            print("Image source: Picsum (seed=" + str(seed) + ")")
            return r.content
        except Exception as e:
            print("Picsum attempt " + str(attempt) + " failed: " + str(e))

    print("All photo sources failed.")
    return None


def draw_text_on_image(image_bytes, headline, font_path=FONT_PATH, illustrated=False):
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

    # Для иллюстраций — текст ближе к верху, чтобы не перекрывать арт по центру/низу.
    # Для фото — классический затемнённый низ.
    if illustrated:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        gradient_height = int(target_h * 0.30)
        for i in range(gradient_height):
            alpha = int(140 * (1 - i / gradient_height))
            draw_overlay.line([(0, i), (target_w, i)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        text_y_center = gradient_height * 0.5
    else:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        gradient_height = int(target_h * 0.42)
        for i in range(gradient_height):
            alpha = int(150 * (i / gradient_height))
            y = target_h - gradient_height + i
            draw_overlay.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        text_y_center = target_h - gradient_height / 2 - 10

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
    y = text_y_center - h / 2

    draw.text((x + 4, y + 4), headline, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), headline, font=font, fill=(255, 255, 255, 255))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    out.seek(0)
    return out


# ───────────────────────── Текст подписи ─────────────────────────

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


# ───────────────────────── Отправка в Telegram ─────────────────────────

def send_photo(image_file, caption):
    try:
        r = requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendPhoto",
            data={"chat_id": CHANNEL_ID, "caption": caption},
            files={"photo": ("card.jpg", image_file, "image/jpeg")},
            timeout=40,
        )
        r.raise_for_status()
        print("Published successfully!")
        return True
    except Exception as e:
        print("Telegram error: " + str(e))
        return False


def send_text(text):
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


# ───────────────────────── Главная логика ─────────────────────────

def main():
    today = now_msk()
    print("Bot started (MSK): " + today.strftime("%d.%m.%Y %H:%M"))
    slot = POST_SLOT
    print("Slot: " + slot)

    holiday_name = None
    illustrated = slot in ILLUSTRATED_SLOTS

    if slot in ("holiday1", "holiday2"):
        h1, h2 = pick_two_distinct_holidays()
        chosen = h1 if slot == "holiday1" else h2
        if not chosen:
            print("No holiday for this slot today, skipping.")
            return
        holiday_name, _, base_query = chosen
        headline = holiday_name
        # Превращаем тему праздника в художественный промпт
        art_prompt = ("cute cartoon illustration, " + base_query +
                       ", warm pastel colors, greeting card digital art style")
        print("Holiday post: " + holiday_name)

    elif slot == "joke":
        art_prompt = random.choice(JOKE_ART_QUERIES)
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
        art_prompt = random.choice(EVENING_ART_QUERIES)
        headline = random.choice(IMAGE_TEXT["evening"])

    elif slot == "night":
        art_prompt = random.choice(NIGHT_ART_QUERIES)
        headline = random.choice(IMAGE_TEXT["night"])

    else:
        hour = today.hour
        if 6 <= hour < 10:
            slot, query, headline, illustrated = "morning", random.choice(MORNING_QUERIES), random.choice(IMAGE_TEXT["morning"]), False
        elif 10 <= hour < 14:
            slot, query, headline, illustrated = "day", random.choice(DAY_QUERIES), random.choice(IMAGE_TEXT["day"]), False
        elif 14 <= hour < 18:
            slot, query, headline, illustrated = "afternoon", random.choice(AFTERNOON_QUERIES), random.choice(IMAGE_TEXT["afternoon"]), False
        elif 18 <= hour < 21:
            slot, illustrated = "evening", True
            art_prompt, headline = random.choice(EVENING_ART_QUERIES), random.choice(IMAGE_TEXT["evening"])
        else:
            slot, illustrated = "night", True
            art_prompt, headline = random.choice(NIGHT_ART_QUERIES), random.choice(IMAGE_TEXT["night"])

    if illustrated:
        print("Illustration prompt: " + art_prompt)
        image_bytes = get_illustration_bytes(art_prompt)
        if not image_bytes:
            print("Illustration failed, falling back to photo source.")
            fallback_query = headline
            image_bytes = get_photo_bytes(fallback_query)
    else:
        print("Photo query: " + query)
        image_bytes = get_photo_bytes(query)

    caption = build_caption(slot, holiday_name)
    print("Caption: " + caption)

    if not image_bytes:
        print("No image available, sending text-only post.")
        send_text(headline + "\n\n" + caption)
        return

    print("Drawing headline: " + headline)
    final_image = draw_text_on_image(image_bytes, headline, illustrated=illustrated)
    send_photo(final_image, caption)


if __name__ == "__main__":
    main()
