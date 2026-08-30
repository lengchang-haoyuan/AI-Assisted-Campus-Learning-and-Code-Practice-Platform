class AppError(Exception):
    status_code = 500
    code = "internal_error"
    default_message = "服务器内部错误"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class InputError(AppError):
    status_code = 400
    code = "input_error"
    default_message = "请求参数无效"


class AuthenticationRequiredError(AppError):
    status_code = 401
    code = "authentication_required"
    default_message = "需要身份认证"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"
    default_message = "没有执行该操作的权限"


class ResourceNotFoundError(AppError):
    status_code = 404
    code = "resource_not_found"
    default_message = "请求的资源不存在"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    default_message = "请求与当前资源状态冲突"
