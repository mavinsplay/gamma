import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), "gamma"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gamma.settings")
import django
django.setup()

from user.models import Profile
from asgiref.sync import sync_to_async

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", 0))

if not BOT_TOKEN or BOT_TOKEN == "1234567890:YOUR_BOT_TOKEN_HERE":
    raise ValueError("Необходимо указать настоящий BOT_TOKEN в файле .env!")

if not WEBAPP_URL or WEBAPP_URL == "https://ваша-ссылка-на-приложение.com":
    raise ValueError("Необходимо указать настоящий WEBAPP_URL в файле .env!")

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    web_app_btn = InlineKeyboardButton(
        text="🚀 Открыть VPN",
        web_app=WebAppInfo(url=WEBAPP_URL),
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[web_app_btn]])
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Добро пожаловать в наш VPN сервис. Нажми на кнопку ниже, "
        f"чтобы открыть панель управления."
    )
    await message.answer(welcome_text, reply_markup=markup)

@dp.message(Command("broadcast"), F.from_user.id == ADMIN_ID)
async def broadcast_command(message: types.Message, state: FSMContext):
    await message.answer(
        "📢 <b>Режим рассылки</b>\n\n"
        "Отправьте сообщение (текст, фото, кружочек и т.д.). Оно будет разослано всем пользователям с включенными уведомлениями.\n"
        "Для отмены напишите /cancel",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastState.waiting_for_message)

@dp.message(Command("cancel"), F.from_user.id == ADMIN_ID)
async def cancel_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Рассылка отменена.")

@sync_to_async
def get_users_for_broadcast():
    return list(Profile.objects.filter(notifications_enabled=True).values_list('telegram_id', flat=True))

@dp.message(BroadcastState.waiting_for_message, F.from_user.id == ADMIN_ID)
async def process_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("⏳ Начинаю рассылку...")
    
    users = await get_users_for_broadcast()
    count = 0
    
    for tg_id in users:
        try:
            await message.copy_to(chat_id=tg_id, reply_markup=None)
            count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logging.error(f"Failed to send to {tg_id}: {e}")
            
    await message.answer(f"✅ Рассылка завершена!\nДоставлено: <b>{count}</b> пользователям.", parse_mode="HTML")

from connect.services.remnawave import RemnawaveClient
from datetime import datetime, timedelta, timezone

async def subscription_reminder_task():
    while True:
        try:
            users = await sync_to_async(list)(Profile.objects.filter(payment_reminder_enabled=True, tarif__isnull=False).select_related("tarif"))
            if users:
                client = RemnawaveClient()
                try:
                    for profile in users:
                        rw_user = await client.get_user_by_tgid(profile.telegram_id)
                        if isinstance(rw_user, list):
                            rw_user = rw_user[0] if len(rw_user) > 0 else None
                            
                        if rw_user and rw_user.get("expireAt"):
                            expire_str = rw_user["expireAt"].replace("Z", "+00:00")
                            try:
                                expire_dt = datetime.fromisoformat(expire_str)
                                delta = expire_dt - datetime.now(timezone.utc)
                                print(delta.days)
                                # Если осталось от 2 до 3 дней
                                if 1 <= delta.days < 3:
                                    ds = "день" if delta.days == 1 else "дня" if delta.days == 2 else "дней"
                                    text = f"🔔 <b>Напоминание</b>\n\nВаша подписка на тариф <b>{profile.tarif.name}</b> истекает примерно через {delta.days} {ds}!\n\nПожалуйста, продлите подписку в панели управления."
                                    await bot.send_message(profile.telegram_id, text, parse_mode="HTML")
                            except ValueError:
                                pass
                finally:
                    await client.close()
        except Exception as e:
            logging.error(f"Error in reminder task: {e}")
            
        await asyncio.sleep(24 * 3600)  # Check once a day

async def main() -> None:
    logging.info("Бот успешно запущен и готов к работе!")
    asyncio.create_task(subscription_reminder_task())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен.")
