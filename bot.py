import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "gamma"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gamma.settings")

from aiogram import BaseMiddleware, Bot, Dispatcher, F, types  # noqa: E402
from aiogram.exceptions import (  # noqa: E402
    TelegramAPIError,
    TelegramNetworkError,
)
from aiogram.filters import Command, CommandStart  # noqa: E402
from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.state import State, StatesGroup  # noqa: E402
from aiogram.types import (  # noqa: E402
    FSInputFile,
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
REQUIRED_CHANNEL_ID = os.getenv("REQUIRED_CHANNEL_ID", "").strip()
REQUIRED_CHANNEL_URL = os.getenv("REQUIRED_CHANNEL_URL", "").strip()

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

# Иконки кнопок (custom emoji id). Пустое значение — без иконки.
ICON_PERSONAL_CABINET = os.getenv("ICON_PERSONAL_CABINET") or None
ICON_SERVER_STATUS = os.getenv("ICON_SERVER_STATUS") or None
ICON_SUPPORT = os.getenv("ICON_SUPPORT") or None
ICON_CHANNEL = os.getenv("ICON_CHANNEL") or None


WELCOME_PHOTO_PATH = (
    Path(__file__).resolve().parent
    / "gamma"
    / "static_dev"
    / "favicons"
    / "web-app-manifest-512x512.png"
)


def _button(
    text: str,
    icon_custom_emoji_id: str | None = None,
    **kwargs,
) -> InlineKeyboardButton:
    """Собирает InlineKeyboardButton, подставляя icon_custom_emoji_id
    только если он реально задан (чтобы не слать пустое поле)."""
    if icon_custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id

    return InlineKeyboardButton(text=text, **kwargs)


def build_welcome_markup(ref_code=None) -> InlineKeyboardMarkup:
    status_url = f"{WEBAPP_URL}?tab=connection"
    support_url = f"https://t.me/{SUPPORT_USERNAME}"
    cabinet_url = f"{WEBAPP_URL}?ref={ref_code}" if ref_code else WEBAPP_URL

    bottom_row = [
        _button(
            "Поддержка",
            icon_custom_emoji_id=ICON_SUPPORT,
            url=support_url,
        ),
    ]
    if REQUIRED_CHANNEL_URL:
        bottom_row.append(
            _button(
                "Канал",
                icon_custom_emoji_id=ICON_CHANNEL,
                url=REQUIRED_CHANNEL_URL,
            ),
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    "Личный кабинет",
                    icon_custom_emoji_id=ICON_PERSONAL_CABINET,
                    style="primary",  # синяя
                    web_app=WebAppInfo(url=cabinet_url),
                ),
            ],
            [
                _button(
                    "Статус серверов",
                    icon_custom_emoji_id=ICON_SERVER_STATUS,
                    style="success",  # зелёная
                    web_app=WebAppInfo(url=status_url),
                ),
            ],
            bottom_row,  # Поддержка | Канал — обычного цвета
        ],
    )


def build_welcome_text(first_name: str) -> str:
    return (
        "<b>Ɣ Gamma</b>\n"
        "<b>Безопасность. Скорость. Качество.</b>\n\n"
        "<b>Как подключиться?</b>\n"
        "• Нажми кнопку «Личный кабинет»\n"
        "• Выбери тариф\n"
        "• Следуй короткой инструкции\n\n"
    )


async def send_welcome(
    message: types.Message,
    first_name: str,
    ref_code=None,
) -> None:
    text = build_welcome_text(first_name)
    markup = build_welcome_markup(ref_code=ref_code)
    if WELCOME_PHOTO_PATH.is_file():
        try:
            await message.answer_photo(
                photo=FSInputFile(WELCOME_PHOTO_PATH),
                caption=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
            return
        except Exception as e:
            logging.warning(f"Failed to send welcome photo: {e}")

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=markup,
    )


@sync_to_async
def _find_referrer_code(payload):
    """Проверить deep-link payload вида ref_CODE, вернуть код или None."""
    if not payload or not payload.startswith("ref_"):
        return None

    code = payload[4:].strip().upper()
    if not code:
        return None

    exists = Profile.objects.filter(referral_code=code).exists()
    return code if exists else None


