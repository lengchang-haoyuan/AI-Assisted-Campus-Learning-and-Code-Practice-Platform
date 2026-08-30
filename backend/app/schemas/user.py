from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    username: str
    email: str
    avatar_url: str | None
    bio: str | None
    is_active: bool
    created_at: datetime
