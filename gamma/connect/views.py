import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import NodeStatus
from shop.utils import verify_telegram_init_data


@csrf_exempt
@require_POST
def set_node_status_api(request):
    init_data = request.POST.get("init_data")
    is_valid, tg_user = verify_telegram_init_data(init_data)

    if is_valid:
        telegram_id = tg_user.get("id")
    elif settings.DEBUG:
        telegram_id = request.POST.get("tg_id")
    else:
        return JsonResponse({"error": "Invalid auth"}, status=403)

    if str(telegram_id) != str(settings.ADMIN_TELEGRAM_ID):
        return JsonResponse(
            {"success": False, "error": "Unauthorized"}, status=403
        )

    node_id = request.POST.get("node_id")
    status_text = request.POST.get("status_text")
    use_manual = request.POST.get("use_manual_status") == "true"
    manual_online = request.POST.get("manual_is_online") == "true"

    if not node_id:
        return JsonResponse(
            {"success": False, "error": "Node ID required"}, status=400
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
    """Opens happ:// deep link via system browser (works inside Telegram Mini App)."""
    sub_link = request.GET.get("link", "")
    # sub_link is already a full https:// URL; happ uses happ:// + that URL
    happ_link = "happ://" + sub_link if sub_link else ""
    return render(
        request,
        "connect/open_sub.html",
        {
            "happ_link": happ_link,
            "happ_link_json": json.dumps(happ_link),
        },
    )
