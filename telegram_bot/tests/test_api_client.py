import json

import httpx
import pytest

from bot.services.api import ApiError, BackendClient

SECRET = "bot-secret-123"


def client_with(handler) -> BackendClient:
    return BackendClient("http://api.test/api/v1", SECRET, transport=httpx.MockTransport(handler))


async def test_every_request_carries_the_bot_secret():
    seen = {}

    def handler(request):
        seen["secret"] = request.headers.get("X-Bot-Secret")
        return httpx.Response(200, json={"linked": True, "user": {}, "unread_notifications": 0})

    api = client_with(handler)
    await api.me(7)
    assert seen["secret"] == SECRET


async def test_me_returns_none_when_not_linked():
    def handler(request):
        return httpx.Response(404, json={"error": {"status": 404, "detail": "Request failed.",
                                                   "fields": {"detail": "not linked", "code": "not_linked"}}})

    assert await client_with(handler).me(7) is None


async def test_link_errors_expose_the_machine_code():
    def handler(request):
        return httpx.Response(400, json={"error": {"status": 400, "detail": "Request failed.",
                                                   "fields": {"detail": "expired", "code": "expired"}}})

    with pytest.raises(ApiError) as e:
        await client_with(handler).link(7, "u", "ABCD-EFGH")
    assert e.value.code == "expired"
    assert e.value.status == 400


async def test_unknown_error_shape_is_tolerated():
    def handler(request):
        return httpx.Response(500, text="<html>boom</html>")

    with pytest.raises(ApiError) as e:
        await client_with(handler).projects(7)
    assert e.value.status == 500
    assert e.value.code == "error"


async def test_transport_failure_becomes_backend_unavailable():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ApiError) as e:
        await client_with(handler).projects(7)
    assert e.value.code == "backend_unavailable"


async def test_link_sends_telegram_id_and_code_and_returns_user():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"linked": True, "user": {"email": "m@x.com"}})

    user = await client_with(handler).link(555, "maker", "ABCD-EFGH")
    assert user["email"] == "m@x.com"
    assert captured["body"] == {"telegram_id": 555, "username": "maker", "code": "ABCD-EFGH"}


async def test_export_returns_raw_bytes():
    def handler(request):
        assert request.url.path.endswith("/cutting-lists/9/export/pdf/")
        return httpx.Response(200, content=b"%PDF-1.4 data", headers={"Content-Type": "application/pdf"})

    assert await client_with(handler).export_cutting_list(7, 9, "pdf") == b"%PDF-1.4 data"


async def test_upload_is_multipart_with_telegram_id():
    def handler(request):
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert b'name="telegram_id"' in request.content
        assert b'filename="plan.pdf"' in request.content
        return httpx.Response(201, json={"id": 1, "name": "plan.pdf", "kind": "pdf", "size_bytes": 9, "storage_percent": 0.1})

    saved = await client_with(handler).upload_file(7, "plan.pdf", b"%PDF-1.4 x")
    assert saved["name"] == "plan.pdf"