@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    ref_code = None
    try:
        parts = (message.text or "").split()
        payload = parts[1] if len(parts) > 1 else ""
        ref_code = await _find_referrer_code(payload)
    except Exception as e:
        logging.warning(f"Failed to parse start payload: {e}")

    await send_welcome(
        message,
        message.from_user.first_name,
        ref_code=ref_code,
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


async def is_subscribed(user_id) -> bool:
    if not REQUIRED_CHANNEL_ID:
        return True

    try:
        member = await bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL_ID,
            user_id=user_id,
        )
        return member.status in ("creator", "administrator", "member")
    except Exception as e:
        logging.error(f"Failed to check channel subscription: {e}")
        return True


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = getattr(event.from_user, "id", None)
        if (
            user_id is None
            or user_id == ADMIN_ID
            or await is_subscribed(user_id)
        ):
            return await handler(event, data)

        buttons = []
        if REQUIRED_CHANNEL_URL:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text="Подписаться",
                        url=REQUIRED_CHANNEL_URL,
                    ),
                ],
            )

        buttons.append(
            [
                InlineKeyboardButton(
                    text="Проверить подписку",
                    callback_data="check_subscription",
                ),
            ],
        )
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await event.answer(
            "🔒 <b>Для доступа нужно подписаться на наш канал</b>\n\n"
            "Подпишитесь и нажмите кнопку ниже, чтобы продолжить.",
            parse_mode="HTML",
            reply_markup=markup,
        )
        return None


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(
    callback: types.CallbackQuery,
) -> None:
    user_id = callback.from_user.id
    if await is_subscribed(user_id):
        await callback.answer("Подписка подтверждена!")
        await callback.message.delete()
        await send_welcome(
            callback.message,
            callback.from_user.first_name,
        )
    else:
        await callback.answer("Вы ещё не подписаны на канал.", show_alert=True)


dp.message.middleware(SubscriptionMiddleware())


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
                    # Один bulk-запрос вместо N персональных, чтобы не
                    # перегружать панель. _wl-заглушки пропускаем.
                    try:
                        rw_all = await client.get_all_users_stream(size=250)
                    except Exception as e:
                        logging.error(f"Reminder bulk fetch failed: {e}")
                        rw_all = []

                    rw_by_tgid = {}
                    for u in rw_all:
                        if not isinstance(u, dict):
                            continue

                        if (u.get("username") or "").endswith("_wl"):
                            continue

                        if u.get("telegramId") is None:
                            continue

                        key = str(u["telegramId"])
                        if key not in rw_by_tgid:
                            rw_by_tgid[key] = u

                    logging.info(
                        "Reminder: %d panel users for %d profiles",
                        len(rw_by_tgid),
                        len(users),
                    )

                    for profile in users:
                        try:
                            rw_user = rw_by_tgid.get(str(profile.telegram_id))

                            if not (
                                isinstance(rw_user, dict)
                                and rw_user.get("expireAt")
                            ):
                                continue

                            expire_str = rw_user["expireAt"].replace(
                                "Z",
                                "+00:00",
                            )
                            try:
                                expire_dt = datetime.fromisoformat(expire_str)
                            except ValueError:
                                continue

                            delta = expire_dt - datetime.now(timezone.utc)
                            # noqa: T201

                            # Подписка истекла — отправляем один раз
                            if delta.total_seconds() <= 0:
                                if (
                                    not profile.subscription_expired_notification_sent  # noqa: E501
                                ):
                                    text = (
                                        "🔔 <b>Напоминание</b>\n\n"
                                        f"Ваша подписка на тариф "
                                        f"<b>{profile.tarif.name}</b> "
                                        "истекла!\n\n"
                                        "Пожалуйста, продлите подписку "
                                        "в панели управления."
                                    )
                                    try:
                                        await bot.send_message(
                                            profile.telegram_id,
                                            text,
                                            parse_mode="HTML",
                                        )
                                    except TelegramAPIError as e:
                                        logging.warning(
                                            "Reminder skip tg=%s: %s",
                                            profile.telegram_id,
                                            e,
                                        )
                                        continue

                                    # Отмечаем что уведомление отправлено
                                    profile.subscription_expired_notification_sent = (  # noqa: E501
                                        True
                                    )
                                    await sync_to_async(profile.save)()

                                continue

                            # delta.days — полные сутки (floor).
                            # Остаток <1 суток считаем за 1 день,
                            # чтобы не слать «истекла» за пару часов
                            # до конца и не пропускать напоминание.
                            days_left = max(1, delta.days)

                            # Подписка активна (>3 дней) —
                            # сбрасываем флаг
                            if days_left > 3:
                                if (
                                    profile.subscription_expired_notification_sent  # noqa: E501
                                ):
                                    profile.subscription_expired_notification_sent = (  # noqa: E501
                                        False
                                    )
                                    await sync_to_async(profile.save)()

                                continue

                            # 1-3 дня до конца — напоминание
                            if 1 <= days_left <= 3:
                                ds = "день" if days_left == 1 else "дня"
                                text = (
                                    "🔔 <b>Напоминание</b>\n\n"
                                    "Ваша подписка на тариф "
                                    f"<b>{profile.tarif.name}</b> "
                                    "истекает примерно через "
                                    f"{days_left} {ds}!\n\n"
                                    "Пожалуйста, продлите подписку "
                                    "в панели управления."
                                )
                                try:
                                    await bot.send_message(
                                        profile.telegram_id,
                                        text,
                                        parse_mode="HTML",
                                    )
                                except TelegramAPIError as e:
                                    logging.warning(
                                        "Reminder skip tg=%s: %s",
                                        profile.telegram_id,
                                        e,
                                    )
                                    continue

                                await asyncio.sleep(0.05)
                        except TelegramAPIError as e:
                            logging.warning(
                                "Reminder skip tg=%s: %s",
                                profile.telegram_id,
                                e,
                            )
                            continue
                        except Exception as e:
                            logging.error(
                                "Reminder failed tg=%s: %s",
                                profile.telegram_id,
                                e,
                            )
                            continue
                finally:
                    await client.close()
        except Exception as e:
            logging.error(f"Error in reminder task: {e}")

        await asyncio.sleep(24 * 3600)  # Check once a day


