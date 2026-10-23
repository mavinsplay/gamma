import asyncio
from datetime import datetime, timedelta
import os

from django.conf import settings
import httpx

__all__ = ["RemnawaveClient", "match_wl_id", "user_ref"]


def user_ref(user):
    """Версионно-независимый идентификатор юзера для update/delete/get.

    3.x: числовой id; 2.x: строковый uuid. Всегда строка — так его можно
    класть в Profile.whitelist_uuid (CharField) и сравнивать со старыми
    значениями. Остальное — для резолва.
    """
    if not isinstance(user, dict):
        return user

    for key in ("id", "uuid"):
        value = user.get(key)
        if value is not None and str(value) != "":
            return str(value)

    for key in ("vlessUuid", "shortUuid", "username"):
        value = user.get(key)
        if value:
            return str(value)

    return None


def _is_numeric_id(value):
    try:
        return str(int(str(value))) == str(value)
    except (TypeError, ValueError):
        return False


def match_wl_id(user, stored):
    """Совпал ли юзер с сохранённым whitelist-идентификатором."""
    if not stored or not isinstance(user, dict):
        return False

    stored = str(stored)
    for key in ("id", "uuid", "vlessUuid", "shortUuid"):
        if user.get(key) is not None and str(user[key]) == stored:
            return True

    return False


