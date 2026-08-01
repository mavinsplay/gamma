import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import re

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt

from connect.services.remnawave import RemnawaveClient
from shop.models import Order, PromoCode, PromoCodeUsage, Tariff
from shop.platega import Platega, PlategaAPIError, PlategaCallback
from shop.services.platega import (
    create_platega_payment,
    process_platega_callback,
    verify_platega_payment,
)
from shop.services.yoomoney import (
    cancel_expired_orders,
    create_payment_url,
    process_successful_payment,
    verify_operation,
    verify_payment_api,
)
from shop.utils import verify_telegram_init_data
from user.models import Profile

logger = logging.getLogger(__name__)

WHITELIST_EXTERNAL_SQUAD_UUID = getattr(
    settings,
    "WHITELIST_EXTERNAL_SQUAD_UUID",
    "68fce704-b469-43f4-afc9-8a38a5c8b851",
)

__all__ = [
    "app_index",
    "buy_tariff_api",
    "topup_api",
    "buy_slot_api",
    "get_subscription_link_api",
    "delete_hwid_device_api",
    "check_payment_api",
    "success_view",
    "fail_view",
    "sync_data_api",
    "topup_whitelist_traffic_api",
    "platega_callback",
]


def _get_main_user(rw_users, profile=None):
    """Filter _wl (whitelist) user from a list of Remnawave users,
    returning only the main user."""
    if not isinstance(rw_users, list):
        return rw_users

    wl_uuid = getattr(profile, "whitelist_uuid", None) if profile else None

    for u in rw_users:
        if u and u.get("uuid"):
            if wl_uuid and u["uuid"] == wl_uuid:
                continue

            if u.get("username", "").endswith("_wl"):
                continue

            return u

    return rw_users[0] if rw_users else None


def extract_flag(text):
    if not text:
        return None, text
    # Regex for emoji flags (regional indicator symbols)
    flag_pattern = re.compile(r"([\U0001F1E6-\U0001F1FF]{2})")
    match = flag_pattern.search(text)
    if match:
        flag = match.group(1)
        clean_name = text.replace(flag, "").strip()
        # Remove common separators like | or - if they are left at the start
        clean_name = re.sub(r"^[|\-\s]+", "", clean_name)
        return flag, clean_name

    return None, text


def country_code_to_flag(code):
    if not code or len(code) != 2:
        return None

    try:
        # Convert each letter to Regional Indicator Symbol (0x1F1E6 + index)
        return chr(ord(code[0].upper()) + 127397) + chr(
            ord(code[1].upper()) + 127397,
        )
    except Exception:
        return None


