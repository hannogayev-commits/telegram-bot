"""Бот «Ногай тили»: приветствие, кнопки снизу, напоминания об учёбе.

Запуск:
    pip install aiogram tzdata
    BOT_TOKEN=123:ABC python bot.py
"""
import asyncio
import logging
import os
import random
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo,
)

TOKEN = os.environ["BOT_TOKEN"]
URL = os.getenv("WEBAPP_URL", "https://hannogayev-commits.github.io/Nogai/")
TZ = ZoneInfo(os.getenv("TZ_NAME", "Europe/Moscow"))
TIMES = ["09:00", "13:00", "19:00", "21:00"]

REMINDERS = [
    "Яхшыма! 🌿 Три минуты ногайского сегодня, и огонь 🔥 не погаснет.",
    "Яхшыма! Одно маленькое занятие в день лучше, чем час раз в месяц.",
    "Пора на урок! Сегодня можно выучить пару новых слов 📖",
    "Не теряй серию дней 🔥 Заходи на пару минут.",
]

db = sqlite3.connect("bot.db")
db.execute(
    "CREATE TABLE IF NOT EXISTS users "
    "(id INTEGER PRIMARY KEY, remind TEXT, last_sent TEXT)"
)
db.commit()

dp = Dispatcher()


def menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [KeyboardButton(text="📖 Учить", web_app=WebAppInfo(url=URL)),
             KeyboardButton(text="🔔 Напоминание")],
            [KeyboardButton(text="👋 Яхшыма"), KeyboardButton(text="🙏 Савбол")],
            [KeyboardButton(text="ℹ️ О проекте"), KeyboardButton(text="💬 Помощь")],
        ],
    )


def times_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data="t:" + t) for t in TIMES],
        [InlineKeyboardButton(text="Выключить", callback_data="t:off")],
    ])


def ensure_user(uid: int) -> None:
    db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (uid,))
    db.commit()


@dp.message(CommandStart())
async def start(m: Message):
    ensure_user(m.from_user.id)
    await m.answer(
        "Яхшыма! 🌿 Это «Ногай тили»: короткие уроки ногайского языка.\n"
        "Нажми «📖 Учить», чтобы начать.",
        reply_markup=menu(),
    )
    await m.answer("Во сколько напоминать об уроке?", reply_markup=times_kb())


@dp.message(F.text == "🔔 Напоминание")
async def remind_menu(m: Message):
    ensure_user(m.from_user.id)
    row = db.execute("SELECT remind FROM users WHERE id=?", (m.from_user.id,)).fetchone()
    now = f"Сейчас: {row[0]}" if row and row[0] else "Сейчас: выключено"
    await m.answer(f"{now} (время московское).\nВыбери, когда напоминать:", reply_markup=times_kb())


@dp.callback_query(F.data.startswith("t:"))
async def set_time(c: CallbackQuery):
    value = c.data[2:]
    ensure_user(c.from_user.id)
    db.execute("UPDATE users SET remind=? WHERE id=?",
               (None if value == "off" else value, c.from_user.id))
    db.commit()
    await c.message.edit_text(
        "Напоминания выключены." if value == "off"
        else f"Готово! Буду напоминать каждый день в {value}."
    )
    await c.answer()


@dp.message(F.text == "👋 Яхшыма")
async def salam(m: Message):
    await m.answer(random.choice(["Яхшыма! 🌿", "Яхшыма, рад тебя видеть! 🌿"]))


@dp.message(F.text == "🙏 Савбол")
async def rahmet(m: Message):
    await m.answer("Савбол! 🙏 Заходи учиться каждый день.")


@dp.message(F.text == "ℹ️ О проекте")
async def about(m: Message):
    await m.answer(
        "Бесплатное приложение для тех, кто хочет вернуть ногайский язык.\n"
        "Слова взяты из русско-ногайского словаря А. Баскакова (1956).\n"
        "Достаточно 3-5 минут в день."
    )


@dp.message(F.text == "💬 Помощь")
async def help_(m: Message):
    await m.answer(
        "«📖 Учить» открывает уроки.\n"
        "«🔔 Напоминание» включает, меняет или выключает напоминания.\n"
        "Если что-то не работает, напиши об этом сюда."
    )


@dp.message()
async def fallback(m: Message):
    await m.answer("Выбери кнопку внизу 👇", reply_markup=menu())


async def reminder_loop(bot: Bot) -> None:
    while True:
        now = datetime.now(TZ)
        hm, day = now.strftime("%H:%M"), now.strftime("%Y-%m-%d")
        rows = db.execute(
            "SELECT id FROM users WHERE remind=? AND (last_sent IS NULL OR last_sent!=?)",
            (hm, day),
        ).fetchall()
        for (uid,) in rows:
            try:
                await bot.send_message(
                    uid, random.choice(REMINDERS),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="📖 Открыть урок", web_app=WebAppInfo(url=URL))
                    ]]),
                )
                db.execute("UPDATE users SET last_sent=? WHERE id=?", (day, uid))
            except TelegramForbiddenError:  # человек заблокировал бота
                db.execute("UPDATE users SET remind=NULL WHERE id=?", (uid,))
            except Exception:
                logging.exception("не удалось отправить %s", uid)
            db.commit()
            await asyncio.sleep(0.05)
        await asyncio.sleep(60 - datetime.now(TZ).second)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(TOKEN)
    task = asyncio.create_task(reminder_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
