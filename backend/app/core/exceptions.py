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


class AIConfigurationError(AppError):
    status_code = 503
    code = "ai_configuration_error"
    default_message = "AI Provider 尚未正确配置"


class AIRateLimitError(AppError):
    status_code = 503
    code = "ai_rate_limited"
    default_message = "AI Provider 当前请求过多，请稍后重试"


class AIUpstreamTimeoutError(AppError):
    status_code = 504
    code = "ai_timeout"
    default_message = "AI Provider 响应超时"


class AIUpstreamError(AppError):
    status_code = 502
    code = "ai_upstream_error"
    default_message = "AI Provider 调用失败"


class AgentOutputError(AppError):
    status_code = 502
    code = "agent_output_invalid"
    default_message = "AI Agent 返回的结构化结果无效"