class RemnawaveClient:
    def __init__(
        self,
        base_url: str = None,
        token: str = None,
        secret_name: str = None,
        secret_value: str = None,
        api_key: str = None,
    ):
        self.base_url = (base_url or settings.REMNAWAVE_URL).rstrip("/")
        self.token = token or settings.REMNAWAVE_TOKEN
        secret_name = secret_name or settings.REMNAWAVE_SECRET_NAME
        secret_value = secret_value or settings.REMNAWAVE_SECRET_VALUE
        api_key = api_key or getattr(settings, "REMNAWAVE_API_KEY", "")

        api_url = self.base_url
        if not api_url.endswith("/api"):
            api_url = f"{api_url}/api"

        if not api_url.endswith("/"):
            api_url = f"{api_url}/"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 "
            "Safari/537.36",
        }
        # 3.x за Caddy ходит по X-Api-Key; 2.x — по cookie. Шлём оба,
        # лишнее панель игнорирует.
        if api_key:
            headers["X-Api-Key"] = api_key

        transport = httpx.AsyncHTTPTransport(retries=5)
        self.http_client = httpx.AsyncClient(
            transport=transport,
            base_url=api_url,
            cookies={secret_name: secret_value},
            headers=headers,
            timeout=30.0,
        )

    async def _resolve_numeric_id(self, identifier):
        """Числовой id юзера (3.x) из любого идентификатора."""
        if _is_numeric_id(identifier):
            return int(str(identifier))

        ident = str(identifier)
        for path in (
            f"users/by-short-uuid/{ident}",
            f"users/by-username/{ident}",
        ):
            try:
                response = await self.http_client.get(path)
                response.raise_for_status()
                data = response.json().get("response", {})
                if isinstance(data, dict) and _is_numeric_id(data.get("id")):
                    return int(data["id"])
            except Exception:
                continue

        for body in ({"shortUuid": ident}, {"username": ident}):
            try:
                response = await self.http_client.post(
                    "users/resolve",
                    json=body,
                )
                response.raise_for_status()
                data = response.json().get("response", {})
                if isinstance(data, dict) and _is_numeric_id(data.get("id")):
                    return int(data["id"])
            except Exception:
                continue

        raise ValueError(f"Cannot resolve Remnawave user id for {ident!r}")

    async def get_nodes(self):
        response = await self.http_client.get("nodes")
        response.raise_for_status()
        return response.json().get("response")

    async def create_user(
        self,
        username: str,
        days: int,
        trafficlimitbytes: int = 0,
        hwiddevicelimit: int = 0,
        telegramid: int = None,
        activeinternalsquads: list[str] = None,
        status: str = "ACTIVE",
        externalsquaduuid: str = None,
        trafficlimitstrategy: str = "NO_RESET",
    ):
        expire_at = (
            datetime.utcnow() + timedelta(days=days)
        ).isoformat() + "Z"

        payload = {
            "username": username,
            "expireAt": expire_at,
            "trafficLimitBytes": trafficlimitbytes,
            "trafficLimitStrategy": trafficlimitstrategy,
            "status": status,
            "hwidDeviceLimit": hwiddevicelimit,
            "telegramId": telegramid,
            "activeInternalSquads": activeinternalsquads,
            "externalSquadUuid": externalsquaduuid,
        }

        response = await self.http_client.post("users", json=payload)
        response.raise_for_status()
        return response.json().get("response", {})

    async def update_user(
        self,
        uuid: str,
        username: str = None,
        expire_at: str = None,
        trafficlimitbytes: int = None,
        hwiddevicelimit: int = None,
        telegramid: int = None,
        status: str = None,
        activeinternalsquads: list = None,
        externalsquaduuid: str = None,
        trafficlimitstrategy: str = None,
    ):
        # Fetch current user to merge data
        current_user = await self.get_user(uuid)

        # Extract activeInternalSquads UUIDs if they are dictionaries
        squads = current_user.get("activeInternalSquads", [])
        squad_uuids = (
            activeinternalsquads
            if activeinternalsquads is not None
            else [s.get("uuid") if isinstance(s, dict) else s for s in squads]
        )

        merged = {
            "username": (
                username
                if username is not None
                else current_user.get("username", "")
            ),
            "status": (
                status
                if status is not None
                else current_user.get("status", "ACTIVE")
            ),
            "trafficLimitBytes": (
                trafficlimitbytes
                if trafficlimitbytes is not None
                else current_user.get("trafficLimitBytes", 0)
            ),
            "trafficLimitStrategy": (
                trafficlimitstrategy
                if trafficlimitstrategy is not None
                else current_user.get("trafficLimitStrategy", "NO_RESET")
            ),
            "expireAt": (
                expire_at
                if expire_at is not None
                else current_user.get("expireAt", "")
            ),
            "description": current_user.get("description"),
            "tag": current_user.get("tag", ""),
            "telegramId": (
                telegramid
                if telegramid is not None
                else current_user.get("telegramId")
            ),
            "email": current_user.get("email"),
            "hwidDeviceLimit": (
                hwiddevicelimit
                if hwiddevicelimit is not None
                else current_user.get("hwidDeviceLimit", 0)
            ),
            "activeInternalSquads": squad_uuids,
            "externalSquadUuid": (
                externalsquaduuid
                if externalsquaduuid is not None
                else current_user.get("externalSquadUuid")
            ),
        }

        numeric_id = (
            current_user.get("id") if isinstance(current_user, dict) else None
        )
        # 3.x-first (numeric id), 2.x-fallback (uuid string).
        attempts = []
        if _is_numeric_id(numeric_id):
            attempts.append({"id": int(str(numeric_id)), **merged})

        attempts.append({"uuid": user_ref(current_user) or uuid, **merged})
        last_error = None
        for payload in attempts:
            try:
                response = await self.http_client.patch("users", json=payload)
                response.raise_for_status()
                return response.json().get("response", {})
            except Exception as e:
                last_error = e
                status_code = getattr(
                    getattr(e, "response", None),
                    "status_code",
                    None,
                )
                if status_code not in (None, 400, 404, 405, 422):
                    raise

        raise last_error

    async def get_users(self, size: int = 100, start: int = 0):
        response = await self.http_client.get(
            "users",
            params={"size": size, "start": start},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", {})

    async def get_users_stream(self, size: int = 250, cursor=None, **filters):
        """Одна страница cursor-пагинации users/stream.

        Возвращает словарь {users, nextCursor, hasMore}.
        """
        params = {"size": size}
        if cursor is not None:
            params["cursor"] = cursor

        for key, value in filters.items():
            if value is not None:
                params[key] = value

        response = await self.http_client.get("users/stream", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("response", data)

    async def get_all_users_stream(self, size: int = 250, **filters):
        """Все пользователи панели одним проходом по курсору.

        3.x может не отдавать users/stream — тогда падаем на обычную
        пагинацию users?size&start (как в 2.x).
        """
        try:
            users = []
            cursor = None
            while True:
                page = await self.get_users_stream(
                    size=size,
                    cursor=cursor,
                    **filters,
                )
                if not isinstance(page, dict):
                    if isinstance(page, list):
                        users.extend(page)

                    break

                users.extend(page.get("users", []) or [])
                if not page.get("hasMore"):
                    break

                cursor = page.get("nextCursor")
                if cursor is None:
                    break

            return users
        except Exception as e:
            status = getattr(
                getattr(e, "response", None),
                "status_code",
                None,
            )
            if status not in (404, 405):
                raise

        users = []
        start = 0
        while True:
            response = await self.get_users(size=size, start=start)
            if isinstance(response, dict):
                page = response.get("users", [])
            else:
                page = response or []

            users.extend(page)
            if not page:
                break

            start += len(page)

        return users

    async def get_whitelist_user(self, telegram_id, stored=None):
        """_wl-юзер: сначала по сохранённому id, иначе по суффиксу _wl.

        Сохранённый id после переезда 2.x -> 3.x протухает (старый uuid),
        поэтому несовпадение — не ошибка, а повод найти по username.
        Возвращает dict юзера или None (список получен, _wl нет).
        """
        users = await self.get_user_by_tgid(int(telegram_id))
        if isinstance(users, dict):
            inner = users.get("users")
            users = (
                inner
                if isinstance(inner, list)
                else ([users] if users else [])
            )

        if not isinstance(users, list):
            return None

        if stored:
            hit = next(
                (u for u in users if match_wl_id(u, stored)),
                None,
            )
            if hit is not None:
                return hit

        return next(
            (u for u in users if (u.get("username") or "").endswith("_wl")),
            None,
        )

    async def get_user(self, uuid: str):
        """Карточка юзера по любому идентификатору.

        3.x: числовой id; также shortUuid/username через resolve.
        2.x-fallback: users/{uuid} напрямую.
        """
        if _is_numeric_id(uuid):
            response = await self.http_client.get(f"users/{uuid}")
            response.raise_for_status()
            return response.json().get("response", {})

        ident = str(uuid)
        for path in (
            f"users/by-short-uuid/{ident}",
            f"users/by-username/{ident}",
        ):
            try:
                response = await self.http_client.get(path)
                response.raise_for_status()
                return response.json().get("response", {})
            except Exception as e:
                status = getattr(
                    getattr(e, "response", None),
                    "status_code",
                    None,
                )
                if status not in (None, 400, 404, 405, 422):
                    raise

        for body in ({"shortUuid": ident}, {"username": ident}):
            try:
                response = await self.http_client.post(
                    "users/resolve",
                    json=body,
                )
                response.raise_for_status()
                data = response.json().get("response", {})
                if isinstance(data, dict) and _is_numeric_id(data.get("id")):
                    return await self.get_user(int(data["id"]))
            except Exception as e:
                status = getattr(
                    getattr(e, "response", None),
                    "status_code",
                    None,
                )
                if status not in (None, 400, 404, 405, 422):
                    raise

        # Legacy 2.x: users/{uuid}.
        response = await self.http_client.get(f"users/{uuid}")
        response.raise_for_status()
        return response.json().get("response", {})

    async def get_user_by_tgid(self, tgid: int):
        """Юзеры по telegramId. 2.x-first, 3.x-fallback.

        В 3.x `users/by-telegram-id` удалён (404) — вместо него фильтр
        `users/stream?telegramId=`. Фильтр проверяем клиентской
        сверкой telegramId, чтобы не подхватить чужую страницу.
        Возвращает список юзеров (может быть пустым).
        """
        try:
            response = await self.http_client.get(
                f"users/by-telegram-id/{tgid}",
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", {})
        except Exception as e:
            status = getattr(
                getattr(e, "response", None),
                "status_code",
                None,
            )
            if status not in (None, 404, 405):
                raise

        users = []
        cursor = None
        while True:
            page = await self.get_users_stream(
                size=100,
                cursor=cursor,
                telegramId=tgid,
            )
            if not isinstance(page, dict):
                if isinstance(page, list):
                    users.extend(
                        u
                        for u in page
                        if str((u or {}).get("telegramId")) == str(tgid)
                    )

                break

            for u in page.get("users", []) or []:
                if str((u or {}).get("telegramId")) == str(tgid):
                    users.append(u)

            if not page.get("hasMore"):
                break

            cursor = page.get("nextCursor")
            if cursor is None:
                break

        return users

    async def delete_user(self, uuid: str):
        """Удаление юзера. 3.x ждёт числовой id (204), 2.x — uuid."""
        try:
            numeric_id = await self._resolve_numeric_id(uuid)
        except ValueError:
            numeric_id = None

        if numeric_id is not None:
            try:
                response = await self.http_client.delete(f"users/{numeric_id}")
                response.raise_for_status()
                try:
                    return response.json().get("response", {})
                except Exception:
                    return {}
            except Exception as e:
                status = getattr(
                    getattr(e, "response", None),
                    "status_code",
                    None,
                )
                if status not in (None, 400, 404, 405, 422):
                    raise

        # Legacy 2.x.
        response = await self.http_client.delete(f"users/{uuid}")
        response.raise_for_status()
        try:
            return response.json().get("response", {})
        except Exception:
            return {}

    async def get_internal_squads(self):
        response = await self.http_client.get("internal-squads")
        response.raise_for_status()
        data = response.json()
        return data.get("response", {})

    async def close(self):
        """Close the underlying HTTP client."""
        await self.http_client.aclose()

    async def get_sub_link(self, uuid: str):
        """Ссылка на подписку. 3.x-first, 2.x-fallback.

        В 3.x `subscriptions/by-uuid` удалён; ссылка уже лежит в карточке
        юзера (subscriptionUrl), запасной путь — `/sub/{shortUuid}`.
        На входе — любой идентификатор (id/shortUuid/username/uuid).
        """
        user = None
        try:
            user = await self.get_user(uuid)
        except Exception:
            user = None

        if isinstance(user, dict):
            for key in ("subscriptionUrl", "url", "link"):
                if user.get(key):
                    url = str(user[key])
                    return {"url": url, "subscriptionUrl": url}

        short_uuid = ""
        if isinstance(user, dict):
            for key in ("shortUuid", "short_uuid", "shortId", "short_id"):
                if user.get(key):
                    short_uuid = str(user[key])
                    break

        if not short_uuid:
            # Вход уже может быть коротким UUID.
            short_uuid = str(uuid) if len(str(uuid)) < 32 else ""

        if short_uuid:
            try:
                response = await self.http_client.get(f"sub/{short_uuid}")
                response.raise_for_status()
                try:
                    data = response.json()
                except Exception:
                    data = None

                if isinstance(data, str) and data:
                    return {"url": data, "subscriptionUrl": data}

                if isinstance(data, dict):
                    url = (
                        data.get("url")
                        or data.get("subscriptionUrl")
                        or data.get("link")
                        or ""
                    )
                    if url:
                        return data

                    return data

                text = (response.text or "").strip()
                if text.startswith("http") or text.startswith("sub"):
                    return {"url": text, "subscriptionUrl": text}
            except Exception as e:
                status = getattr(
                    getattr(e, "response", None),
                    "status_code",
                    None,
                )
                # 404 по короткому — пробуем legacy, остальное не глотаем,
                # если legacy тоже не ответит.
                if status not in (None, 404, 405):
                    pass

        # Legacy 2.x.
        response = await self.http_client.get(f"subscriptions/by-uuid/{uuid}")
        response.raise_for_status()
        data = response.json()
        return data.get("response", {})

    async def get_user_hwid_devices(self, uuid: str):
        """Устройства юзера. 3.x ждёт числовой id, 2.x — uuid."""
        try:
            numeric_id = await self._resolve_numeric_id(uuid)
        except ValueError:
            numeric_id = None

        identifiers = ([str(numeric_id)] if numeric_id is not None else []) + [
            str(uuid),
        ]
        last_error = None
        for identifier in dict.fromkeys(identifiers):
            try:
                response = await self.http_client.get(
                    f"hwid/devices/{identifier}",
                )
                response.raise_for_status()
                data = response.json().get("response", {})
                if isinstance(data, dict):
                    return data.get("devices", [])

                if isinstance(data, list):
                    return data

                return []
            except Exception as e:
                last_error = e
                status = getattr(
                    getattr(e, "response", None),
                    "status_code",
                    None,
                )
                if status not in (None, 400, 404, 405, 422):
                    raise

        raise last_error

    async def delete_hwid_device(self, user_uuid: str, hwid: str):
        """Удаление устройства. 3.x: {userId, hwid}, 2.x: {userUuid}."""
        try:
            numeric_id = await self._resolve_numeric_id(user_uuid)
        except ValueError:
            numeric_id = None

        bodies = (
            [{"userId": numeric_id, "hwid": hwid}]
            if numeric_id is not None
            else []
        ) + [{"userUuid": str(user_uuid), "hwid": hwid}]
        last_error = None
        for body in bodies:
            try:
                response = await self.http_client.post(
                    "hwid/devices/delete",
                    json=body,
                )
                response.raise_for_status()
                return response.json().get("response", {})
            except Exception as e:
                last_error = e
                status = getattr(
                    getattr(e, "response", None),
                    "status_code",
                    None,
                )
                if status not in (None, 400, 404, 405, 422):
                    raise

        raise last_error


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    async def test():
        client = RemnawaveClient(
            base_url=os.getenv("REMNAWAVE_URL"),
            token=os.getenv("REMNAWAVE_TOKEN"),
            secret_name=os.getenv("REMNAWAVE_SECRET_NAME"),
            secret_value=os.getenv("REMNAWAVE_SECRET_VALUE"),
        )
        try:
            user = await client.get_user_hwid_devices(
                "",
            )
            print(user)  # noqa: T201
        except Exception as e:
            print(f"Error: {e}")  # noqa: T201
        finally:
            await client.close()

    asyncio.run(test())
