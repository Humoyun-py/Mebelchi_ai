"""HTTP client for the Django API. The bot holds no business data: every operation goes through the backend,
authenticated with the shared bot secret and acting on behalf of a linked account (telegram_id)."""
from typing import Any

import httpx


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str, fields: dict | None = None):
        super().__init__(f"{status} {code}: {detail}")
        self.status = status
        self.code = code
        self.detail = detail
        self.fields = fields or {}


def parse_error(response: httpx.Response) -> ApiError:
    """Read the backend error envelope {"error": {"status", "detail", "fields"}}; tolerate anything else."""
    try:
        body = response.json().get("error", {})
    except (ValueError, AttributeError):
        body = {}
    fields = body.get("fields") if isinstance(body.get("fields"), dict) else {}
    code = str(fields.get("code") or body.get("code") or ("not_linked" if response.status_code == 404 else "error"))
    detail = str(body.get("detail") or response.reason_phrase or "Request failed")
    return ApiError(response.status_code, code, detail, fields)


class BackendClient:
    def __init__(self, base_url: str, bot_secret: str, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None):
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Bot-Secret": bot_secret},
            timeout=timeout,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, path: str, *, expect: tuple[int, ...] = (200, 201, 202, 204), **kwargs) -> httpx.Response:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(503, "backend_unavailable", exc.__class__.__name__) from exc
        if response.status_code not in expect:
            raise parse_error(response)
        return response

    async def link(self, telegram_id: int, username: str, code: str) -> dict:
        r = await self._call("POST", "/telegram/bot/link/", json={"telegram_id": telegram_id, "username": username, "code": code})
        return r.json()["user"]

    async def me(self, telegram_id: int) -> dict | None:
        """Returns None when the Telegram account is not linked, so callers can show the linking screen."""
        try:
            r = await self._call("GET", "/telegram/bot/me/", params={"telegram_id": telegram_id})
        except ApiError as exc:
            if exc.code == "not_linked":
                return None
            raise
        return r.json()

    async def unlink(self, telegram_id: int) -> None:
        await self._call("POST", "/telegram/bot/unlink/", json={"telegram_id": telegram_id})

    async def projects(self, telegram_id: int) -> list[dict]:
        return (await self._call("GET", "/telegram/bot/projects/", params={"telegram_id": telegram_id})).json()

    async def create_project(self, telegram_id: int, name: str, category: str = "cabinet") -> dict:
        r = await self._call("POST", "/telegram/bot/projects/", json={"telegram_id": telegram_id, "name": name, "category": category})
        return r.json()

    async def rename_project(self, telegram_id: int, project_id: int, name: str) -> dict:
        r = await self._call("PATCH", f"/telegram/bot/projects/{project_id}/", json={"telegram_id": telegram_id, "name": name})
        return r.json()

    async def calculate(self, telegram_id: int, params: dict[str, Any]) -> dict:
        return (await self._call("POST", "/telegram/bot/calculate/", json={"telegram_id": telegram_id, **params})).json()

    async def create_cutting_list(self, telegram_id: int, params: dict[str, Any]) -> dict:
        return (await self._call("POST", "/telegram/bot/cutting-lists/", json={"telegram_id": telegram_id, **params})).json()

    async def export_cutting_list(self, telegram_id: int, list_id: int, kind: str) -> bytes:
        r = await self._call("GET", f"/telegram/bot/cutting-lists/{list_id}/export/{kind}/", params={"telegram_id": telegram_id})
        return r.content

    async def upload_file(self, telegram_id: int, filename: str, content: bytes, project_id: int | None = None) -> dict:
        data = {"telegram_id": str(telegram_id)}
        if project_id is not None:
            data["project_id"] = str(project_id)
        r = await self._call("POST", "/telegram/bot/files/", data=data, files={"file": (filename, content)})
        return r.json()

    async def notifications(self, telegram_id: int) -> list[dict]:
        return (await self._call("GET", "/telegram/bot/notifications/", params={"telegram_id": telegram_id})).json()

    async def orders(self, telegram_id: int, status: str = "") -> list[dict]:
        params = {"telegram_id": telegram_id, **({"status": status} if status else {})}
        return (await self._call("GET", "/telegram/bot/orders/", params=params)).json()

    async def order(self, telegram_id: int, order_id: int) -> dict:
        return (await self._call("GET", f"/telegram/bot/orders/{order_id}/", params={"telegram_id": telegram_id})).json()

    async def set_order_status(self, telegram_id: int, order_id: int, status: str, note: str = "") -> dict:
        body = {"telegram_id": telegram_id, "status": status, **({"note": note} if note else {})}
        return (await self._call("POST", f"/telegram/bot/orders/{order_id}/status/", json=body)).json()

    async def admin_stats(self, telegram_id: int) -> dict:
        return (await self._call("GET", "/telegram/bot/admin/stats/", params={"telegram_id": telegram_id})).json()

    async def admin_system(self, telegram_id: int) -> dict:
        return (await self._call("GET", "/telegram/bot/admin/system/", params={"telegram_id": telegram_id})).json()

    async def admin_broadcast(self, telegram_id: int, text: str) -> None:
        await self._call("POST", "/telegram/bot/admin/broadcast/", json={"telegram_id": telegram_id, "text": text})