def app_index(request):
    tariffs = Tariff.objects.filter(is_active=True).order_by("-price")
    telegram_id = None
    telegram_username = None
    profile = None

    # 1. Try authenticated session
    if "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
        telegram_username = request.session["tg_user"].get("username")
        profile = Profile.objects.filter(telegram_id=telegram_id).first()

    # 2. DEBUG fallback — only from configured mock user, NEVER from URL params
    if not profile and settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if mock and mock.get("id"):
            telegram_id = mock.get("id")
            telegram_username = mock.get("username")
            profile, created = Profile.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={
                    "telegram_username": telegram_username,
                    "balance": 0.00,
                    "tarif": None,
                },
            )
            if (
                not created
                and telegram_username
                and not profile.telegram_username
            ):
                profile.telegram_username = telegram_username
                profile.save()

    # 3. DISABLE_AUTH fallback — same as DEBUG but triggered by env flag
    if not profile and settings.DISABLE_AUTH:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if mock and mock.get("id"):
            telegram_id = mock.get("id")
            telegram_username = mock.get("username")
            profile, created = Profile.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={
                    "telegram_username": telegram_username,
                    "balance": 0.00,
                    "tarif": None,
                },
            )
            if (
                not created
                and telegram_username
                and not profile.telegram_username
            ):
                profile.telegram_username = telegram_username
                profile.save()

    # JS calls sync-data-api with initData to fetch/create the profile.

    async def fetch_all():
        client = RemnawaveClient()
        try:
            tasks = [asyncio.create_task(client.get_nodes())]
            if profile:
                tasks.append(
                    asyncio.create_task(client.get_user_by_tgid(telegram_id)),
                )

            if profile and profile.whitelist_uuid:
                tasks.append(
                    asyncio.create_task(
                        client.get_user(profile.whitelist_uuid),
                    ),
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            raw_nodes = results[0] if results else []
            rw_user = results[1] if len(results) > 1 else None
            whitelist_user = results[2] if len(results) > 2 else None

            if isinstance(raw_nodes, Exception):
                raw_nodes = []

            if isinstance(rw_user, Exception):
                rw_user = None
            elif isinstance(rw_user, list):
                rw_user = _get_main_user(rw_user, profile)

            if isinstance(whitelist_user, Exception):
                whitelist_user = None

            hwid_devices = []
            if rw_user and rw_user.get("uuid"):
                try:
                    hwid_devices = await client.get_user_hwid_devices(
                        rw_user["uuid"],
                    )
                except Exception:
                    pass

            return raw_nodes, rw_user, hwid_devices, whitelist_user
        finally:
            await client.close()

    try:
        from datetime import datetime, timezone

        raw_nodes, rw_user, hwid_devices, whitelist_user = async_to_sync(
            fetch_all,
        )()
        nodes_data = []
        for node in raw_nodes:
            flag, name = extract_flag(node.get("name", ""))

            # Fallback: if no flag in name, try to convert countryCode
            if not flag:
                flag = country_code_to_flag(node.get("countryCode"))

            node["display_flag"] = flag
            node["display_name"] = name
            nodes_data.append(node)

        remaining_days = 0
        if rw_user and rw_user.get("expireAt"):
            expire_str = rw_user["expireAt"].replace("Z", "+00:00")
            try:
                expire_dt = datetime.fromisoformat(expire_str)
                delta = expire_dt - datetime.now(timezone.utc)
                remaining_days = max(0, delta.days)
                rw_user["remaining_days"] = remaining_days
                rw_user["expire_at"] = rw_user["expireAt"]
            except ValueError:
                pass

        # Compute whitelist remaining days
        if whitelist_user:
            whitelist_user["remaining_days"] = 0
            whitelist_user["expire_at"] = None
            if whitelist_user.get("expireAt"):
                try:
                    wl_expire_str = whitelist_user["expireAt"].replace(
                        "Z",
                        "+00:00",
                    )
                    wl_expire_dt = datetime.fromisoformat(wl_expire_str)
                    wl_delta = wl_expire_dt - datetime.now(timezone.utc)
                    whitelist_user["remaining_days"] = max(0, wl_delta.days)
                    whitelist_user["expire_at"] = whitelist_user["expireAt"]
                except ValueError:
                    pass

        online_count = sum(1 for node in nodes_data if node.get("isConnected"))
        offline_count = len(nodes_data) - online_count

        # Proxy Bypass logic
        proxies = []
        if profile and profile.tarif:
            proxies = profile.tarif.proxies.filter(is_active=True)

        # Payment History logic
        payments = []
        if profile:
            payments = Order.objects.filter(telegram_id=telegram_id).order_by(
                "-created_at",
            )[:20]

        # Pending payment check
        has_pending_payment = (
            Order.objects.filter(
                telegram_id=telegram_id,
                status="PENDING",
                order_type="TOPUP",
            ).exists()
            if profile
            else False
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Exception in app_index: {e}")  # noqa: T201
        nodes_data = []
        rw_user = None
        whitelist_user = None
        hwid_devices = []
        online_count = 0
        offline_count = 0
        proxies = []
        payments = []
        has_pending_payment = False

    return render(
        request,
        "base.html",
        {
            "tariffs": tariffs,
            "nodes": nodes_data,
            "online_count": online_count,
            "offline_count": offline_count,
            "proxies": proxies,
            "payments": payments,
            "profile": profile,
            "debug": settings.DEBUG,
            "rw_user": rw_user,
            "whitelist_user": whitelist_user,
            "hwid_devices": hwid_devices,
            "is_admin": str(telegram_id) == str(settings.ADMIN_TELEGRAM_ID),
            "admin_url": settings.ADMIN_URL,
            "mock_user_data": (
                json.dumps(settings.MOCK_TELEGRAM_USER_DATA)
                if settings.DEBUG and settings.MOCK_TELEGRAM_USER_DATA
                else None
            ),
            "bot_username": settings.TELEGRAM_BOT_USERNAME,
            "admin_id": settings.ADMIN_TELEGRAM_ID,
            "support_url": settings.SUPPORT_URL,
            "has_pending_payment": has_pending_payment,
        },
    )


def buy_tariff_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    tariff_id = request.POST.get("tariff_id")
    init_data = request.POST.get("init_data")

    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")
    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
        telegram_username = request.session["tg_user"].get("username")
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
        telegram_username = mock.get("username")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id or not tariff_id:
        return JsonResponse({"error": "Missing params"}, status=400)

    tariff = get_object_or_404(Tariff, id=tariff_id)

    with transaction.atomic():
        profile, created = Profile.objects.select_for_update().get_or_create(
            telegram_id=telegram_id,
        )
        if (
            telegram_username
            and profile.telegram_username != telegram_username
        ):
            profile.telegram_username = telegram_username
            profile.save(update_fields=["telegram_username"])

        from decimal import Decimal

        balance_dec = Decimal(str(profile.balance))
        price_dec = Decimal(str(tariff.price))

        if balance_dec < price_dec:
            missing = price_dec - balance_dec
            return JsonResponse(
                {
                    "error": "insufficient_funds",
                    "missing_amount": float(missing),
                    "tariff_price": float(price_dec),
                },
                status=400,
            )

        profile.balance = balance_dec - price_dec
        profile.tarif = tariff
        profile.save(update_fields=["balance", "tarif"])

        Order.objects.create(
            tariff=tariff,
            telegram_id=telegram_id,
            amount=tariff.price,
            order_type="PURCHASE",
            status="PAID",
        )

    try:
        # Cache profile data BEFORE async block (no ORM in async)
        cur_whitelist_uuid = profile.whitelist_uuid if profile else None

        async def provision_new():
            client = RemnawaveClient()
            username = f"{telegram_username}_{telegram_id}"
            try:
                main_squads = [tariff.squad_uuid] if tariff.squad_uuid else []
                # Disable ALL existing users with this telegramId
                try:
                    old_users = await client.get_user_by_tgid(int(telegram_id))
                    if isinstance(old_users, list):
                        for u in old_users:
                            if u and u.get("uuid"):
                                try:
                                    await client.update_user(
                                        uuid=u["uuid"],
                                        status="DISABLED",
                                    )
                                except Exception:
                                    pass
                    elif old_users and old_users.get("uuid"):
                        await client.update_user(
                            uuid=old_users["uuid"],
                            status="DISABLED",
                        )
                except Exception:
                    pass

                main_user = await client.create_user(
                    username=username,
                    days=tariff.duration_days,
                    trafficlimitbytes=(tariff.traffic_limit_bytes),
                    hwiddevicelimit=tariff.device_limit,
                    telegramid=int(telegram_id),
                    activeinternalsquads=main_squads,
                )
                # Provision whitelist sub if tariff supports it
                whitelist_uuid = None
                if tariff.has_whitelist and tariff.whitelist_squad_uuid:
                    # Try to find existing disabled _wl user first
                    if isinstance(old_users, list):
                        for u in old_users:
                            uname = u.get("username", "")
                            if uname.endswith("_wl"):
                                try:
                                    await client.update_user(
                                        uuid=u["uuid"],
                                        expire_at=(
                                            main_user.get("expireAt")
                                            if main_user
                                            else None
                                        ),
                                        trafficlimitbytes=5368709120,
                                        trafficlimitstrategy="MONTH",
                                        hwiddevicelimit=20,
                                        status="ACTIVE",
                                        activeinternalsquads=[
                                            tariff.whitelist_squad_uuid,
                                        ],
                                        externalsquaduuid=(
                                            WHITELIST_EXTERNAL_SQUAD_UUID
                                        ),
                                    )
                                    whitelist_uuid = u["uuid"]
                                except Exception:
                                    pass

                                break
                    # Create new if no existing found
                    if not whitelist_uuid:
                        try:
                            wl_user = await client.create_user(
                                username=f"{username}_wl",
                                days=tariff.duration_days,
                                trafficlimitbytes=5368709120,
                                trafficlimitstrategy="MONTH",
                                hwiddevicelimit=20,
                                telegramid=int(telegram_id),
                                activeinternalsquads=[
                                    tariff.whitelist_squad_uuid,
                                ],
                                externalsquaduuid=(
                                    WHITELIST_EXTERNAL_SQUAD_UUID
                                ),
                            )
                            if wl_user and wl_user.get("uuid"):
                                whitelist_uuid = wl_user["uuid"]
                        except Exception:
                            # Whitelist sub creation is non-fatal
                            pass

                return main_user, whitelist_uuid
            finally:
                await client.close()

        async def replace_sub():
            client = RemnawaveClient()
            try:
                rw_users = await client.get_user_by_tgid(telegram_id)
                rw_user = _get_main_user(rw_users, profile)

                if not rw_user or not rw_user.get("uuid"):
                    return None, None  # fallback to provision_new

                new_expire = (
                    (
                        datetime.now(timezone.utc)
                        + timedelta(days=tariff.duration_days)
                    )
                    .isoformat()
                    .replace("+00:00", "Z")
                )
                main_squads = [tariff.squad_uuid] if tariff.squad_uuid else []
                try:
                    main_user = await client.update_user(
                        uuid=rw_user["uuid"],
                        expire_at=new_expire,
                        trafficlimitbytes=(tariff.traffic_limit_bytes),
                        hwiddevicelimit=tariff.device_limit,
                        activeinternalsquads=main_squads,
                    )
                except Exception:
                    return None, None  # fallback to provision_new
                # Handle whitelist sub
                whitelist_uuid = None
                if tariff.has_whitelist and tariff.whitelist_squad_uuid:
                    # Try to re-enable existing whitelist user
                    if cur_whitelist_uuid:
                        try:
                            await client.update_user(
                                uuid=cur_whitelist_uuid,
                                expire_at=new_expire,
                                status="ACTIVE",
                                trafficlimitbytes=5368709120,
                                trafficlimitstrategy="MONTH",
                                hwiddevicelimit=20,
                                activeinternalsquads=[
                                    tariff.whitelist_squad_uuid,
                                ],
                                externalsquaduuid=(
                                    WHITELIST_EXTERNAL_SQUAD_UUID
                                ),
                            )
                            whitelist_uuid = cur_whitelist_uuid
                        except Exception:
                            pass
                    # Try to find existing disabled _wl user in RW list
                    if not whitelist_uuid:
                        for u in rw_users:
                            uname = u.get("username", "")
                            if uname.endswith("_wl") and u.get(
                                "uuid",
                            ) != rw_user.get("uuid"):
                                try:
                                    await client.update_user(
                                        uuid=u["uuid"],
                                        expire_at=new_expire,
                                        trafficlimitbytes=5368709120,
                                        trafficlimitstrategy="MONTH",
                                        hwiddevicelimit=20,
                                        status="ACTIVE",
                                        activeinternalsquads=[
                                            tariff.whitelist_squad_uuid,
                                        ],
                                        externalsquaduuid=(
                                            WHITELIST_EXTERNAL_SQUAD_UUID
                                        ),
                                    )
                                    whitelist_uuid = u["uuid"]
                                except Exception:
                                    pass

                                break
                    # Create new whitelist user if nothing found
                    if not whitelist_uuid:
                        try:
                            wl_user = await client.create_user(
                                username=(
                                    f"{rw_user.get('username', str(telegram_id))}"  # noqa
                                    f"_wl"
                                ),
                                days=tariff.duration_days,
                                trafficlimitbytes=5368709120,
                                trafficlimitstrategy="MONTH",
                                hwiddevicelimit=20,
                                telegramid=int(telegram_id),
                                activeinternalsquads=[
                                    tariff.whitelist_squad_uuid,
                                ],
                                externalsquaduuid=(
                                    WHITELIST_EXTERNAL_SQUAD_UUID
                                ),
                            )
                            if wl_user and wl_user.get("uuid"):
                                whitelist_uuid = wl_user["uuid"]
                        except Exception:
                            pass
                else:
                    # New tariff has no whitelist — disable old _wl user
                    if cur_whitelist_uuid:
                        try:
                            await client.update_user(
                                uuid=cur_whitelist_uuid,
                                status="DISABLED",
                            )
                        except Exception:
                            pass

                return main_user, whitelist_uuid
            finally:
                await client.close()

        # Always try replace_sub first — it updates an existing RW user
        # (no disable). If no RW user exists, replace_sub returns None
        # and we fall through to provision_new (create fresh).
        rw_data, wl_uuid = async_to_sync(replace_sub)()
        if rw_data is None:
            rw_data, wl_uuid = async_to_sync(provision_new)()

        # Persist whitelist_uuid to profile
        if wl_uuid:
            Profile.objects.filter(telegram_id=telegram_id).update(
                whitelist_uuid=wl_uuid,
            )
        else:
            # Clear stale whitelist_uuid (user deleted externally
            # or tariff no longer has whitelist)
            Profile.objects.filter(telegram_id=telegram_id).update(
                whitelist_uuid=None,
            )

        # Compute remaining days for instant UI update
        remaining_days = 0
        expire_at = None
        if rw_data and rw_data.get("expireAt"):
            expire_str = rw_data["expireAt"].replace("Z", "+00:00")
            try:
                expire_dt = datetime.fromisoformat(expire_str)
                delta = expire_dt - datetime.now(timezone.utc)
                remaining_days = max(0, delta.days)
                expire_at = rw_data["expireAt"]
            except ValueError:
                pass

        return JsonResponse(
            {
                "success": True,
                "new_balance": float(profile.balance),
                "sub": rw_data,
                "has_whitelist": bool(wl_uuid),
                "remaining_days": remaining_days,
                "expire_at": expire_at,
                "tariff_name": tariff.name,
                "tariff_price": float(tariff.price),
                "tariff_days": tariff.duration_days,
            },
        )
    except Exception:
        with transaction.atomic():
            profile = Profile.objects.select_for_update().get(
                telegram_id=telegram_id,
            )
            profile.balance += tariff.price
            profile.tarif = None
            profile.save(update_fields=["balance", "tarif"])
            Order.objects.filter(
                telegram_id=telegram_id,
                tariff=tariff,
                order_type="PURCHASE",
                status="PAID",
            ).update(status="FAILED")

        return JsonResponse({"error": "Ошибка при покупке тарифа"}, status=500)


def topup_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    amount = request.POST.get("amount", 0)
    # Метод оплаты: yoomoney, sbp или crypto
    payment_provider = request.POST.get("payment_provider", "yoomoney")
    if payment_provider not in ("yoomoney", "sbp", "crypto"):
        return JsonResponse({"error": "Неверный метод оплаты"}, status=400)

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")
    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
        telegram_username = request.session["tg_user"].get("username")
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
        telegram_username = mock.get("username")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    try:
        telegram_id = int(telegram_id)
        amount_dec = Decimal(str(amount))
        if amount_dec <= 0 or amount_dec > 100000:
            return JsonResponse(
                {"error": "Некорректная сумма"},
                status=400,
            )
    except Exception:
        return JsonResponse(
            {"error": "Некорректные параметры"},
            status=400,
        )

    cancel_expired_orders()

    with transaction.atomic():
        profile, created = Profile.objects.select_for_update().get_or_create(
            telegram_id=telegram_id,
        )
        if (
            telegram_username
            and profile.telegram_username != telegram_username
        ):
            profile.telegram_username = telegram_username
            profile.save(update_fields=["telegram_username"])

        existing_pending = (
            Order.objects.select_for_update()
            .filter(
                telegram_id=telegram_id,
                status="PENDING",
                order_type="TOPUP",
            )
            .first()
        )
        if existing_pending:
            return JsonResponse(
                {
                    "error": (
                        "У вас уже есть ожидающий платёж. "
                        "Дождитесь его завершения."
                    ),
                    "existing_order_id": existing_pending.id,
                    "payment_url": existing_pending.payment_url or "",
                    "payment_provider": existing_pending.payment_provider,
                },
                status=409,
            )

        order = Order.objects.create(
            telegram_id=telegram_id,
            amount=amount_dec,
            order_type="TOPUP",
            status="PENDING",
            payment_provider=(
                "platega"
                if payment_provider in ("sbp", "crypto")
                else "yoomoney"
            ),
        )

    host = request.get_host()
    scheme = "https" if request.is_secure() else request.scheme
    success_url = f"{scheme}://{host}/shop/success/{order.id}/"
    failed_url = f"{scheme}://{host}/shop/fail/{order.id}/"

    # --- YooMoney ---
    if payment_provider == "yoomoney":
        receiver = getattr(settings, "YOOMONEY_RECEIVER", "")
        if not receiver:
            order.status = "FAILED"
            order.save(update_fields=["status"])
            return JsonResponse(
                {"error": "Payment gateway not configured"},
                status=500,
            )

        try:
            payment_url = create_payment_url(
                order_id=order.id,
                amount=amount_dec,
                receiver=receiver,
                success_url=success_url,
            )
            order.payment_url = payment_url
            order.save(update_fields=["payment_url"])
            expires_at = order.created_at + timedelta(
                minutes=settings.ORDER_TIMEOUT_MINUTES,
            )
            return JsonResponse(
                {
                    "success": True,
                    "payment_url": payment_url,
                    "order_id": order.id,
                    "expires_at": expires_at.isoformat(),
                },
            )
        except Exception:
            order.status = "FAILED"
            order.save(update_fields=["status"])
            return JsonResponse(
                {"error": "Ошибка платежной системы"},
                status=500,
            )

    # --- Platega (SBP / Crypto) ---
    platega_method_map = {
        "sbp": Platega.METHOD_SBP_QR,
        "crypto": Platega.METHOD_CRYPTO,
    }
    platega_method = platega_method_map.get(payment_provider)
    if not platega_method:
        order.status = "FAILED"
        order.save(update_fields=["status"])
        return JsonResponse(
            {"error": "Неизвестный метод оплаты"},
            status=400,
        )

    if not getattr(settings, "PLATEGA_MERCHANT_ID", ""):
        order.status = "FAILED"
        order.save(update_fields=["status"])
        return JsonResponse(
            {"error": "Platega not configured"},
            status=500,
        )

    try:
        redirect_url, transaction_id = create_platega_payment(
            order_id=order.id,
            amount=amount_dec,
            payment_method=platega_method,
            return_url=success_url,
            failed_url=failed_url,
        )
        order.platega_transaction_id = transaction_id
        order.payment_url = redirect_url
        order.save(update_fields=["platega_transaction_id", "payment_url"])
        expires_at = order.created_at + timedelta(
            minutes=settings.ORDER_TIMEOUT_MINUTES,
        )
        return JsonResponse(
            {
                "success": True,
                "payment_url": redirect_url,
                "order_id": order.id,
                "expires_at": expires_at.isoformat(),
            },
        )
    except (PlategaAPIError, ValueError) as e:
        logger.error(
            f"[platega] create_payment error for order #{order.id}: {e}",
        )
        order.status = "FAILED"
        order.save(update_fields=["status"])
        return JsonResponse(
            {"error": "Ошибка Platega: попробуйте позже"},
            status=500,
        )
    except Exception as e:
        logger.error(
            f"[platega] unexpected error for order #{order.id}: {e}",
        )
        order.status = "FAILED"
        order.save(update_fields=["status"])
        return JsonResponse(
            {"error": "Ошибка платежной системы"},
            status=500,
        )


@csrf_exempt
def check_payment_api(request, order_id):
    if request.method != "GET":
        return JsonResponse({"error": "Only GET allowed"}, status=405)

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)

    uid = _get_authorized_telegram_id(request)
    if uid is None or int(order.telegram_id) != int(uid):
        return JsonResponse({"error": "Forbidden"}, status=403)

    if order.status == "PAID":
        profile = Profile.objects.filter(
            telegram_id=order.telegram_id,
        ).first()
        return JsonResponse(
            {
                "status": "paid",
                "new_balance": float(profile.balance) if profile else 0,
            },
        )

    if order.status == "FAILED":
        return JsonResponse({"status": "failed"})

    if order.status == "PENDING":
        if settings.DEBUG:
            age = (
                datetime.now(timezone.utc) - order.created_at
            ).total_seconds()
            if age >= 15:
                result = process_successful_payment(order.id)
                if result:
                    profile = Profile.objects.get(
                        telegram_id=order.telegram_id,
                    )
                    return JsonResponse(
                        {
                            "status": "paid",
                            "new_balance": float(profile.balance),
                        },
                    )
        else:
            if order.payment_provider == "platega":
                status = verify_platega_payment(order.platega_transaction_id)
                if status == Platega.STATUS_CONFIRMED:
                    result = process_successful_payment(order.id)
                    if result:
                        profile = Profile.objects.get(
                            telegram_id=order.telegram_id,
                        )
                        return JsonResponse(
                            {
                                "status": "paid",
                                "new_balance": float(profile.balance),
                            },
                        )
                elif status == Platega.STATUS_CANCELED:  # noqa
                    order.status = "FAILED"
                    order.save(update_fields=["status"])
                    return JsonResponse({"status": "failed"})
                elif status == Platega.STATUS_CHARGEBACKED:
                    order.status = "CHARGEBACK"
                    order.save(update_fields=["status"])
                    return JsonResponse({"status": "chargeback"})
            else:
                op_id = request.GET.get("operation_id")
                confirmed = False
                if op_id:
                    confirmed = verify_operation(
                        op_id,
                        order.id,
                        order.amount,
                    )

                if not confirmed:
                    confirmed = verify_payment_api(order.id, order.amount)

                if confirmed:
                    result = process_successful_payment(order.id)
                    if result:
                        profile = Profile.objects.get(
                            telegram_id=order.telegram_id,
                        )
                        return JsonResponse(
                            {
                                "status": "paid",
                                "new_balance": float(profile.balance),
                            },
                        )

        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.ORDER_TIMEOUT_MINUTES,
        )
        if order.created_at < cutoff:
            order.status = "FAILED"
            order.save(update_fields=["status"])
            return JsonResponse({"status": "failed"})

        return JsonResponse({"status": "pending"})

    return JsonResponse({"status": order.status})


