import re
import uuid

from asgiref.sync import async_to_sync
from django.shortcuts import get_object_or_404, redirect, render

from connect.services.remnawave import RemnawaveClient
from shop.models import Order, Tariff

__all__ = [
    "app_index",
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

    async def fetch_nodes():
        client = RemnawaveClient()
        try:
            return await client.get_nodes()
        finally:
            await client.close()

    try:
        raw_nodes = async_to_sync(fetch_nodes)()
        nodes_data = []
        for node in raw_nodes:
            flag, name = extract_flag(node.get("name", ""))

            # Fallback: if no flag in name, try to convert countryCode
            if not flag:
                flag = country_code_to_flag(node.get("countryCode"))

            node["display_flag"] = flag
            node["display_name"] = name
            nodes_data.append(node)
    except Exception:
        nodes_data = []

    return render(
        request,
        "base.html",
        {
            "tariffs": tariffs,
            "nodes": nodes_data,
        },
    )


def checkout_view(request, tariff_id):
    tariff = get_object_or_404(Tariff, id=tariff_id)
    telegram_id = request.GET.get("tg_id", "123456789")  # Mock telegram ID

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
