import asyncio
from datetime import datetime, timedelta
import os

from django.conf import settings
import httpx
from remnawave_api import RemnawaveSDK

__all__ = ["RemnawaveClient"]


class RemnawaveClient:
    def __init__(
        self,
        base_url: str = None,
        token: str = None,
        secret_name: str = None,
        secret_value: str = None,
    ):
        self.base_url = (base_url or settings.REMNAWAVE_URL).rstrip("/")
        self.token = token or settings.REMNAWAVE_TOKEN
        secret_name = secret_name or settings.REMNAWAVE_SECRET_NAME
        secret_value = secret_value or settings.REMNAWAVE_SECRET_VALUE

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

        self.http_client = httpx.AsyncClient(
            base_url=api_url,
            cookies={secret_name: secret_value},
            headers=headers,
        )

        self.sdk = RemnawaveSDK(client=self.http_client)

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
    ):
        expire_at = (
            datetime.utcnow() + timedelta(days=days)
        ).isoformat() + "Z"

        payload = {
            "username": username,
            "expireAt": expire_at,
            "trafficLimitBytes": trafficlimitbytes,
            "trafficLimitStrategy": "NO_RESET",
            "status": status,
            "hwidDeviceLimit": hwiddevicelimit,
            "telegramId": telegramid,
            "activeInternalSquads": activeinternalsquads,
        }

        response = await self.http_client.post("users", json=payload)
        response.raise_for_status()
        return response.json().get("response", {})

    async def get_users(self, size: int = 100, start: int = 0):
        response = await self.http_client.get(
            "users",
            params={"size": size, "start": start},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", {})

    async def get_user(self, uuid: str):
        response = await self.http_client.get(f"users/{uuid}")
        response.raise_for_status()
        data = response.json()
        return data.get("response", {})

    async def get_user_by_tgid(self, tgid: int):
        response = await self.http_client.get(f"users?telegramId={tgid}")
        response.raise_for_status()
        data = response.json()
        return data.get("response", {})

    async def delete_user(self, uuid: str):
        response = await self.http_client.delete(f"users/{uuid}")
        response.raise_for_status()
        data = response.json()
        return data.get("response", {})

    async def delete_user_by_tgid(self, tgid: int):
        response = await self.http_client.delete(f"users?telegramId={tgid}")
        response.raise_for_status()
        data = response.json()
        return data.get("response", {})

    async def get_internal_squads(self):
        response = await self.http_client.get("internal-squads")
        response.raise_for_status()
        data = response.json()
        return data.get("response", {})

    async def close(self):
        """Close the underlying HTTP client."""
        await self.http_client.aclose()


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
            # data = await client.get_users()
            # users = data.get("users", [])
            # total = data.get("total", 0)
            # print(f"Total users: {total}")  # noqa: T201
            # for user in users:
            #     print(  # noqa: T201
            #         f"User: {user.get('username')} (UUID: {user.get('uuid')})",
            #     )

            # nodes = await client.get_nodes()
            # for node in nodes:
            #     print(  # noqa: T201
            #         f"Node: {node.get('name')} (UUID: {node.get('uuid')})",
            #     )
            squads = await client.get_internal_squads()
            print(squads)  # noqa: T201
        except Exception as e:
            print(f"Error: {e}")  # noqa: T201
        finally:
            await client.close()

    asyncio.run(test())
