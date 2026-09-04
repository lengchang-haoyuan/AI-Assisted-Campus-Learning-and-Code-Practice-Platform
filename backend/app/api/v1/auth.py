from fastapi import APIRouter, Response, status

from app.api.deps import AuthServiceDependency, SliderCaptchaDependency
from app.api.presenters import to_user_response
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    SliderChallengeResponse,
    SliderVerifyRequest,
    SliderVerifyResponse,
    TokenResponse,
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/slider/challenge", summary="获取一次性滑块挑战")
async def slider_challenge(
    response: Response, captcha: SliderCaptchaDependency
) -> SliderChallengeResponse:
    ticket = captcha.create_challenge()
    response.headers["Cache-Control"] = "no-store"
    return SliderChallengeResponse(
        challenge_id=ticket.value, expires_in=ticket.expires_in
    )


@router.post("/slider/verify", summary="校验滑块并签发一次性登录凭证")
async def slider_verify(
    payload: SliderVerifyRequest,
    response: Response,
    captcha: SliderCaptchaDependency,
) -> SliderVerifyResponse:
    ticket = captcha.verify(payload.challenge_id, payload.position)
    response.headers["Cache-Control"] = "no-store"
    return SliderVerifyResponse(slider_token=ticket.value, expires_in=ticket.expires_in)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册用户",
)
async def register(
    payload: RegisterRequest, service: AuthServiceDependency
) -> UserResponse:
    user = service.register(
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    return to_user_response(user)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(
    payload: LoginRequest,
    service: AuthServiceDependency,
    captcha: SliderCaptchaDependency,
) -> TokenResponse:
    captcha.consume(payload.slider_token)
    access_token = service.login(
        identifier=payload.identifier,
        password=payload.password,
    )
    return TokenResponse(
        access_token=access_token.value,
        expires_in=access_token.expires_in,
    )
