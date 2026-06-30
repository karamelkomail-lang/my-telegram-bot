# -*- coding: utf-8 -*-
"""
Telegram-бот "Открытки с душой" — простая и надёжная версия.

Принцип:
1. Скрипт сам вычисляет московское время и сам решает, какой слот сейчас публиковать.
   GitHub Actions просто запускает его раз в час (cron '0 * * * *'), без передачи
   POST_SLOT и без bash-логики определения времени — вся логика в одном месте, в Python.
2. Журнал публикаций (posted_log.txt) хранит "ГГГГ-ММ-ДД:slot" для каждого факта публикации.
   Если сегодняшний слот уже в журнале — публикация не повторяется, что бы ни случилось
   с задержками/повторами cron.
3. Если на текущий час не назначен ни один слот — скрипт просто завершается без публикации.
"""
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
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL_ID     = os.environ.get("CHANNEL_ID", "")
UNSPLASH_KEY   = os.environ.get("UNSPLASH_KEY", "")
PEXELS_KEY     = os.environ.get("PEXELS_KEY", "")
GEMINI_KEY     = os.environ.get("GEMINI_KEY", "")
# ─────────────────────────────────────────

MOSCOW_TZ = timezone(timedelta(hours=3))
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans-Bold.ttf")
LOG_FILE = os.path.join(os.path.dirname(__file__), "posted_log.txt")

# Расписание: московский час -> слот. Один слот на час, без пересечений.
SCHEDULE = {
    7:  "morning",
    10: "holiday1",
    12: "day",
    14: "joke",
    15: "afternoon",
    17: "fact",
    18: "holiday2",
    19: "evening",
    22: "night",
}

ILLUSTRATED_SLOTS = {"evening", "night", "joke", "holiday1", "holiday2"}

MORNING_QUERIES   = ["sunrise morning golden light", "morning coffee flowers", "dawn nature peaceful", "morning dew flowers garden", "sunrise landscape beautiful", "morning forest light mist"]
DAY_QUERIES       = ["sunny day flowers meadow", "beautiful nature sunshine", "spring flowers bright colorful", "colorful flowers garden", "cheerful nature sunshine warm", "blue sky summer field"]
AFTERNOON_QUERIES = ["warm afternoon light nature", "peaceful countryside sunshine", "flowers field bright day"]
FACT_QUERIES      = ["curious nature macro colorful", "interesting wildlife close up", "amazing nature detail bright"]

EVENING_ART_PROMPTS = [
    'Greeting card illustration, large 3D puffy bubble letters spelling "Доброго вечера!" in Russian Cyrillic, warm sunset colors, cozy cottage scene with flowers below the text, soft pastel art style, decorative border',
    'Greeting card illustration with elegant handwritten cursive text "Доброго вечера" in Russian Cyrillic at the top, golden hour sunset background, blooming flowers, warm glowing light, watercolor style',
]
NIGHT_ART_PROMPTS = [
    'Greeting card illustration, elegant handwritten cursive text "Доброй ночи" in Russian Cyrillic glowing softly, sleeping crescent moon with stars, lavender purple night sky, whimsical fairytale style',
    'Greeting card illustration, large 3D puffy bubble letters spelling "Спокойной ночи!" in Russian Cyrillic, night sky background with stars and moon, soft pastel colors, cute sleeping animals below',
]
JOKE_ART_PROMPTS = [
    'Cute cartoon greeting card, large 3D puffy bubble letters spelling "Улыбнись!" in Russian Cyrillic, bright cheerful colors, playful funny character illustration below the text',
]

EVENING_SCENE_PROMPTS = [
    "cozy watercolor illustration, warm sunset colors, cottage scene with flowers, soft pastel art style, greeting card, no text, no letters, no words",
    "golden hour sunset background, blooming flowers, warm glowing light, watercolor style, no text, no letters, no words",
]
NIGHT_SCENE_PROMPTS = [
    "sleeping crescent moon with stars, lavender purple night sky, whimsical fairytale style, no text, no letters, no words",
    "night sky background with stars and moon, soft pastel colors, cute sleeping animals, no text, no letters, no words",
]
JOKE_SCENE_PROMPTS = [
    "bright cheerful colors, playful funny cartoon animal illustration, no text, no letters, no words",
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
]


def now_msk():
    return datetime.now(MOSCOW_TZ)


# ───────────────────────── Журнал публикаций (защита от дублей) ─────────────────────────

