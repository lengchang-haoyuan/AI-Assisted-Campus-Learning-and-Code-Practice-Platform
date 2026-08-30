from app.schemas.user import UserResponse
from app.services.auth import UserIdentity


def to_user_response(user: UserIdentity) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        bio=user.bio,
        is_active=user.is_active,
        created_at=user.created_at,
    )
