# -*- coding: utf-8 -*-
"""
Telegram-бот "Открытки с душой" — версия с днём недели и только иллюстрациями.
Запускается каждый час. Сам определяет слот по московскому времени.
"""
import os, sys, io, random, urllib.parse, base64
from datetime import datetime, timedelta, timezone
import requests
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL_ID     = os.environ.get("CHANNEL_ID", "")
UNSPLASH_KEY   = os.environ.get("UNSPLASH_KEY", "")
GEMINI_KEY     = os.environ.get("GEMINI_KEY", "")

MOSCOW_TZ = timezone(timedelta(hours=3))
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans-Bold.ttf")
LOG_FILE  = os.path.join(os.path.dirname(__file__), "posted_log.txt")

# Расписание: московский час -> слот
SCHEDULE = {
    7:  "morning",
    10: "holiday",
    12: "day",
    14: "joke",
    17: "afternoon",
    19: "evening",
    22: "night",
}

# Дни недели на русском
WEEKDAYS = ["понедельника", "вторника", "среды", "четверга", "пятницы", "субботы", "воскресенья"]
WEEKDAYS_ACC = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]

def now_msk():
    return datetime.now(MOSCOW_TZ)

def get_weekday_name():
    return WEEKDAYS[now_msk().weekday()]

def get_season():
    m = now_msk().month
    if m in (12, 1, 2): return "winter"
    if m in (3, 4, 5):  return "spring"
    if m in (6, 7, 8):  return "summer"
    return "autumn"

# Сезонные темы для фона открытки
SEASON_THEMES = {
    "winter": ["cozy winter cottage snow candles warm light", "snowy forest magical winter fairy tale", "winter morning frost sparkling snow cozy"],
    "spring": ["spring flowers blooming garden butterflies", "spring morning cherry blossom pink flowers", "fresh spring meadow green flowers sunshine"],
    "summer": ["summer sunflowers bright warm sunshine", "summer watermelon flowers bright colorful", "summer garden roses colorful warm light"],
    "autumn": ["autumn leaves cozy cottage warm colors", "autumn forest golden leaves sunlight", "autumn harvest apples cozy warm colors"],
}

# Подписи под постом (короткие, в стиле референса)
CAPTION_MORNING = [
    "Хорошего дня! ☀️", "Пусть день будет добрым! 🌸",
    "Улыбнитесь — всё будет хорошо! ✨", "Доброго утра всем! 🌿",
]
CAPTION_DAY = [
    "Хорошего настроения! 🌸", "Пусть день удастся! ☀️",
    "Заряжайтесь позитивом! ✨", "Хорошего дня, друзья! 🌼",
]
CAPTION_AFTERNOON = [
    "Самое время отдохнуть! ☕", "Хорошего вечера впереди! 🌸",
    "Пусть всё идёт хорошо! ✨",
]
CAPTION_EVENING = [
    "Приятного вечера! 🌙", "Уютного вечера! 🕯️",
    "Пусть вечер будет тихим и добрым! 🌸",
]
CAPTION_NIGHT = [
    "Сладких снов! 🌙✨", "Спите крепко! 😴",
    "Пусть ночь будет тихой! 🌟",
]
CAPTION_HOLIDAY = [
    "С праздником! 🎉", "Поздравляем всех причастных! 🎊",
    "Пусть праздник принесёт радость! 🌸",
]
CAPTION_JOKE = [
    "😄", "Улыбнитесь! 😊", "Хорошего настроения! 😄",
]

# Праздники (месяц, день) -> название
HOLIDAYS = {
    (1, 1): "Новый год", (1, 7): "Рождество Христово",
    (1, 13): "Старый Новый год", (1, 19): "Крещение Господне",
    (1, 25): "День студента",
    (2, 14): "День святого Валентина", (2, 23): "День защитника Отечества",
    (3, 1): "Всемирный день кошек", (3, 8): "Международный женский день",
    (3, 17): "День святого Патрика", (3, 20): "Международный день счастья",
    (4, 1): "День смеха", (4, 12): "День космонавтики",
    (5, 1): "Праздник Весны и Труда", (5, 9): "День Победы",
    (5, 15): "Международный день семьи",
    (6, 1): "День защиты детей", (6, 12): "День России",
    (7, 8): "День семьи любви и верности",
    (8, 1): "День Гранёного стакана", (8, 2): "День ВДВ",
    (8, 11): "День строителя", (8, 19): "Яблочный Спас",
    (9, 1): "День знаний", (9, 27): "Всемирный день туризма",
    (10, 1): "Международный день музыки", (10, 4): "Всемирный день животных",
    (10, 5): "День учителя", (10, 31): "Хэллоуин",
    (11, 4): "День народного единства", (11, 27): "День матери",
    (12, 19): "Никола Зимний", (12, 25): "Католическое Рождество",
    (12, 31): "Канун Нового года",
}