def already_posted_today(slot):
    """Проверяет, был ли этот слот уже опубликован сегодня (по дате МСК)."""
    if not os.path.exists(LOG_FILE):
        return False
    today_key = now_msk().strftime("%Y-%m-%d") + ":" + slot
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
        return today_key in lines
    except Exception as e:
        print("Could not read posted_log.txt: " + str(e))
        return False


def mark_posted(slot):
    """Добавляет запись в журнал и обрезает его до последних 30 строк (чтобы не рос бесконечно)."""
    today_key = now_msk().strftime("%Y-%m-%d") + ":" + slot
    try:
        lines = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
        lines.append(today_key)
        lines = lines[-30:]
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("posted_log.txt updated: " + today_key)
    except Exception as e:
        print("Could not write posted_log.txt: " + str(e))


# ───────────────────────── Праздники ─────────────────────────

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

def get_pollinations_illustration_bytes(prompt, attempts=2):
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999999)
    url = ("https://image.pollinations.ai/prompt/" + encoded +
           "?width=1080&height=1350&model=flux&nologo=true&seed=" + str(seed))
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=40)
            r.raise_for_status()
            if len(r.content) > 1000:
                print("Image source: Pollinations")
                return r.content
        except Exception as e:
            print("Pollinations attempt " + str(attempt) + " failed: " + str(e))
    return None


