from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.api.presenters import to_user_response
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="获取当前用户")
async def get_me(current_user: CurrentUser) -> UserResponse:
    return to_user_response(current_user)