def buy_slot_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")
    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
        telegram_username = request.session["tg_user"].get("username")
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
        telegram_username = mock.get("username")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid tg_id format"}, status=400)

    slot_price = Decimal("100.00")

    with transaction.atomic():
        profile, created = Profile.objects.select_for_update().get_or_create(
            telegram_id=telegram_id,
        )
        if (
            telegram_username
            and profile.telegram_username != telegram_username
        ):
            profile.telegram_username = telegram_username
            profile.save(update_fields=["telegram_username"])

        if profile.balance < slot_price:
            missing = slot_price - profile.balance
            return JsonResponse(
                {
                    "error": "insufficient_funds",
                    "missing_amount": float(missing),
                    "slot_price": float(slot_price),
                },
                status=400,
            )

        profile.balance -= slot_price
        profile.save(update_fields=["balance"])

    try:

        async def add_slot():
            client = RemnawaveClient()
            try:
                rw_user = await client.get_user_by_tgid(telegram_id)
                rw_user = _get_main_user(rw_user, profile)

                if not rw_user or not rw_user.get("uuid"):
                    raise ValueError("User not found in Remnawave")

                current_limit = rw_user.get("hwidDeviceLimit", 0)
                new_limit = current_limit + 1

                return await client.update_user(
                    uuid=rw_user["uuid"],
                    hwiddevicelimit=new_limit,
                )
            finally:
                await client.close()

        rw_data = async_to_sync(add_slot)()

        return JsonResponse(
            {
                "success": True,
                "new_balance": float(profile.balance),
                "new_limit": rw_data.get("hwidDeviceLimit"),
            },
        )
    except Exception:
        with transaction.atomic():
            profile = Profile.objects.select_for_update().get(
                telegram_id=telegram_id,
            )
            profile.balance += slot_price
            profile.save(update_fields=["balance"])

        return JsonResponse({"error": "Ошибка при покупке слота"}, status=500)


