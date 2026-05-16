import asyncio
from decimal import Decimal
import json
import re
import uuid

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from connect.services.remnawave import RemnawaveClient
from shop.models import Order, Tariff
from shop.utils import verify_telegram_init_data
from user.models import Profile

__all__ = [
    "app_index",
    "buy_tariff_api",
    "topup_api",
    "buy_slot_api",
    "get_subscription_link_api",
    "delete_hwid_device_api",
    "checkout_view",
    "mock_payment_view",
    "success_view",
    "sync_data_api",
]


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
    telegram_id = request.GET.get("tg_id")
    telegram_username = request.GET.get("tg_username")

    # 1. Check for DEBUG mode (Legacy URL param)
    profile = None
    if settings.DEBUG and telegram_id:
        profile, created = Profile.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                "telegram_username": telegram_username,
                "balance": 0.00,
                "tarif": None,
            },
        )
        if not created and telegram_username and not profile.telegram_username:
            profile.telegram_username = telegram_username
            profile.save()

    # 2. Handle authentication
    # If we have a session user, use it.
    if not profile and "tg_user" in request.session:
        telegram_id = request.session["tg_user"]["id"]
        profile = Profile.objects.filter(telegram_id=telegram_id).first()

    # We allow the page to load without a redirect here.
    # The JS in app.js will handle the redirect for browsers.
    pass

    # If not DEBUG and not logged in, profile will be None.
    # The JS will then call sync-data-api with initData to fetch/create the real profile.

    async def fetch_all():
        client = RemnawaveClient()
        try:
            tasks = [asyncio.create_task(client.get_nodes())]
            if profile:
                tasks.append(
                    asyncio.create_task(client.get_user_by_tgid(telegram_id)),
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            raw_nodes = results[0] if results else []
            rw_user = results[1] if len(results) > 1 else None

            if isinstance(raw_nodes, Exception):
                raw_nodes = []

            if isinstance(rw_user, Exception):
                rw_user = None
            elif isinstance(rw_user, list):
                rw_user = rw_user[0] if len(rw_user) > 0 else None

            hwid_devices = []
            if rw_user and rw_user.get("uuid"):
                try:
                    hwid_devices = await client.get_user_hwid_devices(
                        rw_user["uuid"]
                    )
                except Exception:
                    pass

            return raw_nodes, rw_user, hwid_devices
        finally:
            await client.close()

    try:
        from datetime import datetime, timezone

        raw_nodes, rw_user, hwid_devices = async_to_sync(fetch_all)()
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
            except ValueError:
                pass

        online_count = sum(1 for node in nodes_data if node.get("isConnected"))
        offline_count = len(nodes_data) - online_count

        # Proxy Bypass logic
        proxies = []
        if profile and profile.tarif:
            from connect.models import Proxy

            proxies = profile.tarif.proxies.filter(is_active=True)

        # Payment History logic
        payments = []
        if profile:
            payments = Order.objects.filter(telegram_id=telegram_id).order_by(
                "-created_at"
            )[:20]

    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Exception in app_index: {e}")
        nodes_data = []
        rw_user = None
        hwid_devices = []
        online_count = 0
        offline_count = 0
        proxies = []
        payments = []

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
        },
    )


