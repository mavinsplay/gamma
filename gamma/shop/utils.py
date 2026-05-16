import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from django.conf import settings


def verify_telegram_init_data(init_data: str):
    """
    Verifies the data received from the Telegram Web App.
    Returns (True, user_data_dict) if valid, (False, None) otherwise.
    """
    if not init_data:
        return False, None

    try:
        # 1. Parse the init_data string
        parsed_data = dict(parse_qsl(init_data))
        if "hash" not in parsed_data:
            return False, None

        received_hash = parsed_data.pop("hash")

        # 2. Sort keys and create data_check_string
        data_check_string = "\n".join(
            [f"{k}={v}" for k, v in sorted(parsed_data.items())]
        )

        # 3. Get secret key from Bot Token
        # The secret key is HMAC_SHA256(data_check_string, HMAC_SHA256("WebAppData", bot_token))
        secret_key = hmac.new(
            b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256
        ).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        # 4. Compare hashes
        if calculated_hash == received_hash:
            user_data = json.loads(parsed_data.get("user", "{}"))
            return True, user_data

        return False, None
    except Exception as e:
        print(f"Verification error: {e}")
        return False, None


def verify_telegram_login_data(data: dict):
    """
    Verifies the data received from the Telegram Login Widget.
    Returns True if valid, False otherwise.
    As per https://core.telegram.org/widgets/login#checking-authorization
    """
    if "hash" not in data:
        return False

    received_hash = data.pop("hash")

    # 1. Construct data_check_string
    # Sort keys alphabetically and join with \n
    check_list = []
    for k, v in sorted(data.items()):
        if v is not None:
            check_list.append(f"{k}={v}")
    data_check_string = "\n".join(check_list)

    # 2. Secret key is SHA256(bot_token)
    secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()

    # 3. Calculate HMAC-SHA256
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    return calculated_hash == received_hash