def gemini_auth_request(url, payload, timeout):
    """Единая точка авторизации Gemini, поддерживает оба формата ключей."""
    if GEMINI_KEY.startswith("AQ."):
        return requests.post(
            url,
            headers={"Authorization": "Bearer " + GEMINI_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    return requests.post(url + "?key=" + GEMINI_KEY, json=payload, timeout=timeout)


def get_gemini_illustration_bytes(prompt, attempts=2):
    if not GEMINI_KEY:
        return None
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    for attempt in range(1, attempts + 1):
        try:
            r = gemini_auth_request(url, payload, timeout=30)
            r.raise_for_status()
            parts = r.json()["candidates"][0]["content"]["parts"]
            for part in parts:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    import base64
                    print("Image source: Gemini")
                    return base64.b64decode(inline["data"])
        except Exception as e:
            print("Gemini image attempt " + str(attempt) + " failed: " + str(e))
    return None


def get_illustration_bytes(text_prompt, scene_prompt):
    """Возвращает (image_bytes, used_gemini)."""
    if GEMINI_KEY:
        result = get_gemini_illustration_bytes(text_prompt)
        if result:
            return result, True
    result = get_pollinations_illustration_bytes(scene_prompt)
    if result:
        return result, False
    return None, False


def get_photo_bytes(query, attempts=2):
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

    for attempt in range(1, 2):
        try:
            seed = random.randint(1, 1000)
            r = requests.get("https://picsum.photos/seed/" + str(seed) + "/1080/1350", timeout=20)
            r.raise_for_status()
            print("Image source: Picsum")
            return r.content
        except Exception as e:
            print("Picsum attempt failed: " + str(e))

    return None


def draw_text_on_image(image_bytes, headline, illustrated=False):
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
    font = ImageFont.truetype(FONT_PATH, font_size)
    max_width = target_w - 120
    while True:
        bbox = draw.textbbox((0, 0), headline, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width or font_size <= 36:
            break
        font_size -= 4
        font = ImageFont.truetype(FONT_PATH, font_size)

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

def gemini_text_request(prompt):
    if not GEMINI_KEY:
        return None
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = gemini_auth_request(url, payload, timeout=15)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print("Gemini text unavailable: " + str(e))
        return None


def build_caption(slot, holiday_name=None):
    if holiday_name:
        prompt = ("Напиши короткое тёплое поздравление с праздником «" + holiday_name +
                   "» для Telegram-канала. 2-3 строки, искренне, с эмодзи. Только текст.")
        return gemini_text_request(prompt) or random.choice(HOLIDAY_CAPTION_FALLBACK)

    if slot in CAPTION_FALLBACK:
        prompts = {
            "morning": "Напиши тёплое пожелание доброго утра для Telegram-канала, 2 строки, с эмодзи. Только текст.",
            "day": "Напиши тёплое пожелание доброго дня для Telegram-канала, 2 строки, с эмодзи. Только текст.",
            "afternoon": "Напиши лёгкое пожелание хорошего полудня для Telegram-канала, 2 строки, с эмодзи. Только текст.",
            "evening": "Напиши тёплое пожелание доброго вечера для Telegram-канала, 2 строки, с эмодзи. Только текст.",
            "night": "Напиши тёплое пожелание спокойной ночи для Telegram-канала, 2 строки, с эмодзи. Только текст.",
        }
        return gemini_text_request(prompts[slot]) or random.choice(CAPTION_FALLBACK[slot])

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


# ───────────────────────── Построение контента под слот ─────────────────────────

def build_content_for_slot(slot):
    """Возвращает (headline, text_prompt_or_None, scene_prompt_or_None, query_or_None, holiday_name_or_None)."""
    if slot in ("holiday1", "holiday2"):
        h1, h2 = pick_two_distinct_holidays()
        chosen = h1 if slot == "holiday1" else h2
        if not chosen:
            return None
        holiday_name, _, base_query = chosen
        text_prompt = ('Greeting card illustration, large 3D puffy bubble letters spelling "' +
                        holiday_name + '" in Russian Cyrillic at the top, ' + base_query +
                        ', warm pastel colors, decorative festive border, digital art style')
        scene_prompt = (base_query + ", warm pastel colors, decorative festive border, " +
                         "digital art greeting card style, no text, no letters, no words")
        return holiday_name, text_prompt, scene_prompt, None, holiday_name

    if slot == "joke":
        idx = random.randint(0, len(JOKE_ART_PROMPTS) - 1)
        headline = random.choice(IMAGE_TEXT["joke"])
        return headline, JOKE_ART_PROMPTS[idx], JOKE_SCENE_PROMPTS[idx % len(JOKE_SCENE_PROMPTS)], None, None

    if slot == "evening":
        idx = random.randint(0, len(EVENING_ART_PROMPTS) - 1)
        headline = random.choice(IMAGE_TEXT["evening"])
        return headline, EVENING_ART_PROMPTS[idx], EVENING_SCENE_PROMPTS[idx % len(EVENING_SCENE_PROMPTS)], None, None

    if slot == "night":
        idx = random.randint(0, len(NIGHT_ART_PROMPTS) - 1)
        headline = random.choice(IMAGE_TEXT["night"])
        return headline, NIGHT_ART_PROMPTS[idx], NIGHT_SCENE_PROMPTS[idx % len(NIGHT_SCENE_PROMPTS)], None, None

    if slot == "morning":
        return random.choice(IMAGE_TEXT["morning"]), None, None, random.choice(MORNING_QUERIES), None
    if slot == "day":
        return random.choice(IMAGE_TEXT["day"]), None, None, random.choice(DAY_QUERIES), None
    if slot == "afternoon":
        return random.choice(IMAGE_TEXT["afternoon"]), None, None, random.choice(AFTERNOON_QUERIES), None
    if slot == "fact":
        return random.choice(IMAGE_TEXT["fact"]), None, None, random.choice(FACT_QUERIES), None

    return None


# ───────────────────────── Главная логика ─────────────────────────

def main():
    today = now_msk()
    hour = today.hour
    print("Bot run started (MSK): " + today.strftime("%d.%m.%Y %H:%M"))

    slot = SCHEDULE.get(hour)
    if not slot:
        print("No scheduled slot for hour " + str(hour) + " MSK. Nothing to do.")
        return

    print("Scheduled slot for this hour: " + slot)

    if already_posted_today(slot):
        print("Slot '" + slot + "' was already posted today. Skipping to avoid duplicate.")
        return

    content = build_content_for_slot(slot)
    if content is None:
        print("No content available for slot '" + slot + "' today (e.g. no holiday). Skipping.")
        return

    headline, text_prompt, scene_prompt, query, holiday_name = content
    illustrated = slot in ILLUSTRATED_SLOTS
    image_is_illustration_with_text = False

    if illustrated:
        print("Text prompt (Gemini): " + str(text_prompt))
        print("Scene prompt (Pollinations): " + str(scene_prompt))
        image_bytes, used_gemini = get_illustration_bytes(text_prompt, scene_prompt)
        if image_bytes and used_gemini:
            image_is_illustration_with_text = True
        if not image_bytes:
            print("Illustration failed, falling back to photo source.")
            illustrated = False
            image_bytes = get_photo_bytes(headline)
    else:
        print("Photo query: " + str(query))
        image_bytes = get_photo_bytes(query)

    caption = build_caption(slot, holiday_name)
    print("Caption: " + caption)

    if not image_bytes:
        print("No image available, sending text-only post.")
        if send_text(headline + "\n\n" + caption):
            mark_posted(slot)
        return

    if image_is_illustration_with_text:
        final_image = io.BytesIO(image_bytes)
    else:
        final_image = draw_text_on_image(image_bytes, headline, illustrated=illustrated)

    if send_photo(final_image, caption):
        mark_posted(slot)


if __name__ == "__main__":
    main()
