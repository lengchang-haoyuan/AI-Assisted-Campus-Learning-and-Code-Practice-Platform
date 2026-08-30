from fastapi import APIRouter, status

from app.api.deps import AuthServiceDependency
from app.api.presenters import to_user_response
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


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
    payload: LoginRequest, service: AuthServiceDependency
) -> TokenResponse:
    access_token = service.login(
        identifier=payload.identifier,
        password=payload.password,
    )
    return TokenResponse(
        access_token=access_token.value,
        expires_in=access_token.expires_in,
    )
