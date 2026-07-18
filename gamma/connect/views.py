import json
from urllib.parse import urlsplit

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from connect.models import NodeStatus
from shop.utils import verify_telegram_init_data

__all__ = ()


@csrf_exempt
@require_POST
def set_node_status_api(request):
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

    if str(telegram_id) != str(settings.ADMIN_TELEGRAM_ID):
        return JsonResponse(
            {"success": False, "error": "Unauthorized"},
            status=403,
        )

    node_id = request.POST.get("node_id")
    status_text = request.POST.get("status_text")
    use_manual = request.POST.get("use_manual_status") == "true"
    manual_online = request.POST.get("manual_is_online") == "true"

    if not node_id:
        return JsonResponse(
            {"success": False, "error": "Node ID required"},
            status=400,
        )

    status, created = NodeStatus.objects.update_or_create(
        node_id=node_id,
        defaults={
            "status_text": status_text,
            "use_manual_status": use_manual,
            "manual_is_online": manual_online,
        },
    )

    return JsonResponse({"success": True})


def open_sub_redirect(request):
    """Open happ:// deep link via system browser (works in Telegram Mini App).
    No auth required — only constructs a happ:// deep link, no user data exposed.
    """  # noqa: E501
    sub_link = request.GET.get("link", "")
    parsed_link = urlsplit(sub_link)
    if (
        parsed_link.scheme != "https"
        or not parsed_link.netloc
        or parsed_link.username
        or parsed_link.password
    ):
        happ_link = ""
    else:
        happ_link = f"happ://add/{sub_link}"

    return render(
        request,
        "connect/open_sub.html",
        {
            "happ_link": happ_link,
            "happ_link_json": json.dumps(happ_link).replace("<", "\\u003c"),
        },
    )
