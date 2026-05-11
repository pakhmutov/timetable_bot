import os
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from parser import get_day_text, get_week_text

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID", "11854")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Вчера",  callback_data="day_-1"),
            InlineKeyboardButton("📅 Сегодня", callback_data="day_0"),
            InlineKeyboardButton("Завтра ▶️",  callback_data="day_1"),
        ],
        [
            InlineKeyboardButton("📆 Вся неделя", callback_data="week"),
        ],
    ])


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет\\! Я бот расписания\\.\n\nВыбери что показать:",
        parse_mode="MarkdownV2",
        reply_markup=main_keyboard(),
    )


async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = get_day_text(GROUP_ID, datetime.today())
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=main_keyboard()
    )


async def cmd_week(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = get_week_text(GROUP_ID, datetime.today())
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=main_keyboard()
    )


async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("day_"):
        delta = int(data.split("_")[1])
        date = datetime.today() + timedelta(days=delta)
        text = get_day_text(GROUP_ID, date)
    elif data == "week":
        text = get_week_text(GROUP_ID, datetime.today())
    else:
        return

    try:
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=main_keyboard()
        )
    except Exception:
        # Если текст не изменился — телеграм бросает ошибку, игнорируем
        pass


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CallbackQueryHandler(button))

    logger.info("Бот запущен. GROUP_ID=%s", GROUP_ID)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
