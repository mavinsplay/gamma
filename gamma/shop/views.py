import asyncio
from decimal import Decimal
import re
import uuid

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from connect.services.remnawave import RemnawaveClient
from shop.models import Order, Tariff
from user.models import Profile

__all__ = [
    "app_index",
    "buy_tariff_api",
    "topup_api",
    "buy_slot_api",
    "get_subscription_link_api",
    "checkout_view",
    "mock_payment_view",
    "success_view",
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

    if settings.DEBUG and settings.MOCK_TELEGRAM_USER_DATA["id"]:
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA["id"]

        # If ID matches mock ID, fill in missing username
        if (
            str(telegram_id) == str(settings.MOCK_TELEGRAM_USER_DATA["id"])
            and not telegram_username
        ):
            telegram_username = settings.MOCK_TELEGRAM_USER_DATA.get(
                "username",
            )

    profile = None
    if telegram_id:
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
                    hwid_devices = await client.get_user_hwid_devices(rw_user["uuid"])
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
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Exception in app_index: {e}")
        nodes_data = []
        rw_user = None
        hwid_devices = []

    return render(
        request,
        "base.html",
        {
            "tariffs": tariffs,
            "nodes": nodes_data,
            "profile": profile,
            "debug": settings.DEBUG,
            "rw_user": rw_user,
            "hwid_devices": hwid_devices,
            "mock_user_data": (
                settings.MOCK_TELEGRAM_USER_DATA if settings.DEBUG else None
            ),
        },
    )


def buy_tariff_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    tariff_id = request.POST.get("tariff_id")
    telegram_id = request.POST.get("tg_id")
    telegram_username = request.POST.get("tg_username")

    if settings.DEBUG and settings.MOCK_TELEGRAM_USER_DATA["id"]:
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA["id"]

        if (
            str(telegram_id) == str(settings.MOCK_TELEGRAM_USER_DATA["id"])
            and not telegram_username
        ):
            telegram_username = settings.MOCK_TELEGRAM_USER_DATA.get(
                "username",
            )

    if not telegram_id or not tariff_id:
        return JsonResponse({"error": "Missing params"}, status=400)

    tariff = get_object_or_404(Tariff, id=tariff_id)
    profile, _ = Profile.objects.get_or_create(telegram_id=telegram_id)

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

    # Create user in Remnawave
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

    if not (
        telegram_id
        and settings.DEBUG
        and settings.MOCK_TELEGRAM_USER_DATA["id"]
    ):
        telegram_id = settings.MOCK_TELEGRAM_USER_DATA["id"]

    try:
        amount = float(amount)
        if amount <= 0:
            return JsonResponse({"error": "Invalid amount"}, status=400)
    except ValueError:
        return JsonResponse({"error": "Invalid amount format"}, status=400)

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    profile, _ = Profile.objects.get_or_create(telegram_id=telegram_id)
    profile.balance += Decimal(str(amount))
    profile.save()

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
    if settings.DEBUG and settings.MOCK_TELEGRAM_USER_DATA["id"]:
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA["id"]

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    slot_price = Decimal("100.00")
    profile, _ = Profile.objects.get_or_create(telegram_id=telegram_id)

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
                uuid=rw_user["uuid"],
                hwiddevicelimit=new_limit
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
    if settings.DEBUG and settings.MOCK_TELEGRAM_USER_DATA["id"]:
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA["id"]

    if not telegram_id:
        return JsonResponse({"error": "Missing tg_id"}, status=400)

    async def fetch_link():
        client = RemnawaveClient()
        try:
            rw_user = await client.get_user_by_tgid(telegram_id)
            if isinstance(rw_user, list):
                rw_user = rw_user[0] if len(rw_user) > 0 else None
            if not rw_user or not rw_user.get("uuid"):
                raise ValueError("User not found")
            return await client.get_sub_link(rw_user["uuid"])
        finally:
            await client.close()

    try:
        sub_data = async_to_sync(fetch_link)()
        return JsonResponse({"success": True, "link": sub_data.get("url", sub_data.get("subscriptionUrl", ""))})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def extend_sub_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    telegram_id = request.POST.get("tg_id")
    months = request.POST.get("months")
    
    if settings.DEBUG and settings.MOCK_TELEGRAM_USER_DATA["id"]:
        if not telegram_id:
            telegram_id = settings.MOCK_TELEGRAM_USER_DATA["id"]

    if not telegram_id or not months:
        return JsonResponse({"error": "Missing params"}, status=400)

    try:
        months = int(months)
        if months not in [1, 3, 6, 12]:
            raise ValueError
    except ValueError:
        return JsonResponse({"error": "Invalid months value"}, status=400)

    profile = get_object_or_404(Profile, telegram_id=telegram_id)
    if not profile.tarif:
        return JsonResponse({"error": "No active tariff to extend"}, status=400)

    # Calculate price proportionally: (tariff price / duration days) * (months * 30)
    # We'll assume a standard 30-day month for simplicity, or just calculate price directly
    # If the user's base tariff is for 30 days, 1 month = tariff.price.
    price_per_month = profile.tarif.price / Decimal(str(profile.tarif.duration_days / 30.0))
    total_price = Decimal(str(price_per_month * months)).quantize(Decimal("0.00"))

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
                uuid=rw_user["uuid"],
                expire_at=new_expire_str
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
