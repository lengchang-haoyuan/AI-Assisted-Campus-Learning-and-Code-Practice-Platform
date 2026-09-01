from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ProjectDifficulty, ProjectStatus


class TagResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    slug: str


class TagSummaryResponse(TagResponse):
    project_count: int


class CommunityOwnerResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    username: str
    avatar_url: str | None


class CommunityProjectResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    description: str | None
    difficulty: ProjectDifficulty
    status: ProjectStatus
    language: str | None
    framework: str | None
    frontend: str | None
    backend: str | None
    database: str | None
    owner: CommunityOwnerResponse
    tags: list[TagResponse]
    published_at: datetime
    updated_at: datetime
    view_count: int
    comment_count: int
    like_count: int
    favorite_count: int
    liked: bool
    favorited: bool


class CommunityProjectListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[CommunityProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=2_000)

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CommentAuthorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    username: str
    avatar_url: str | None


class CommentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    project_id: int
    author: CommentAuthorResponse
    content: str
    created_at: datetime
    updated_at: datetime
    can_delete: bool


class CommentListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[CommentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class InteractionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    active: bool
    count: int


class ViewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    view_count: int


class PublishProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tags: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_tag in value:
            tag = raw_tag.strip()
            if not tag or len(tag) > 50:
                raise ValueError("标签长度必须为 1 到 50 个字符")
            key = tag.casefold()
            if key not in seen:
                normalized.append(tag)
                seen.add(key)
        return normalized