def get_subscription_link_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    init_data = request.POST.get("init_data")
    sub_type = request.POST.get("sub_type", "main")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")
    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
        telegram_username = request.session["tg_user"].get("username")
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
        telegram_username = mock.get("username")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid tg_id format"}, status=400)

    profile, created = Profile.objects.get_or_create(telegram_id=telegram_id)
    if telegram_username and profile.telegram_username != telegram_username:
        profile.telegram_username = telegram_username
        profile.save()

    if sub_type == "whitelist":
        if not profile.whitelist_uuid:
            return JsonResponse(
                {"error": "У вас нет активной whitelist-подписки"},
                status=400,
            )

        async def fetch_wl_link():
            client = RemnawaveClient()
            try:
                return await client.get_sub_link(profile.whitelist_uuid)
            finally:
                await client.close()

        try:
            sub_data = async_to_sync(fetch_wl_link)()
            return JsonResponse(
                {
                    "success": True,
                    "link": sub_data.get(
                        "url",
                        sub_data.get("subscriptionUrl", ""),
                    ),
                },
            )
        except Exception:
            return JsonResponse(
                {"error": "Ошибка получения ссылки"},
                status=500,
            )

    async def fetch_link():
        client = RemnawaveClient()
        try:
            try:
                rw_users = await client.get_user_by_tgid(telegram_id)
                rw_user = _get_main_user(rw_users, profile)
            except Exception as e:
                print(f"Error fetching user from Remnawave: {e}")  # noqa: T201
                rw_user = None

            if not rw_user or not rw_user.get("uuid"):
                # Auto-heal: user has tariff in DB but missing in Remnawave
                if profile and profile.tarif:
                    username = (
                        f"{profile.telegram_username or 'user'}_{telegram_id}"
                    )
                    rw_user = await client.create_user(
                        username=username,
                        days=profile.tarif.duration_days,
                        trafficlimitbytes=profile.tarif.traffic_limit_bytes,
                        hwiddevicelimit=profile.tarif.device_limit,
                        telegramid=int(telegram_id),
                        activeinternalsquads=[profile.tarif.squad_uuid],
                    )
                    if not rw_user or not rw_user.get("uuid"):
                        raise ValueError(
                            "User not found and failed to re-provision",
                        )

                else:
                    raise ValueError("User not found")

            return await client.get_sub_link(rw_user["uuid"])
        finally:
            await client.close()

    try:
        sub_data = async_to_sync(fetch_link)()
        return JsonResponse(
            {
                "success": True,
                "link": sub_data.get(
                    "url",
                    sub_data.get("subscriptionUrl", ""),
                ),
            },
        )
    except Exception:
        return JsonResponse({"error": "Ошибка получения ссылки"}, status=500)


