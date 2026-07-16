import asyncio
from datetime import datetime, timezone
import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "gamma"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gamma.settings")

from aiogram import Bot, Dispatcher, F, types  # noqa: E402
from aiogram.exceptions import TelegramNetworkError  # noqa: E402
from aiogram.filters import Command, CommandStart  # noqa: E402
from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.state import State, StatesGroup  # noqa: E402
from aiogram.types import (  # noqa: E402
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from asgiref.sync import sync_to_async  # noqa: E402
import django  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

django.setup()

from connect.services.remnawave import RemnawaveClient  # noqa: E402
from user.models import Profile  # noqa: E402

__all__ = ()

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


SUPPORT_USERNAME = os.getenv(
    "SUPPORT_USERNAME",
    "@o3o20",
).lstrip("@")


@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    status_url = f"{WEBAPP_URL}?tab=connection"
    support_url = f"https://t.me/{SUPPORT_USERNAME}"

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Личный кабинет",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📡 Статус серверов",
                    web_app=WebAppInfo(url=status_url),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🆘 Чат с поддержкой",
                    url=support_url,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📜 Политика конфиденциальности",
                    url="https://telegra.ph/Politika-konfidencialnosti-06-21-31",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📜 Пользовательское соглашение",
                    url="https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19",
                ),
            ],
        ],
    )

    await message.answer(
        f"✨ <b>Добро пожаловать в Gamma</b>\n\n"
        f"Привет, {message.from_user.first_name}! 👋\n"
        f"Быстрый и надёжный ускоритель для ежедневного использования.\n\n"
        f"• 🚀 <b>Скорость</b> без ограничений\n"
        f"• 🌍 <b>Серверы</b> в разных странах\n"
        f"• 🔒 <b>Защита</b> ваших данных\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=markup,
    )


@dp.message(Command("broadcast"), F.from_user.id == ADMIN_ID)
async def broadcast_command(message: types.Message, state: FSMContext):
    await message.answer(
        "📢 <b>Режим рассылки</b>\n\n"
        "Отправьте сообщение (текст, фото, кружочек и т.д.). "
        "Оно будет разослано всем пользователям "
        "с включенными уведомлениями.\n"
        "Для отмены напишите /cancel",
        parse_mode="HTML",
    )
    await state.set_state(BroadcastState.waiting_for_message)


@dp.message(Command("cancel"), F.from_user.id == ADMIN_ID)
async def cancel_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Рассылка отменена.")


@sync_to_async
def get_users_for_broadcast():
    return list(
        Profile.objects.filter(notifications_enabled=True).values_list(
            "telegram_id",
            flat=True,
        ),
    )


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

    await message.answer(
        f"✅ Рассылка завершена!\nДоставлено: <b>{count}</b> пользователям.",
        parse_mode="HTML",
    )


async def subscription_reminder_task():
    while True:
        try:
            users = await sync_to_async(list)(
                Profile.objects.filter(
                    payment_reminder_enabled=True,
                    tarif__isnull=False,
                ).select_related("tarif"),
            )
            if users:
                client = RemnawaveClient()
                try:
                    for profile in users:
                        rw_user = await client.get_user_by_tgid(
                            profile.telegram_id,
                        )
                        if isinstance(rw_user, list):
                            rw_user = rw_user[0] if len(rw_user) > 0 else None

                        if rw_user and rw_user.get("expireAt"):
                            expire_str = rw_user["expireAt"].replace(
                                "Z",
                                "+00:00",
                            )
                            try:
                                expire_dt = datetime.fromisoformat(expire_str)
                                delta = expire_dt - datetime.now(timezone.utc)
                                # noqa: T201

                                # Подписка активна — сбрасываем флаг
                                if delta.days > 0:
                                    if (
                                        profile.subscription_expired_notification_sent  # noqa: E501
                                    ):
                                        profile.subscription_expired_notification_sent = (  # noqa: E501
                                            False
                                        )
                                        await sync_to_async(profile.save)()

                                # 1-2 дня до конца — напоминание
                                elif 1 <= delta.days < 3:
                                    ds = "день" if delta.days == 1 else "дня"
                                    text = (
                                        "🔔 <b>Напоминание</b>\n\n"
                                        f"Ваша подписка на тариф "
                                        f"<b>{profile.tarif.name}</b> "
                                        f"истекает примерно через "
                                        f"{delta.days} {ds}!\n\n"
                                        "Пожалуйста, продлите подписку "
                                        "в панели управления."
                                    )
                                    await bot.send_message(
                                        profile.telegram_id,
                                        text,
                                        parse_mode="HTML",
                                    )

                                # Подписка истекла — отправляем один раз
                                elif (
                                    delta.days <= 0
                                    and not profile.subscription_expired_notification_sent  # noqa: E501
                                ):
                                    text = (
                                        "🔔 <b>Напоминание</b>\n\n"
                                        f"Ваша подписка на тариф "
                                        f"<b>{profile.tarif.name}</b> "
                                        f"истекла!\n\n"
                                        "Пожалуйста, продлите подписку "
                                        "в панели управления."
                                    )
                                    await bot.send_message(
                                        profile.telegram_id,
                                        text,
                                        parse_mode="HTML",
                                    )
                                    # Отмечаем что уведомление отправлено
                                    profile.subscription_expired_notification_sent = (  # noqa: E501
                                        True
                                    )
                                    await sync_to_async(profile.save)()
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

    retry_delay = 5
    while True:
        try:
            await dp.start_polling(bot)
            break
        except TelegramNetworkError as e:
            logging.warning(
                "Не удалось подключиться к Telegram API: %s. "
                "Повтор через %d сек.",
                e,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 120)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен.")