def buy_tariff_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    tariff_id = request.POST.get("tariff_id")
    init_data = request.POST.get("init_data")

    # 1. Verify Identity
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")
    elif settings.DEBUG:
        # Fallback to legacy/mock only in debug
        telegram_id = request.POST.get("tg_id")
        telegram_username = request.POST.get("tg_username")
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA.get("id")
            telegram_username = settings.MOCK_TELEGRAM_USER_DATA.get(
                "username"
            )
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id or not tariff_id:
        return JsonResponse({"error": "Missing params"}, status=400)

    tariff = get_object_or_404(Tariff, id=tariff_id)
    profile, created = Profile.objects.get_or_create(telegram_id=telegram_id)
    if telegram_username and profile.telegram_username != telegram_username:
        profile.telegram_username = telegram_username
        profile.save()

    if profile.balance < tariff.price:
        missing = tariff.price - profile.balance
        return JsonResponse(
            {
                "error": "insufficient_funds",
                "missing_amount": float(missing),
                "tariff_price": float(tariff.price),
            },
            status=400,
        )

    replace = request.POST.get("replace") == "true"

    if replace:
        # Replace existing subscription — update user in Remnawave
        async def replace_sub():
            from datetime import datetime, timedelta, timezone

            client = RemnawaveClient()
            try:
                rw_user = await client.get_user_by_tgid(telegram_id)
                if isinstance(rw_user, list):
                    rw_user = rw_user[0] if len(rw_user) > 0 else None
                if not rw_user or not rw_user.get("uuid"):
                    raise ValueError("User not found in Remnawave")

                new_expire = (
                    (
                        datetime.now(timezone.utc)
                        + timedelta(days=tariff.duration_days)
                    )
                    .isoformat()
                    .replace("+00:00", "Z")
                )

                return await client.update_user(
                    uuid=rw_user["uuid"],
                    expire_at=new_expire,
                    trafficlimitbytes=tariff.traffic_limit_bytes,
                    hwiddevicelimit=tariff.device_limit,
                )
            finally:
                await client.close()

        try:
            with transaction.atomic():
                profile.balance -= tariff.price
                profile.tarif = tariff
                profile.save()

                Order.objects.create(
                    tariff=tariff,
                    telegram_id=telegram_id,
                    amount=tariff.price,
                    order_type="PURCHASE",
                    status="PAID",
                )

                rw_data = async_to_sync(replace_sub)()

            return JsonResponse(
                {
                    "success": True,
                    "new_balance": float(profile.balance),
                    "sub": rw_data,
                },
            )
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # Create user in Remnawave (new subscription)
    async def provision():
        client = RemnawaveClient()
        username = f"{telegram_username}_{telegram_id}"
        try:
            return await client.create_user(
                username=username,
                days=tariff.duration_days,
                trafficlimitbytes=tariff.traffic_limit_bytes,
                hwiddevicelimit=tariff.device_limit,
                telegramid=int(telegram_id),
                activeinternalsquads=[tariff.squad_uuid],
            )
        finally:
            await client.close()

    try:
        with transaction.atomic():
            # Deduct balance
            profile.balance -= tariff.price
            profile.tarif = tariff
            profile.save()

            # Create Order
            Order.objects.create(
                tariff=tariff,
                telegram_id=telegram_id,
                amount=tariff.price,
                order_type="PURCHASE",
                status="PAID",
            )

            # Provision VPN via Remnawave
            rw_data = async_to_sync(provision)()

        return JsonResponse(
            {
                "success": True,
                "new_balance": float(profile.balance),
                "sub": rw_data,
            },
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def topup_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    telegram_id = request.POST.get("tg_id")
    amount = request.POST.get("amount", 0)

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")
    elif settings.DEBUG:
        telegram_id = request.POST.get("tg_id")
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA.get("id")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid tg_id format"}, status=400)

    try:
        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            return JsonResponse(
                {"error": "Сумма должна быть больше нуля"}, status=400
            )
        if amount_dec > 100000:
            return JsonResponse(
                {
                    "error": "Сумма недопустима. Максимальная сумма пополнения — 100 000 рублей."
                },
                status=400,
            )
    except Exception:
        return JsonResponse({"error": "Некорректная сумма"}, status=400)

    profile, created = Profile.objects.get_or_create(telegram_id=telegram_id)
    # topup_api might not always get username but we update if it's there
    telegram_username = request.POST.get("tg_username")
    if telegram_username and profile.telegram_username != telegram_username:
        profile.telegram_username = telegram_username
        profile.save()
    profile.balance += amount_dec
    profile.save()

    # Create top-up order
    Order.objects.create(
        telegram_id=telegram_id,
        amount=amount_dec,
        order_type="TOPUP",
        status="PAID",
    )

    return JsonResponse(
        {
            "success": True,
            "new_balance": float(profile.balance),
        },
    )


def buy_slot_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    telegram_id = request.POST.get("tg_id")
    telegram_username = request.POST.get("tg_username")

    has_mock = getattr(
        settings, "MOCK_TELEGRAM_USER_DATA", None
    ) and isinstance(settings.MOCK_TELEGRAM_USER_DATA, dict)
    if (
        settings.DEBUG
        and has_mock
        and settings.MOCK_TELEGRAM_USER_DATA.get("id")
    ):
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA.get("id")
            if not telegram_username:
                telegram_username = settings.MOCK_TELEGRAM_USER_DATA.get(
                    "username"
                )

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")
    elif settings.DEBUG:
        telegram_id = request.POST.get("tg_id")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid tg_id format"}, status=400)

    slot_price = Decimal("100.00")
    profile, created = Profile.objects.get_or_create(telegram_id=telegram_id)
    if telegram_username and profile.telegram_username != telegram_username:
        profile.telegram_username = telegram_username
        profile.save()

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

    async def add_slot():
        client = RemnawaveClient()
        try:
            rw_user = await client.get_user_by_tgid(telegram_id)
            if isinstance(rw_user, list):
                rw_user = rw_user[0] if len(rw_user) > 0 else None
            if not rw_user or not rw_user.get("uuid"):
                raise ValueError("User not found in Remnawave")

            current_limit = rw_user.get("hwidDeviceLimit", 0)
            new_limit = current_limit + 1

            return await client.update_user(
                uuid=rw_user["uuid"], hwiddevicelimit=new_limit
            )
        finally:
            await client.close()

    try:
        with transaction.atomic():
            profile.balance -= slot_price
            profile.save()

            # Note: We probably want to record this in Order model too, but skipping for now or maybe just deduct.
            rw_data = async_to_sync(add_slot)()

        return JsonResponse(
            {
                "success": True,
                "new_balance": float(profile.balance),
                "new_limit": rw_data.get("hwidDeviceLimit"),
            },
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def get_subscription_link_api(request):
    telegram_id = request.GET.get("tg_id")
    telegram_username = request.POST.get("tg_username")

    init_data = request.GET.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")
    elif settings.DEBUG:
        telegram_id = request.GET.get("tg_id")
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA.get("id")
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

    async def fetch_link():
        client = RemnawaveClient()
        try:
            try:
                rw_user = await client.get_user_by_tgid(telegram_id)
                if isinstance(rw_user, list):
                    rw_user = rw_user[0] if len(rw_user) > 0 else None
            except Exception as e:
                print(f"Error fetching user from Remnawave: {e}")
                rw_user = None

            if not rw_user or not rw_user.get("uuid"):
                # Auto-heal: If user has tariff in DB but missing in Remnawave, re-provision
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
                            "User not found and failed to re-provision"
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
                    "url", sub_data.get("subscriptionUrl", "")
                ),
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def delete_hwid_device_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    telegram_id = request.POST.get("tg_id")
    hwid = request.POST.get("hwid")

    has_mock = getattr(
        settings, "MOCK_TELEGRAM_USER_DATA", None
    ) and isinstance(settings.MOCK_TELEGRAM_USER_DATA, dict)
    if (
        settings.DEBUG
        and has_mock
        and settings.MOCK_TELEGRAM_USER_DATA.get("id")
    ):
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA.get("id")

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
    elif settings.DEBUG:
        telegram_id = request.POST.get("tg_id")
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
            rw_user = await client.get_user_by_tgid(telegram_id)
            if isinstance(rw_user, list):
                rw_user = rw_user[0] if len(rw_user) > 0 else None
            if not rw_user or not rw_user.get("uuid"):
                raise ValueError("User not found in Remnawave")
            await client.delete_hwid_device(rw_user["uuid"], hwid)
        finally:
            await client.close()

    try:
        async_to_sync(do_delete)()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def extend_sub_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    telegram_id = request.POST.get("tg_id")
    months = request.POST.get("months")

    has_mock = getattr(
        settings, "MOCK_TELEGRAM_USER_DATA", None
    ) and isinstance(settings.MOCK_TELEGRAM_USER_DATA, dict)
    if (
        settings.DEBUG
        and has_mock
        and settings.MOCK_TELEGRAM_USER_DATA.get("id")
    ):
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA.get("id")

    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
    elif settings.DEBUG:
        telegram_id = request.POST.get("tg_id")
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

    profile = get_object_or_404(Profile, telegram_id=telegram_id)
    if not profile.tarif:
        return JsonResponse(
            {"error": "No active tariff to extend"}, status=400
        )

    # Calculate price proportionally: (tariff price / duration days) * (months * 30)
    # We'll assume a standard 30-day month for simplicity, or just calculate price directly
    # If the user's base tariff is for 30 days, 1 month = tariff.price.
    price_per_month = profile.tarif.price / Decimal(
        str(profile.tarif.duration_days / 30.0)
    )
    total_price = Decimal(str(price_per_month * months)).quantize(
        Decimal("0.00")
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

    async def extend_remnawave():
        client = RemnawaveClient()
        try:
            rw_user = await client.get_user_by_tgid(telegram_id)
            if isinstance(rw_user, list):
                rw_user = rw_user[0] if len(rw_user) > 0 else None
            if not rw_user or not rw_user.get("uuid"):
                raise ValueError("User not found in Remnawave")

            current_expire_str = rw_user.get("expireAt")
            from datetime import datetime, timedelta, timezone

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
            new_expire_str = new_expire_dt.isoformat().replace("+00:00", "Z")

            return await client.update_user(
                uuid=rw_user["uuid"], expire_at=new_expire_str
            )
        finally:
            await client.close()

    try:
        with transaction.atomic():
            profile.balance -= total_price
            profile.save()

            Order.objects.create(
                tariff=profile.tarif,
                telegram_id=telegram_id,
                amount=total_price,
                order_type="PURCHASE",
                status="PAID",
            )

            async_to_sync(extend_remnawave)()

            return JsonResponse(
                {
                    "success": True,
                    "new_balance": float(profile.balance),
                },
            )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


def checkout_view(request, tariff_id):
    tariff = get_object_or_404(Tariff, id=tariff_id)
    telegram_id = request.GET.get("tg_id", "123456789")

    if request.method == "POST":
        order = Order.objects.create(
            tariff=tariff,
            telegram_id=telegram_id,
            status="PENDING",
        )
        return redirect("mock_payment", order_id=order.id)

    return render(
        request,
        "shop/checkout.html",
        {"tariff": tariff, "telegram_id": telegram_id},
    )


def mock_payment_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        order.status = "PAID"
        order.save()

        # Provision VPN via Remnawave
        client = RemnawaveClient()
        username = f"tg_{order.telegram_id}_{uuid.uuid4().hex[:6]}"

        try:
            rw_data = client.create_user(
                username=username,
                days=order.tariff.duration_days,
                trafficlimitbytes=order.tariff.traffic_limit_bytes,
            )

            return render(request, "shop/success.html", {"sub": rw_data})

        except Exception as e:
            order.status = "FAILED"
            order.save()
            return render(request, "shop/error.html", {"error": str(e)})

    return render(request, "shop/mock_payment.html", {"order": order})


def success_view(request, sub_id):
    return render(request, "shop/success.html", {"sub": {}})


def sync_data_api(request):
    init_data = request.GET.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
        telegram_username = tg_user.get("username")

        # Securely create or update profile
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
        telegram_id = request.GET.get("tg_id")
        if not telegram_id:
            # Check if settings.MOCK_TELEGRAM_USER_DATA is not None
            if settings.MOCK_TELEGRAM_USER_DATA:
                telegram_id = settings.MOCK_TELEGRAM_USER_DATA.get("id")
            else:
                return JsonResponse({"error": "No mock data"}, status=400)

        try:
            telegram_id = int(telegram_id)
            profile = Profile.objects.filter(telegram_id=telegram_id).first()
        except (ValueError, TypeError):
            profile = None
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if not profile:
        # If profile doesn't exist and we couldn't create it
        return JsonResponse(
            {"success": True, "profile": None, "rw_user": None}
        )

    async def fetch_sync_data():
        client = RemnawaveClient()
        try:
            tasks = [asyncio.create_task(client.get_nodes())]
            if telegram_id:
                tasks.append(
                    asyncio.create_task(client.get_user_by_tgid(telegram_id)),
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            raw_nodes = results[0] if results else []
            rw_user = results[1] if len(results) > 1 else None

            if isinstance(raw_nodes, Exception):
                raw_nodes = []

            if isinstance(rw_user, Exception):
                rw_user = None
            elif isinstance(rw_user, list):
                rw_user = rw_user[0] if len(rw_user) > 0 else None

            hwid_devices = []
            if rw_user and rw_user.get("uuid"):
                try:
                    hwid_devices = await client.get_user_hwid_devices(
                        rw_user["uuid"]
                    )
                except Exception:
                    pass

            return (
                raw_nodes,
                rw_user,
                hwid_devices,
                isinstance(results[0] if results else None, Exception),
            )
        finally:
            await client.close()

    try:
        from datetime import datetime, timezone

        raw_nodes, rw_user, hwid_devices, nodes_error = async_to_sync(
            fetch_sync_data
        )()
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
            except ValueError:
                pass

        # Payment History
        payments = []
        if profile:
            qs = Order.objects.filter(telegram_id=telegram_id).order_by(
                "-created_at"
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
                    }
                )

        # Proxy Bypass logic
        proxies_data = []
        if profile and profile.tarif:
            from connect.models import Proxy

            active_proxies = profile.tarif.proxies.filter(is_active=True)
            for p in active_proxies:
                proxies_data.append(
                    {"name": p.name, "connection_url": p.connection_url}
                )

        is_admin = str(telegram_id) == str(settings.ADMIN_TELEGRAM_ID)

        from connect.models import NodeStatus

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
                        "payment_reminder_enabled": profile.payment_reminder_enabled,
                        "notifications_enabled": profile.notifications_enabled,
                    }
                    if profile
                    else None
                ),
                "rw_user": rw_user,
                "hwid_devices": hwid_devices,
                "nodes": nodes_data,
                "nodes_error": nodes_error,
                "online_count": online_count,
                "offline_count": offline_count,
                "payments": payments,
                "proxies": proxies_data,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def update_preferences_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    telegram_id = request.POST.get("tg_id")
    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
    elif settings.DEBUG:
        telegram_id = request.POST.get("tg_id")
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
    else:
        return JsonResponse({"error": "Invalid type"}, status=400)

    profile.save()
    return JsonResponse({"success": True})