def delete_hwid_device_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    hwid = request.POST.get("hwid")

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id or not hwid:
        return JsonResponse({"error": "Missing params"}, status=400)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid tg_id format"}, status=400)

    async def do_delete():
        client = RemnawaveClient()
        try:
            profile = Profile.objects.filter(
                telegram_id=telegram_id,
            ).first()
            rw_user = await client.get_user_by_tgid(telegram_id)
            rw_user = _get_main_user(rw_user, profile)

            if not rw_user or not rw_user.get("uuid"):
                raise ValueError("User not found in Remnawave")

            await client.delete_hwid_device(rw_user["uuid"], hwid)
        finally:
            await client.close()

    try:
        async_to_sync(do_delete)()
        return JsonResponse({"success": True})
    except Exception:
        return JsonResponse(
            {"error": "Ошибка удаления устройства"},
            status=500,
        )


def promo_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    code = request.POST.get("code", "").strip()

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid tg_id format"}, status=400)

    if not code:
        return JsonResponse({"error": "Введите промокод"}, status=400)

    try:
        promo = PromoCode.objects.get(code__iexact=code, is_active=True)
    except PromoCode.DoesNotExist:
        return JsonResponse(
            {"error": "Промокод не найден или неактивен"},
            status=400,
        )

    profile, created = Profile.objects.get_or_create(telegram_id=telegram_id)

    days_to_extend = None

    try:
        with transaction.atomic():
            promo = PromoCode.objects.select_for_update().get(
                pk=promo.pk,
                is_active=True,
            )
            profile = Profile.objects.select_for_update().get(pk=profile.pk)

            if PromoCodeUsage.objects.filter(
                promo_code=promo,
                profile=profile,
            ).exists():
                return JsonResponse(
                    {"error": "Этот промокод уже был использован"},
                    status=400,
                )

            if promo.reward_type == "BALANCE":
                profile.balance += promo.reward_value
                profile.save()
            elif promo.reward_type == "DAYS":
                days_to_extend = int(promo.reward_value)
                if days_to_extend <= 0:
                    return JsonResponse(
                        {"error": "Некорректное значение промокода"},
                        status=400,
                    )

                async def extend_via_promo():
                    client = RemnawaveClient()
                    try:
                        rw_users = await client.get_user_by_tgid(telegram_id)
                        if isinstance(rw_users, list):
                            rw_user = _get_main_user(rw_users, profile)
                        else:
                            rw_user = rw_users

                        if rw_user and rw_user.get("uuid"):
                            from datetime import (
                                datetime,
                                timedelta,
                                timezone,
                            )

                            current_expire_str = rw_user.get("expireAt")
                            now = datetime.now(timezone.utc)
                            if current_expire_str:
                                expire_str = current_expire_str.replace(
                                    "Z",
                                    "+00:00",
                                )
                                try:
                                    expire_dt = datetime.fromisoformat(
                                        expire_str,
                                    )
                                    if expire_dt < now:
                                        expire_dt = now
                                except ValueError:
                                    expire_dt = now
                            else:
                                expire_dt = now

                            new_expire_dt = expire_dt + timedelta(
                                days=days_to_extend,
                            )
                            new_expire_str = new_expire_dt.isoformat().replace(
                                "+00:00",
                                "Z",
                            )

                            await client.update_user(
                                uuid=rw_user["uuid"],
                                expire_at=new_expire_str,
                            )
                    finally:
                        await client.close()

                async_to_sync(extend_via_promo)()

            PromoCodeUsage.objects.create(promo_code=promo, profile=profile)
    except Exception:
        return JsonResponse(
            {"error": "Ошибка применения промокода"},
            status=500,
        )

    return JsonResponse(
        {
            "success": True,
            "new_balance": float(profile.balance),
            "reward_type": promo.reward_type,
            "reward_value": float(promo.reward_value),
        },
    )


