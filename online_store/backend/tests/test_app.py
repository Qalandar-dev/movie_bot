import httpx
from fastapi import APIRouter

from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.main import create_app


async def test_live(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r.headers["x-content-type-options"] == "nosniff"
    assert len(r.headers["x-request-id"]) == 32


async def test_ready_with_real_dependencies(client: httpx.AsyncClient) -> None:
    """Requires the test PostgreSQL and Redis to be running."""
    r = await client.get("/api/v1/health/ready")
    assert r.json() == {"status": "ok", "database": True, "redis": True}
    assert r.status_code == 200


async def test_valid_request_id_is_propagated(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/health/live", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


async def test_malicious_request_id_is_replaced(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/health/live", headers={"X-Request-ID": "x\r\nSet-Cookie: a"})
    assert r.headers["x-request-id"] != "x\r\nSet-Cookie: a"


async def test_404_uses_error_format(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    body = r.json()["error"]
    assert body["code"] == "not_found"
    assert body["message"] == "Sahifa yoki ma’lumot topilmadi."
    assert "request_id" in body


async def test_app_error_and_unhandled_error_format(settings: Settings) -> None:
    app = create_app(settings)
    router = APIRouter()

    @router.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("Bu SKU allaqachon mavjud.", details={"field": "sku"})

    @router.get("/boom")
    async def boom() -> None:
        raise RuntimeError("password=should-not-leak")

    app.include_router(router)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get("/conflict")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "conflict"
        assert r.json()["error"]["details"] == {"field": "sku"}

        r = await c.get("/boom")
        assert r.status_code == 500
        assert r.json()["error"]["code"] == "internal_error"
        assert "should-not-leak" not in r.text


async def test_cors_only_allows_configured_origins(client: httpx.AsyncClient) -> None:
    preflight = {"Access-Control-Request-Method": "GET"}
    ok = await client.options(
        "/api/v1/health/live", headers={"Origin": "http://localhost:3000", **preflight}
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = await client.options(
        "/api/v1/health/live", headers={"Origin": "https://evil.example", **preflight}
    )
    assert "access-control-allow-origin" not in bad.headers


async def test_openapi_available_outside_production(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/health/live" in r.json()["paths"]
