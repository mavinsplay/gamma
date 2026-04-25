import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import WebAppInfo
from dotenv import load_dotenv

__all__ = [
    "BOT_TOKEN",
    "WEBAPP_URL",
]

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")

if not BOT_TOKEN or BOT_TOKEN == "1234567890:YOUR_BOT_TOKEN_HERE":
    raise ValueError("Необходимо указать настоящий BOT_TOKEN в файле .env!")

if not WEBAPP_URL or WEBAPP_URL == "https://ваша-ссылка-на-приложение.com":
    raise ValueError("Необходимо указать настоящий WEBAPP_URL в файле .env!")

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """
    Этот хендлер срабатывает на команду /start.
    Отправляет приветственное сообщение с кнопкой Mini App.
    """
    web_app_btn = InlineKeyboardButton(
        text="🚀 Открыть VPN",
        web_app=WebAppInfo(url=WEBAPP_URL),
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[web_app_btn]])
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Добро пожаловать в наш VPN сервис. Нажми на кнопку ниже, "
        f"чтобы открыть панель управления, выбрать тариф или "
        f"посмотреть настройки своего профиля."
    )
    await message.answer(welcome_text, reply_markup=markup)


async def main() -> None:
    logging.info("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен.")