def extend_sub_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    months = request.POST.get("months")

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id or not months:
        return JsonResponse({"error": "Missing params"}, status=400)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid tg_id format"}, status=400)

    try:
        months = int(months)
        if months not in [1, 3, 6, 12]:
            raise ValueError
    except ValueError:
        return JsonResponse({"error": "Invalid months value"}, status=400)

    with transaction.atomic():
        profile = get_object_or_404(
            Profile.objects.select_for_update(),
            telegram_id=telegram_id,
        )
        if not profile.tarif:
            return JsonResponse(
                {"error": "No active tariff to extend"},
                status=400,
            )

        price_per_month = profile.tarif.price / Decimal(
            str(profile.tarif.duration_days / 30.0),
        )
        total_price = Decimal(str(price_per_month * months)).quantize(
            Decimal("0.00"),
        )

        if profile.balance < total_price:
            missing = total_price - profile.balance
            return JsonResponse(
                {
                    "error": "insufficient_funds",
                    "missing_amount": float(missing),
                    "extension_price": float(total_price),
                },
                status=400,
            )

        tariff_ref = profile.tarif
        profile.balance -= total_price
        profile.save(update_fields=["balance"])

        Order.objects.create(
            tariff=tariff_ref,
            telegram_id=telegram_id,
            amount=total_price,
            order_type="PURCHASE",
            status="PAID",
        )

    try:
        new_expire_at = None
        cur_whitelist_uuid = profile.whitelist_uuid

        async def extend_both():
            nonlocal new_expire_at
            client = RemnawaveClient()
            try:
                rw_users = await client.get_user_by_tgid(telegram_id)
                rw_user = _get_main_user(rw_users, profile)

                if rw_user and rw_user.get("uuid"):
                    current_expire_str = rw_user.get("expireAt")
                    now = datetime.now(timezone.utc)
                    if current_expire_str:
                        expire_str = current_expire_str.replace("Z", "+00:00")
                        try:
                            expire_dt = datetime.fromisoformat(expire_str)
                            if expire_dt < now:
                                expire_dt = now
                        except ValueError:
                            expire_dt = now
                    else:
                        expire_dt = now

                    new_expire_dt = expire_dt + timedelta(days=months * 30)
                    new_expire_at = new_expire_dt.isoformat().replace(
                        "+00:00",
                        "Z",
                    )

                    await client.update_user(
                        uuid=rw_user["uuid"],
                        expire_at=new_expire_at,
                    )

                # Also extend whitelist user if it exists
                if cur_whitelist_uuid:
                    try:
                        wl_user = await client.get_user(cur_whitelist_uuid)
                        wl_expire_str = wl_user.get("expireAt")
                        now = datetime.now(timezone.utc)
                        if wl_expire_str:
                            wl_exp_str = wl_expire_str.replace("Z", "+00:00")
                            try:
                                wl_dt = datetime.fromisoformat(wl_exp_str)
                                if wl_dt < now:
                                    wl_dt = now
                            except ValueError:
                                wl_dt = now
                        else:
                            wl_dt = now

                        wl_new_dt = wl_dt + timedelta(days=months * 30)
                        wl_new_expire = wl_new_dt.isoformat().replace(
                            "+00:00",
                            "Z",
                        )
                        await client.update_user(
                            uuid=cur_whitelist_uuid,
                            expire_at=wl_new_expire,
                        )
                    except Exception:
                        pass

            finally:
                await client.close()

        async_to_sync(extend_both)()

        # Compute actual remaining days from new expire
        actual_remaining = months * 30
        if new_expire_at:
            try:
                expire_dt = datetime.fromisoformat(
                    new_expire_at.replace("Z", "+00:00"),
                )
                delta = expire_dt - datetime.now(timezone.utc)
                actual_remaining = max(0, delta.days)
            except ValueError:
                pass

        return JsonResponse(
            {
                "success": True,
                "new_balance": float(profile.balance),
                "new_expire_at": new_expire_at,
                "remaining_days": actual_remaining,
            },
        )
    except Exception:
        with transaction.atomic():
            profile = Profile.objects.select_for_update().get(
                telegram_id=telegram_id,
            )
            profile.balance += total_price
            profile.save(update_fields=["balance"])
            Order.objects.filter(
                telegram_id=telegram_id,
                tariff=tariff_ref,
                order_type="PURCHASE",
                status="PAID",
            ).update(status="FAILED")

        return JsonResponse({"error": "Ошибка продления подписки"}, status=500)


def _get_authorized_telegram_id(request):
    if settings.DISABLE_AUTH:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if mock:
            return mock.get("id")

        return 1

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)
    if is_valid:
        return tg_user.get("id")

    if "tg_user" in request.session:
        return request.session["tg_user"]["id"]

    if settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if mock:
            return mock.get("id")

    return None


def success_view(request, sub_id):
    order = get_object_or_404(Order, id=sub_id)

    uid = _get_authorized_telegram_id(request)
    if uid is None or int(order.telegram_id) != int(uid):
        return render(
            request,
            "shop/fail.html",
            {"error_message": "Доступ запрещён."},
        )

    operation_id = request.GET.get("operation_id")
    if operation_id and order.status == "PENDING":
        confirmed = verify_operation(
            operation_id,
            order.id,
            order.amount,
        )
        if confirmed:
            process_successful_payment(order.id)
            order.refresh_from_db()

    return render(request, "shop/success.html", {"order": order})


