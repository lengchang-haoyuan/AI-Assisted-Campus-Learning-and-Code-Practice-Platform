import asyncio
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from secrets import token_urlsafe
import unittest
from urllib.parse import urlsplit
from unittest.mock import Mock, patch

from fastapi import FastAPI

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_db_session
from app.core.exceptions import (
    AuthenticationRequiredError,
    ConflictError,
    InputError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.core.logging import JsonFormatter
from app.main import create_app

APP_DIR = Path(__file__).resolve().parents[1] / "app"


@dataclass(frozen=True)
class ASGIResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> dict[str, object]:
        return json.loads(self.body)


async def invoke_asgi(
    application: FastAPI,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | None = None,
) -> ASGIResponse:
    messages: list[dict[str, object]] = []
    request_sent = False
    request_body = json.dumps(body).encode("utf-8") if body is not None else b""
    parsed_url = urlsplit(path)

    async def receive() -> dict[str, object]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {
                "type": "http.request",
                "body": request_body,
                "more_body": False,
            }
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    request_headers = dict(headers or {})
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json")
    encoded_headers = [
        (name.lower().encode("ascii"), value.encode("ascii"))
        for name, value in request_headers.items()
    ]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": parsed_url.path,
        "raw_path": parsed_url.path.encode("ascii"),
        "query_string": parsed_url.query.encode("ascii"),
        "root_path": "",
        "headers": encoded_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
        "state": {},
    }
    try:
        await application(scope, receive, send)
    except Exception:
        if not any(message["type"] == "http.response.start" for message in messages):
            raise

    start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    response_headers = {
        name.decode("latin-1").lower(): value.decode("latin-1")
        for name, value in start["headers"]
    }
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return ASGIResponse(
        status_code=start["status"],
        headers=response_headers,
        body=response_body,
    )


def request(
    application: FastAPI,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | None = None,
) -> ASGIResponse:
    return asyncio.run(
        invoke_asgi(application, method, path, headers=headers, body=body)
    )


class APIFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()

    def test_health_and_swagger_remain_available(self) -> None:
        health = request(
            self.app,
            "GET",
            "/api/v1/health",
            headers={"X-Request-ID": "test-request-1"},
        )
        self.assertEqual(health.status_code, 200)
        self.assertEqual(
            health.json(),
            {"status": "ok", "service": "ScholarHub API", "version": "0.1.0"},
        )
        self.assertEqual(health.headers["x-request-id"], "test-request-1")

        docs = request(self.app, "GET", "/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn(b"Swagger UI", docs.body)

    def test_app_errors_have_stable_status_and_shape(self) -> None:
        errors = {
            "input": (InputError, 400, "input_error"),
            "authentication": (
                AuthenticationRequiredError,
                401,
                "authentication_required",
            ),
            "permission": (PermissionDeniedError, 403, "permission_denied"),
            "missing": (ResourceNotFoundError, 404, "resource_not_found"),
            "conflict": (ConflictError, 409, "conflict"),
        }

        def error_route(error_type: type[Exception]):
            async def raise_error() -> None:
                raise error_type()

            return raise_error

        for route_name, (error_type, expected_status, expected_code) in errors.items():
            self.app.add_api_route(
                f"/test/{route_name}", error_route(error_type), methods=["GET"]
            )
            response = request(self.app, "GET", f"/test/{route_name}")
            with self.subTest(route=route_name):
                body = response.json()["error"]
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(body["code"], expected_code)
                self.assertEqual(body["request_id"], response.headers["x-request-id"])
                if expected_status == 401:
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")

        unknown = request(self.app, "GET", "/unknown-route")
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(unknown.json()["error"]["code"], "resource_not_found")

    def test_validation_and_internal_errors_do_not_leak_details(self) -> None:
        async def validated_route(limit: int) -> dict[str, int]:
            return {"limit": limit}

        async def failing_route() -> None:
            raise RuntimeError("SELECT secret FROM private_path")

        self.app.add_api_route("/test/validation", validated_route, methods=["GET"])
        self.app.add_api_route("/test/internal", failing_route, methods=["GET"])

        validation = request(self.app, "GET", "/test/validation")
        self.assertEqual(validation.status_code, 422)
        self.assertEqual(validation.json()["error"]["code"], "validation_error")

        with self.assertLogs("scholarhub.error", level="ERROR"):
            internal = request(self.app, "GET", "/test/internal")
        self.assertEqual(internal.status_code, 500)
        self.assertEqual(internal.json()["error"]["code"], "internal_error")
        self.assertNotIn(b"SELECT", internal.body)
        self.assertNotIn(b"private_path", internal.body)

    def test_cors_allows_configured_origin_only(self) -> None:
        allowed = request(
            self.app,
            "OPTIONS",
            "/api/v1/health",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(
            allowed.headers["access-control-allow-origin"],
            "http://127.0.0.1:5173",
        )
        self.assertIn("POST", allowed.headers["access-control-allow-methods"])
        self.assertIn("PUT", allowed.headers["access-control-allow-methods"])
        self.assertIn("DELETE", allowed.headers["access-control-allow-methods"])
        self.assertIn(
            "Authorization", allowed.headers["access-control-allow-headers"]
        )

        simple = request(
            self.app,
            "GET",
            "/api/v1/health",
            headers={"Origin": "http://127.0.0.1:5173"},
        )
        self.assertEqual(simple.headers["access-control-expose-headers"], "X-Request-ID")

        denied = request(
            self.app,
            "OPTIONS",
            "/api/v1/health",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertNotIn("access-control-allow-origin", denied.headers)

    def test_database_session_dependency_closes_session(self) -> None:
        session = Mock()
        session_factory = Mock(return_value=session)
        with patch(
            "app.api.deps.get_session_factory", return_value=session_factory
        ):
            dependency = get_db_session()
            self.assertIs(next(dependency), session)
            dependency.close()
        session.close.assert_called_once_with()

    def test_logs_are_json_and_include_request_context(self) -> None:
        record = logging.LogRecord(
            name="scholarhub.request",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="request_completed",
            args=(),
            exc_info=None,
        )
        record.request_id = "request-123"
        record.status_code = 200
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["message"], "request_completed")
        self.assertEqual(payload["request_id"], "request-123")
        self.assertEqual(payload["status_code"], 200)

    def test_routers_do_not_import_orm_or_sqlalchemy(self) -> None:
        router_sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (APP_DIR / "api" / "v1").glob("*.py")
        )
        self.assertNotIn("app.models", router_sources)
        self.assertNotIn("sqlalchemy", router_sources)


if __name__ == "__main__":
    unittest.main()
