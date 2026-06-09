import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
import requests

from user.models import Profile

__all__ = ()


def _get_redirect_uri(request):
    host = request.get_host()
    scheme = "https" if "ngrok" in host else request.scheme
    return f"{scheme}://{host}{reverse('telegram_login_callback')}"


def _generate_pkce():
    """Генерируем code_verifier и code_challenge для PKCE (S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def login_view(request):
    if "tg_user" in request.session:
        return redirect("home")

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _generate_pkce()

    request.session["oauth_state"] = state
    request.session["pkce_verifier"] = code_verifier  # сохраняем для callback

    params = {
        "client_id": settings.TELEGRAM_CLIENT_ID,
        "redirect_uri": _get_redirect_uri(request),
        "response_type": "code",
        "scope": "openid profile",  # добавьте нужные скоупы
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    oauth_host = (
        "oauth.telegram.org"
        if settings.DEBUG
        else "oauth-tg.gamma.careerpiter.ru"
    )
    auth_url = f"https://{oauth_host}/auth?{urlencode(params)}"
    return render(
        request,
        "user/login.html",
        {
            "bot_username": settings.TELEGRAM_BOT_USERNAME,
            "auth_url": auth_url,
        },
    )


def telegram_login_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")

    if not code or state != request.session.get("oauth_state"):
        return render(
            request,
            "user/login.html",
            {
                "error": (
                    "Ошибка авторизации: неверный state"
                    " или код отсутствует."
                ),
                "bot_username": settings.TELEGRAM_BOT_USERNAME,
            },
        )

    code_verifier = request.session.get("pkce_verifier")
    redirect_uri = _get_redirect_uri(request)

    # Basic Auth: base64(client_id:client_secret)
    auth_str = (
        f"{settings.TELEGRAM_CLIENT_ID}" f":{settings.TELEGRAM_CLIENT_SECRET}"
    )
    credentials = base64.b64encode(auth_str.encode()).decode()

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.TELEGRAM_CLIENT_ID,
        "code_verifier": code_verifier,  # PKCE verifier
    }

    try:
        response = requests.post(
            "https://oauth.telegram.org/token",
            data=payload,
            headers={
                "Authorization": (f"Basic {credentials}"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        data = response.json()

        if "id_token" not in data:
            return render(
                request,
                "user/login.html",
                {
                    "error": "Ошибка токена: "
                    + str(
                        data.get(
                            "error_description",
                            data.get("error", data),
                        ),
                    ),
                    "bot_username": settings.TELEGRAM_BOT_USERNAME,
                },
            )

        # Декодируем JWT payload
        payload_b64 = data["id_token"].split(".")[1]
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        user_info = json.loads(base64.urlsafe_b64decode(payload_b64))

        telegram_id = user_info.get("id")
        username = user_info.get("preferred_username")

        profile, _ = Profile.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={"telegram_username": username},
        )

        picture = user_info.get("picture")
        if picture and not settings.DEBUG:
            proxy = "https://oauth-tg.gamma.careerpiter.ru"
            mapping = {
                "cdn.telegram.org": f"{proxy}/cdn",
                "t.me": f"{proxy}/tme",
            }
            parsed = urlparse(picture)
            if parsed.netloc in mapping:
                picture = (
                    mapping[parsed.netloc]
                    + parsed.path
                    + ("?" + parsed.query if parsed.query else "")
                )

        request.session["tg_user"] = {
            "id": telegram_id,
            "username": username,
            "first_name": user_info.get("given_name"),
            "last_name": user_info.get("family_name"),
            "photo_url": picture,
        }

        return redirect("home")

    except Exception:
        return render(
            request,
            "user/login.html",
            {
                "error": "Внутренняя ошибка авторизации",
                "bot_username": settings.TELEGRAM_BOT_USERNAME,
            },
        )


def get_user_status(request):
    user_data = request.session.get("tg_user")
    if user_data:
        return JsonResponse({"authenticated": True, "user": user_data})
    return JsonResponse({"authenticated": False})


def logout_view(request):
    logout(request)
    if "tg_user" in request.session:
        del request.session["tg_user"]

    return JsonResponse({"success": True})