def get_today_holiday():
    today = now_msk()
    return HOLIDAYS.get((today.month, today.day))


# ─── Журнал публикаций ───

def already_posted_today(slot):
    if not os.path.exists(LOG_FILE):
        return False
    key = now_msk().strftime("%Y-%m-%d") + ":" + slot
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return key in [l.strip() for l in f]
    except:
        return False

def mark_posted(slot):
    key = now_msk().strftime("%Y-%m-%d") + ":" + slot
    try:
        lines = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
        lines.append(key)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines[-30:]) + "\n")
        print("Logged: " + key)
    except Exception as e:
        print("Log write error: " + str(e))


# ─── Генерация картинки ───

def build_prompt(slot, headline, holiday_name=None):
    """Строим промпт для Pollinations с текстом прямо в картинке."""
    season = get_season()
    bg = random.choice(SEASON_THEMES[season])

    if slot == "morning":
        return (
            f'Cute cartoon greeting card illustration, '
            f'beautiful handwritten calligraphy text "{headline}" in Russian Cyrillic, '
            f'elegant cursive font with shadow effect, '
            f'{bg}, soft warm pastel colors, cozy atmosphere, '
            f'decorative floral border, digital art style, no extra text'
        )
    elif slot in ("evening", "night"):
        return (
            f'Cute cartoon greeting card illustration, '
            f'glowing handwritten text "{headline}" in Russian Cyrillic, '
            f'elegant script font with golden glow effect, '
            f'{bg}, soft dreamy colors, magical atmosphere, '
            f'stars and moon elements, digital art style, no extra text'
        )
    elif slot == "holiday" and holiday_name:
        return (
            f'Beautiful festive greeting card illustration, '
            f'elegant decorative text "{holiday_name}" in Russian Cyrillic at top, '
            f'festive {bg}, bright celebratory colors, '
            f'decorative ornamental border with flowers, digital art style, no extra text'
        )
    elif slot == "joke":
        return (
            f'Cute funny cartoon greeting card, '
            f'bold colorful text "{headline}" in Russian Cyrillic, '
            f'funny cartoon character, bright cheerful colors, '
            f'playful style, no extra text'
        )
    else:
        return (
            f'Cute cartoon greeting card illustration, '
            f'beautiful handwritten text "{headline}" in Russian Cyrillic, '
            f'{bg}, soft pastel colors, warm atmosphere, '
            f'decorative floral elements, digital art style, no extra text'
        )

def get_pollinations_image(prompt, attempts=3):
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999999)
    url = (f"https://image.pollinations.ai/prompt/{encoded}"
           f"?width=1080&height=1350&model=flux&nologo=true&seed={seed}")
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=45)
            r.raise_for_status()
            if len(r.content) > 5000:
                print("Image: Pollinations OK")
                return r.content
            print(f"Pollinations: small response attempt {attempt}")
        except Exception as e:
            print(f"Pollinations attempt {attempt} failed: {e}")
    return None

def get_gemini_image(prompt, attempts=2):
    if not GEMINI_KEY:
        return None
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    for attempt in range(1, attempts + 1):
        try:
            if GEMINI_KEY.startswith("AQ."):
                r = requests.post(url, headers={"Authorization": "Bearer " + GEMINI_KEY, "Content-Type": "application/json"}, json=payload, timeout=35)
            else:
                r = requests.post(url + "?key=" + GEMINI_KEY, json=payload, timeout=35)
            r.raise_for_status()
            parts = r.json()["candidates"][0]["content"]["parts"]
            for part in parts:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    print("Image: Gemini OK")
                    return base64.b64decode(inline["data"])
        except Exception as e:
            print(f"Gemini attempt {attempt} failed: {e}")
    return None