def fail_view(request, sub_id):
    order = get_object_or_404(Order, id=sub_id)
    uid = _get_authorized_telegram_id(request)
    if uid is None or int(order.telegram_id) != int(uid):
        return render(
            request,
            "shop/fail.html",
            {"error_message": "Доступ запрещён."},
        )

    error_message = None
    if order.status == "FAILED":
        error_message = "Платёж был отклонён платёжной системой."
    elif order.status == "PENDING":
        error_message = (
            "Платёж ещё не завершён. Попробуйте обновить страницу позже."
        )
    else:
        error_message = "Платёж был отменён."

    return render(
        request,
        "shop/fail.html",
        {"order": order, "error_message": error_message},
    )


def sync_data_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")

        request.session["tg_user"] = {
            "id": telegram_id,
            "username": telegram_username,
            "first_name": tg_user.get("first_name"),
            "last_name": tg_user.get("last_name"),
            "photo_url": tg_user.get("photo_url"),
        }

        profile, created = Profile.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                "telegram_username": telegram_username,
                "balance": 0.00,
            },
        )
        if (
            not created
            and telegram_username
            and profile.telegram_username != telegram_username
        ):
            profile.telegram_username = telegram_username
            profile.save()

    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
        profile = Profile.objects.filter(telegram_id=telegram_id).first()
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
        profile = Profile.objects.filter(telegram_id=telegram_id).first()
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not profile:
        # If profile doesn't exist and we couldn't create it
        return JsonResponse(
            {"success": True, "profile": None, "rw_user": None},
        )

    cancel_expired_orders()

    async def fetch_sync_data():
        client = RemnawaveClient()
        try:
            tasks = [asyncio.create_task(client.get_nodes())]
            if telegram_id:
                tasks.append(
                    asyncio.create_task(client.get_user_by_tgid(telegram_id)),
                )

            if profile and profile.whitelist_uuid:
                tasks.append(
                    asyncio.create_task(
                        client.get_user(profile.whitelist_uuid),
                    ),
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            raw_nodes = results[0] if results else []
            rw_user = results[1] if len(results) > 1 else None
            whitelist_raw = results[2] if len(results) > 2 else None

            if isinstance(raw_nodes, Exception):
                raw_nodes = []

            if isinstance(rw_user, Exception):
                rw_user = None
            elif isinstance(rw_user, list):
                rw_user = _get_main_user(rw_user, profile)

            if isinstance(whitelist_raw, Exception):
                whitelist_raw = None

            hwid_devices = []
            if rw_user and rw_user.get("uuid"):
                try:
                    hwid_devices = await client.get_user_hwid_devices(
                        rw_user["uuid"],
                    )
                except Exception:
                    pass

            whitelist_user_data = None
            if whitelist_raw:
                wl_user = whitelist_raw
                wl_user["remaining_days"] = 0
                wl_user["expire_at"] = None
                if wl_user.get("expireAt"):
                    wl_str = wl_user["expireAt"].replace("Z", "+00:00")
                    wl_dt = datetime.fromisoformat(wl_str)
                    wl_delta = wl_dt - datetime.now(timezone.utc)
                    wl_user["remaining_days"] = max(0, wl_delta.days)
                    wl_user["expire_at"] = wl_user["expireAt"]

                whitelist_user_data = wl_user

            return (
                raw_nodes,
                rw_user,
                hwid_devices,
                whitelist_user_data,
                isinstance(results[0] if results else None, Exception),
            )
        finally:
            await client.close()

    try:
        from datetime import datetime, timezone

        raw_nodes, rw_user, hwid_devices, whitelist_user_data, nodes_error = (
            async_to_sync(
                fetch_sync_data,
            )()
        )
        nodes_data = []
        for node in raw_nodes:
            flag, name = extract_flag(node.get("name", ""))
            if not flag:
                flag = country_code_to_flag(node.get("countryCode"))

            node["display_flag"] = flag
            node["display_name"] = name
            nodes_data.append(node)

        remaining_days = 0
        if rw_user and rw_user.get("expireAt"):
            expire_str = rw_user["expireAt"].replace("Z", "+00:00")
            try:
                expire_dt = datetime.fromisoformat(expire_str)
                delta = expire_dt - datetime.now(timezone.utc)
                remaining_days = max(0, delta.days)
                rw_user["remaining_days"] = remaining_days
                rw_user["expire_at"] = rw_user["expireAt"]
            except ValueError:
                pass

        # Payment History
        payments = []
        if profile:
            qs = Order.objects.filter(telegram_id=telegram_id).order_by(
                "-created_at",
            )[:20]
            for p in qs:
                payments.append(
                    {
                        "id": p.id,
                        "amount": float(p.amount),
                        "order_type": p.order_type,
                        "status": p.status,
                        "created_at": p.created_at.strftime("%d.%m.%Y %H:%M"),
                        "tariff_name": p.tariff.name if p.tariff else None,
                    },
                )

        # Proxy Bypass logic
        proxies_data = []
        if profile and profile.tarif:
            active_proxies = profile.tarif.proxies.filter(is_active=True)
            for p in active_proxies:
                proxies_data.append(
                    {"name": p.name, "connection_url": p.connection_url},
                )

        is_admin = str(telegram_id) == str(settings.ADMIN_TELEGRAM_ID)

        from connect.models import NodeStatus

        pending_order = (
            Order.objects.filter(
                telegram_id=telegram_id,
                status="PENDING",
                order_type="TOPUP",
            ).first()
            if profile
            else None
        )
        has_pending_payment = pending_order is not None
        pending_payment = None
        if pending_order:
            payment_url = pending_order.payment_url
            if not payment_url:
                receiver = getattr(settings, "YOOMONEY_RECEIVER", "")
                success_url = "{scheme}://{host}/shop/success/{oid}/".format(
                    scheme=request.scheme,
                    host=request.get_host(),
                    oid=pending_order.id,
                )
                payment_url = create_payment_url(
                    pending_order.id,
                    pending_order.amount,
                    receiver,
                    success_url,
                )

            pending_payment = {
                "order_id": pending_order.id,
                "amount": float(pending_order.amount),
                "payment_url": payment_url,
                "payment_provider": pending_order.payment_provider,
                "expires_at": (
                    pending_order.created_at
                    + timedelta(minutes=settings.ORDER_TIMEOUT_MINUTES)
                ).isoformat(),
            }

        statuses = {s.node_id: s for s in NodeStatus.objects.all()}

        online_count = 0
        offline_count = 0

        for node in nodes_data:
            node_id = str(node.get("id") or node.get("uuid") or "")
            node["id"] = node_id

            custom = statuses.get(node_id)
            is_online = node.get("isConnected")

            if custom:
                node["custom_status"] = custom.status_text
                node["use_manual_status"] = custom.use_manual_status
                node["manual_is_online"] = custom.manual_is_online
                if custom.use_manual_status:
                    is_online = custom.manual_is_online
            else:
                node["custom_status"] = None
                node["use_manual_status"] = False
                node["manual_is_online"] = True

            if is_online:
                online_count += 1
            else:
                offline_count += 1

        return JsonResponse(
            {
                "success": True,
                "is_admin": is_admin,
                "profile": (
                    {
                        "balance": float(profile.balance),
                        "tarif_name": (
                            profile.tarif.name if profile.tarif else "—"
                        ),
                        "tarif_price": (
                            float(profile.tarif.price) if profile.tarif else 0
                        ),
                        "tarif_days": (
                            profile.tarif.duration_days if profile.tarif else 0
                        ),
                        "payment_reminder_enabled": (
                            profile.payment_reminder_enabled
                        ),
                        "notifications_enabled": (
                            profile.notifications_enabled
                        ),
                        "server_notifications_enabled": (
                            profile.server_notifications_enabled
                        ),
                        "whitelist_uuid": (
                            str(profile.whitelist_uuid)
                            if profile.whitelist_uuid
                            else None
                        ),
                    }
                    if profile
                    else None
                ),
                "rw_user": rw_user,
                "whitelist_user": whitelist_user_data,
                "hwid_devices": hwid_devices,
                "nodes": nodes_data,
                "nodes_error": nodes_error,
                "online_count": online_count,
                "offline_count": offline_count,
                "payments": payments,
                "proxies": proxies_data,
                "has_pending_payment": has_pending_payment,
                "pending_payment": pending_payment,
            },
        )
    except Exception:
        return JsonResponse(
            {"error": "Ошибка синхронизации данных"},
            status=500,
        )


def update_preferences_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid tg_id format"}, status=400)

    profile = Profile.objects.filter(telegram_id=telegram_id).first()
    if not profile:
        return JsonResponse({"error": "Profile not found"}, status=404)

    pref_type = request.POST.get("type")
    value = request.POST.get("value") == "true"

    if pref_type == "payment_reminder":
        profile.payment_reminder_enabled = value
    elif pref_type == "notifications":
        profile.notifications_enabled = value
    elif pref_type == "server_notifications":
        if str(telegram_id) != str(settings.ADMIN_TELEGRAM_ID):
            return JsonResponse({"error": "Unauthorized"}, status=403)

        profile.server_notifications_enabled = value
    else:
        return JsonResponse({"error": "Invalid type"}, status=400)

    profile.save()
    return JsonResponse({"success": True})


def topup_whitelist_traffic_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    gb_amount = request.POST.get("gb_amount")

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
    elif "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
    elif settings.DEBUG:
        mock = settings.MOCK_TELEGRAM_USER_DATA
        if not mock:
            return JsonResponse(
                {"error": "No mock data configured"},
                status=400,
            )

        telegram_id = mock.get("id")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id or not gb_amount:
        return JsonResponse({"error": "Missing params"}, status=400)

    try:
        telegram_id = int(telegram_id)
        gb_amount = int(gb_amount)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid params"}, status=400)

    if gb_amount <= 0:
        return JsonResponse({"error": "Invalid amount"}, status=400)

    PRICE_PER_GB = Decimal("10.00")  # noqa
    total_price = (Decimal(str(gb_amount)) * PRICE_PER_GB).quantize(
        Decimal("0.00"),
    )

    with transaction.atomic():
        profile = get_object_or_404(
            Profile.objects.select_for_update(),
            telegram_id=telegram_id,
        )

        if not profile.whitelist_uuid:
            return JsonResponse(
                {"error": "У вас нет активной whitelist-подписки"},
                status=400,
            )

        balance_dec = Decimal(str(profile.balance))
        if balance_dec < total_price:
            missing = total_price - balance_dec
            return JsonResponse(
                {
                    "error": "insufficient_funds",
                    "missing_amount": float(missing),
                    "extension_price": float(total_price),
                },
                status=400,
            )

        tariff_ref = profile.tarif
        profile.balance = balance_dec - total_price
        profile.save(update_fields=["balance"])

        order = Order.objects.create(
            tariff=tariff_ref,
            telegram_id=telegram_id,
            amount=total_price,
            order_type="WHITELIST_TOPUP",
            status="PAID",
        )
        order_id = order.id

    try:
        bytes_to_add = gb_amount * 1024 * 1024 * 1024

        async def topup_remnawave():
            client = RemnawaveClient()
            try:
                wl_user = await client.get_user(profile.whitelist_uuid)
                current_limit = wl_user.get("trafficLimitBytes", 0)
                new_limit = current_limit + bytes_to_add
                return await client.update_user(
                    uuid=profile.whitelist_uuid,
                    trafficlimitbytes=new_limit,
                )
            finally:
                await client.close()

        result = async_to_sync(topup_remnawave)()

        new_limit = result.get("trafficLimitBytes", 0)
        return JsonResponse(
            {
                "success": True,
                "new_balance": float(profile.balance),
                "new_traffic_limit": new_limit,
            },
        )
    except Exception:
        with transaction.atomic():
            profile = Profile.objects.select_for_update().get(
                telegram_id=telegram_id,
            )
            profile.balance += total_price
            profile.save(update_fields=["balance"])

            Order.objects.filter(id=order_id).update(status="FAILED")

        return JsonResponse(
            {"error": "Ошибка при покупке трафика"},
            status=500,
        )


@csrf_exempt
def platega_callback(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    merchant_id = getattr(settings, "PLATEGA_MERCHANT_ID", "")
    secret = getattr(settings, "PLATEGA_SECRET", "")
    if not merchant_id or not secret:
        return JsonResponse({"error": "Platega not configured"}, status=500)

    callback = PlategaCallback(merchant_id, secret)
    if not callback.validate_django(request):
        logger.warning(
            f"[platega] Callback validation failed"
            f": {callback.get_validation_error()}",
        )
        return JsonResponse(
            {"error": callback.get_validation_error()},
            status=400,
        )

    order_id_str = callback.get_order_id()
    try:
        order_id = int(order_id_str)
    except (ValueError, TypeError):
        logger.warning(
            f"[platega] Invalid order_id in callback: {order_id_str}",
        )
        return JsonResponse({"error": "Invalid order_id"}, status=400)

    status = callback.get_status()
    order = process_platega_callback(order_id, status)
    if not order:
        logger.warning(
            f"[platega] Order #{order_id} not processed"
            f" (not found, already paid, or status ignored)",
        )
        return JsonResponse({"status": "ignored"})

    return JsonResponse({"status": "ok"})
