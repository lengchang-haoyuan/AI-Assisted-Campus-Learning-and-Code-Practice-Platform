from fastapi import APIRouter, Request, Response, status

from app.api.deps import (
    AuthServiceDependency,
    CampusServiceDependency,
    CurrentUser,
    SensitiveActionLimiterDependency,
    SliderCaptchaDependency,
)
from app.api.presenters import to_user_response
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SliderChallengeResponse,
    SliderVerifyRequest,
    SliderVerifyResponse,
    TokenResponse,
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/slider/challenge", summary="获取一次性滑块挑战")
def slider_challenge(
    request: Request,
    response: Response,
    captcha: SliderCaptchaDependency,
    limiter: SensitiveActionLimiterDependency,
) -> SliderChallengeResponse:
    remote = request.client.host if request.client is not None else "unknown"
    limiter.check(f"slider-challenge:{remote}", limit=30, window_seconds=300)
    ticket = captcha.create_challenge()
    response.headers["Cache-Control"] = "no-store"
    return SliderChallengeResponse(
        challenge_id=ticket.value, expires_in=ticket.expires_in
    )


@router.post("/slider/verify", summary="校验滑块并签发一次性登录凭证")
def slider_verify(
    payload: SliderVerifyRequest,
    request: Request,
    response: Response,
    captcha: SliderCaptchaDependency,
    limiter: SensitiveActionLimiterDependency,
) -> SliderVerifyResponse:
    remote = request.client.host if request.client is not None else "unknown"
    limiter.check(f"slider-verify:{remote}", limit=30, window_seconds=300)
    ticket = captcha.verify(payload.challenge_id, payload.position)
    response.headers["Cache-Control"] = "no-store"
    return SliderVerifyResponse(slider_token=ticket.value, expires_in=ticket.expires_in)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册用户",
)
def register(
    payload: RegisterRequest,
    request: Request,
    service: AuthServiceDependency,
    campus_service: CampusServiceDependency,
    limiter: SensitiveActionLimiterDependency,
) -> UserResponse:
    remote = request.client.host if request.client is not None else "unknown"
    limiter.check(f"register:{remote}", limit=8, window_seconds=300)
    if payload.invite_token is not None:
        user = campus_service.register_with_invitation(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            token=payload.invite_token,
        )
    else:
        user = service.register(
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    return to_user_response(user)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
def login(
    payload: LoginRequest,
    request: Request,
    service: AuthServiceDependency,
    captcha: SliderCaptchaDependency,
    limiter: SensitiveActionLimiterDependency,
) -> TokenResponse:
    remote = request.client.host if request.client is not None else "unknown"
    limiter.check(f"login:{remote}", limit=20, window_seconds=300)
    captcha.consume(payload.slider_token)
    access_token = service.login(
        identifier=payload.identifier,
        password=payload.password,
    )
    return TokenResponse(
        access_token=access_token.value,
        expires_in=access_token.expires_in,
    )


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="修改当前账号密码",
)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: CurrentUser,
    service: CampusServiceDependency,
    limiter: SensitiveActionLimiterDependency,
) -> Response:
    remote = request.client.host if request.client is not None else "unknown"
    limiter.check(
        f"change-password:{remote}:{current_user.id}", limit=6, window_seconds=300
    )
    service.change_password(
        current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="撤销当前账号全部会话",
)
def logout_all(
    current_user: CurrentUser, service: CampusServiceDependency
) -> Response:
    service.logout_all(current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="使用一次性凭证重置密码",
)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    service: CampusServiceDependency,
    limiter: SensitiveActionLimiterDependency,
) -> Response:
    remote = request.client.host if request.client is not None else "unknown"
    limiter.check(f"reset-password:{remote}", limit=8, window_seconds=300)
    service.reset_password(token=payload.reset_token, new_password=payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