def add_text_overlay(image_bytes, headline):
    """Запасной вариант — наложение текста через PIL если модель не нарисовала."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    # Resize to portrait
    target_w, target_h = 1080, 1350
    r = img.width / img.height
    if r > target_w / target_h:
        new_h, new_w = target_h, int(target_h * r)
    else:
        new_w, new_h = target_w, int(target_w / r)
    img = img.resize((new_w, new_h))
    img = img.crop(((new_w - target_w)//2, (new_h - target_h)//2,
                    (new_w - target_w)//2 + target_w, (new_h - target_h)//2 + target_h))
    # Gradient overlay at top
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    gh = int(target_h * 0.28)
    for i in range(gh):
        d.line([(0,i),(target_w,i)], fill=(0,0,0,int(160*(1-i/gh))))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)
    fs = 80
    font = ImageFont.truetype(FONT_PATH, fs)
    while draw.textbbox((0,0), headline, font=font)[2] > target_w - 80 and fs > 36:
        fs -= 4
        font = ImageFont.truetype(FONT_PATH, fs)
    bb = draw.textbbox((0,0), headline, font=font)
    x = (target_w - (bb[2]-bb[0])) / 2
    y = gh * 0.45 - (bb[3]-bb[1]) / 2
    draw.text((x+3, y+3), headline, font=font, fill=(0,0,0,160))
    draw.text((x, y), headline, font=font, fill=(255,255,255,255))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92)
    out.seek(0)
    return out


# ─── Отправка ───

def send_photo(image_file, caption):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
            data={"chat_id": CHANNEL_ID, "caption": caption},
            files={"photo": ("card.jpg", image_file, "image/jpeg")},
            timeout=40,
        )
        r.raise_for_status()
        print("Published!")
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


# ─── Главная логика ───

def main():
    today = now_msk()
    print(f"Bot started (MSK): {today.strftime('%d.%m.%Y %H:%M')}")

    slot = SCHEDULE.get(today.hour)
    if not slot:
        print(f"No slot for hour {today.hour} MSK. Nothing to do.")
        return

    print(f"Slot: {slot}")

    if already_posted_today(slot):
        print(f"Slot '{slot}' already posted today. Skipping.")
        return

    weekday = get_weekday_name()
    holiday_name = get_today_holiday()

    # Определяем заголовок (текст на картинке)
    if slot == "morning":
        headline = random.choice([
            f"С добрым утром {weekday}!",
            f"Доброе утро {weekday}!",
            f"Доброе утро!",
        ])
        caption = random.choice(CAPTION_MORNING)

    elif slot == "holiday":
        if not holiday_name:
            print("No holiday today, skipping holiday slot.")
            mark_posted(slot)  # помечаем чтобы не пытаться снова
            return
        headline = holiday_name
        caption = random.choice(CAPTION_HOLIDAY)

    elif slot == "day":
        headline = random.choice([
            f"Добрый день!",
            f"Хорошего {weekday}!",
            f"Добрый день, друзья!",
        ])
        caption = random.choice(CAPTION_DAY)

    elif slot == "joke":
        headline = random.choice(["Улыбнись!", "Юмор дня", "Смейтесь!"])
        caption = random.choice(CAPTION_JOKE)

    elif slot == "afternoon":
        headline = random.choice([
            "Хорошего вечера!",
            "Добрый день!",
            "Приятного вечера!",
        ])
        caption = random.choice(CAPTION_AFTERNOON)

    elif slot == "evening":
        headline = random.choice([
            f"Доброго вечера {weekday}а!",
            "Хорошего вечера!",
            "Доброго вечера!",
        ])
        caption = random.choice(CAPTION_EVENING)

    elif slot == "night":
        headline = random.choice([
            f"Доброй ночи {weekday}а!",
            "Спокойной ночи!",
            "Сладких снов!",
            "Доброй ночи!",
        ])
        caption = random.choice(CAPTION_NIGHT)

    else:
        return

    # Строим промпт
    prompt = build_prompt(slot, headline, holiday_name if slot == "holiday" else None)
    print(f"Prompt: {prompt[:100]}...")

    # Пробуем Gemini, потом Pollinations
    image_bytes = get_gemini_image(prompt)
    used_gemini = image_bytes is not None
    if not image_bytes:
        image_bytes = get_pollinations_image(prompt)

    if not image_bytes:
        print("All image sources failed.")
        return

    # Если Gemini — текст уже в картинке; если Pollinations — добавляем PIL-overlay как страховку
    if used_gemini:
        final = io.BytesIO(image_bytes)
    else:
        final = add_text_overlay(image_bytes, headline)

    if send_photo(final, caption):
        mark_posted(slot)


if __name__ == "__main__":
    main()
