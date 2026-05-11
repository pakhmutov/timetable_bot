import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import json
import os

NVSK_TZ = timezone(timedelta(hours=5))


def now_nvsk() -> datetime:
    return datetime.now(NVSK_TZ)

BASE_URL = "https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/group"
CACHE_FILE = "timetable_cache.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

LESSON_TYPES = {
    "consul":  "📝 Консультация",
    "exam":    "📋 Экзамен",
    "lect":    "📖 Лекция",
    "seminar": "💬 Семинар",
    "lab":     "🔬 Лабораторная",
    "default": "📚 Занятие",
}

WEEKDAYS = {
    "Понедельник": "Понедельник",
    "Вторник":     "Вторник",
    "Среда":       "Среда",
    "Четверг":     "Четверг",
    "Пятница":     "Пятница",
    "Суббота":     "Суббота",
    "Воскресенье": "Воскресенье",
}


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def parse_html(html: str) -> dict:
    """
    Парсит HTML страницы и возвращает словарь:
    { "Понедельник 11 Мая": [{ time, subject, type, teacher, room }, ...], ... }
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="timetable")
    if not table:
        return {}

    result = {}
    current_day = None

    for element in table.children:
        if element.name == "thead":
            # Проверяем — это заголовок дня или строка "занятий нет"
            title_td = element.find("td", class_="title")
            if title_td:
                # Пропускаем div.today (метка "Сегодня"), берём первый без этого класса
                day_div = next(
                    (d for d in title_td.find_all("div", recursive=False)
                     if "today" not in (d.get("class") or [])),
                    None,
                )
                if day_div:
                    # На случай если .today вложен внутрь заголовка
                    nested = day_div.find("div", class_="today")
                    if nested:
                        nested.decompose()
                    current_day = " ".join(day_div.get_text().split())
                    result[current_day] = []

            # Проверяем "занятий нет"
            empty_td = element.find("td", class_="empty-day")
            if empty_td and current_day:
                result[current_day] = []  # пустой список = нет пар

        elif element.name == "tbody" and current_day is not None:
            rows = element.find_all("tr")
            for row in rows:
                lesson = parse_row(row)
                if lesson:
                    result[current_day].append(lesson)

    return result


def parse_row(row) -> dict | None:
    cells = row.find_all("td")
    if len(cells) < 4:
        return None

    # Тип пары из класса маркера (первая td)
    marker_td = cells[0]
    lesson_type = "default"
    for cls in (marker_td.get("class") or []):
        if cls in LESSON_TYPES:
            lesson_type = cls
            break

    # Время (вторая td)
    time_td = cells[1]
    time_div = time_td.find("div")
    time_text = time_div.get_text(strip=True).replace("\n", " ") if time_div else ""
    # Приводим "10:10 11:40" → "10:10–11:40"
    parts = time_text.split()
    if len(parts) == 2:
        time_text = f"{parts[0]}–{parts[1]}"

    # Предмет (третья td)
    subject_td = cells[2]
    # Убираем span с типом (КпЭ, Эк и т.д.)
    type_span = subject_td.find("span")
    if type_span:
        type_span.decompose()
    subject = subject_td.get_text(" ", strip=True).lstrip("- ").strip()

    # Преподаватель (четвёртая td)
    teacher_td = cells[3]
    teacher_div = teacher_td.find("div", class_="teacher")
    teacher = teacher_div.get_text(strip=True) if teacher_div else ""
    # Убираем должность в скобках
    who_span = teacher_td.find("span", class_="who_is")
    if who_span:
        role = who_span.get_text(strip=True)
        teacher = teacher.replace(role, "").strip()

    # Кабинет (последняя td)
    room_td = cells[-1]
    room = room_td.get_text(strip=True)

    if not subject:
        return None

    return {
        "time":    time_text,
        "subject": subject,
        "type":    lesson_type,
        "teacher": teacher,
        "room":    room,
    }


def format_day(day_name: str, lessons: list) -> str:
    header = f"📅 *{day_name}*\n{'─' * 20}\n"

    if not lessons:
        return header + "😴 Занятий нет"

    parts = []
    for l in lessons:
        lesson_type = LESSON_TYPES.get(l["type"], LESSON_TYPES["default"])
        text = (
            f"🕐 {l['time']}\n"
            f"{lesson_type}\n"
            f"*{l['subject']}*\n"
            f"👨‍🏫 {l['teacher']}\n"
            f"🚪 {l['room']}"
        )
        parts.append(text)

    return header + "\n\n".join(parts)


def get_week(group_id: str, date: datetime = None) -> dict:
    """Возвращает расписание на неделю как словарь {день: [пары]}"""
    if date is None:
        date = now_nvsk()

    date_str = date.strftime("%d_%m_%Y")
    cache_key = f"{group_id}_{date_str}"
    cache = load_cache()

    try:
        url = f"{BASE_URL}/{group_id}//0/?date={date_str}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        data = parse_html(resp.text)

        if data:
            cache[cache_key] = data
            save_cache(cache)

        return data, False  # False = не из кэша

    except Exception:
        if cache_key in cache:
            return cache[cache_key], True  # True = из кэша
        return {}, True


def get_day_text(group_id: str, date: datetime = None) -> str:
    """Возвращает готовый текст для одного дня"""
    if date is None:
        date = now_nvsk()

    week_data, from_cache = get_week(group_id, date)

    if not week_data:
        return "❌ Сайт недоступен и кэша нет. Попробуй позже."

    # Ищем нужный день по числу и месяцу
    day_num = date.strftime("%-d")  # "11"
    month = date.strftime("%B")     # нужен русский месяц

    RU_MONTHS = {
        "January": "Января", "February": "Февраля", "March": "Марта",
        "April": "Апреля", "May": "Мая", "June": "Июня",
        "July": "Июля", "August": "Августа", "September": "Сентября",
        "October": "Октября", "November": "Ноября", "December": "Декабря",
    }
    ru_month = RU_MONTHS.get(month, month)

    # Ключи вида "Вторник 12 Мая"
    target = None
    for key in week_data:
        parts = key.split()
        if len(parts) >= 3 and parts[1] == day_num and parts[2] == ru_month:
            target = key
            break

    if target is None:
        return f"❌ День {date.strftime('%d.%m.%Y')} не найден в расписании."

    text = format_day(target, week_data[target])

    if from_cache:
        text += "\n\n⚠️ _Данные из кэша — сайт недоступен_"

    return text


def get_week_text(group_id: str, date: datetime = None) -> str:
    """Возвращает расписание на всю неделю"""
    if date is None:
        date = now_nvsk()

    week_data, from_cache = get_week(group_id, date)

    if not week_data:
        return "❌ Сайт недоступен и кэша нет. Попробуй позже."

    days_text = []
    for day_name, lessons in week_data.items():
        days_text.append(format_day(day_name, lessons))

    text = "\n\n".join(days_text)

    if from_cache:
        text += "\n\n⚠️ _Данные из кэша — сайт недоступен_"

    return text