async def check_and_notify_nodes(raw_nodes, admin_id):
    from connect.models import NodeStatus

    statuses = await sync_to_async(
        lambda: {s.node_id: s for s in NodeStatus.objects.all()},
    )()

    for node in raw_nodes:
        node_id = str(node.get("id") or node.get("uuid") or "")
        if not node_id:
            continue

        node_name = node.get("name", f"Server {node_id}")

        if node.get("isConnected") is None:
            continue

        is_connected = bool(node.get("isConnected"))

        node_status = statuses.get(node_id)
        if not node_status:
            node_status = await sync_to_async(NodeStatus.objects.create)(
                node_id=node_id,
                last_known_online=is_connected,
            )
            statuses[node_id] = node_status
            continue

        # Skip notifications for nodes with manual status override
        if node_status.use_manual_status:
            continue

        # If previous state was online and now is offline -> Send OFF alert
        if node_status.last_known_online is True and not is_connected:
            if node_status.last_alert_sent != "OFFLINE":
                msg = (
                    "⚠️ <b>Внимание! Сервер отключился!</b>\n\n"
                    f"🖥 <b>Сервер:</b> {node_name}\n"
                    f"🔴 <b>Состояние:</b> Отключен (Offline)\n"
                    f"🆔 <code>{node_id}</code>"
                )
                try:
                    await bot.send_message(admin_id, msg, parse_mode="HTML")
                    node_status.last_alert_sent = "OFFLINE"
                except Exception as e:
                    logging.error(
                        f"Failed to send server offline alert to admin: {e}",
                    )

        # If previous state was offline and now is online -> Send ON alert once
        elif node_status.last_known_online is False and is_connected:
            if node_status.last_alert_sent != "ONLINE":
                msg = (
                    "✅ <b>Сервер снова работает!</b>\n\n"
                    f"🖥 <b>Сервер:</b> {node_name}\n"
                    f"🟢 <b>Состояние:</b> Доступен (Online)\n"
                    f"🆔 <code>{node_id}</code>"
                )
                try:
                    await bot.send_message(admin_id, msg, parse_mode="HTML")
                    node_status.last_alert_sent = "ONLINE"
                except Exception as e:
                    logging.error(
                        f"Failed to send server online alert to admin: {e}",
                    )

        if node_status.last_known_online != is_connected:
            node_status.last_known_online = is_connected
            await sync_to_async(node_status.save)()


async def node_monitoring_task():
    while True:
        try:
            admin_id = ADMIN_ID
            if admin_id:
                admin_profile = await sync_to_async(
                    Profile.objects.filter(telegram_id=admin_id).first,
                )()
                if (
                    admin_profile
                    and admin_profile.server_notifications_enabled
                ):
                    client = RemnawaveClient()
                    try:
                        raw_nodes = await client.get_nodes()
                        if isinstance(raw_nodes, list):
                            await check_and_notify_nodes(raw_nodes, admin_id)
                    finally:
                        await client.close()
        except Exception as e:
            logging.error(f"Error in node monitoring task: {e}")

        await asyncio.sleep(60)


async def main() -> None:
    logging.info("Бот успешно запущен и готов к работе!")
    asyncio.create_task(subscription_reminder_task())
    asyncio.create_task(node_monitoring_task())

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
