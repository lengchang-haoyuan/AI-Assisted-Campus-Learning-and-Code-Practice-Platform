from collections.abc import Awaitable, Callable
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response

REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 64
logger = logging.getLogger("scholarhub.request")


def normalize_request_id(value: str | None) -> str:
    if value and len(value) <= MAX_REQUEST_ID_LENGTH and value.isascii():
        normalized = value.strip()
        if normalized and all(
            character.isalnum() or character in "-_." for character in normalized
        ):
            return normalized
    return uuid4().hex


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id
    started_at = perf_counter()

    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((perf_counter() - started_at) * 1000, 3),
        },
    )
    return response
