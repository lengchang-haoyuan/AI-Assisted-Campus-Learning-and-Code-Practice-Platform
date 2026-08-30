import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.middleware import normalize_request_id
from app.core.exceptions import AppError
from app.schemas.error import ErrorDetail, ErrorResponse

logger = logging.getLogger("scholarhub.error")
HTTP_ERROR_MAP = {
    401: ("authentication_required", "需要身份认证"),
    403: ("permission_denied", "没有执行该操作的权限"),
    404: ("resource_not_found", "请求的资源不存在"),
    409: ("conflict", "请求与当前资源状态冲突"),
}


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else normalize_request_id(None)


def build_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = get_request_id(request)
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    response_headers = {"X-Request-ID": request_id, **(headers or {})}
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=response_headers,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return build_error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        headers=headers,
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del exc
    return build_error_response(
        request,
        status_code=422,
        code="validation_error",
        message="请求参数校验失败",
    )


async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code, message = HTTP_ERROR_MAP.get(
        exc.status_code, ("http_error", "请求处理失败")
    )
    headers = dict(exc.headers or {})
    if exc.status_code == 401:
        headers.setdefault("WWW-Authenticate", "Bearer")
    return build_error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        headers=headers,
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    logger.error(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "error_code": "internal_error",
            "error_type": type(exc).__name__,
        },
    )
    return build_error_response(
        request,
        status_code=500,
        code="internal_error",
        message="服务器内部错误",
    )


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_error_handler)
    application.add_exception_handler(Exception, internal_error_handler)
