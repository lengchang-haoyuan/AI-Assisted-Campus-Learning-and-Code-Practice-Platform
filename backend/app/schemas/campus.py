import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.campus import CampusRole, InvitationStatus, MembershipStatus

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MembershipResponse(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    role: CampusRole
    status: MembershipStatus
    revision: int
    verified_at: datetime


class CampusMeResponse(BaseModel):
    membership: MembershipResponse | None


class InvitationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_user_id: int | None = Field(default=None, ge=1)
    target_email: str | None = Field(default=None, min_length=3, max_length=255)
    role: CampusRole
    expires_in_hours: int = Field(default=72, ge=1, le=72)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("target_email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("target_email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and EMAIL_PATTERN.fullmatch(value) is None:
            raise ValueError("邮箱格式无效")
        return value

    @model_validator(mode="after")
    def validate_target(self) -> "InvitationCreateRequest":
        if (self.target_user_id is None) == (self.target_email is None):
            raise ValueError("必须且只能指定目标账号或目标邮箱")
        return self


class InvitationResponse(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    target_user_id: int | None
    target_email: str | None
    role: CampusRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


class InvitationIssuedResponse(InvitationResponse):
    token: str


class InvitationRedeemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=128)


class ReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class AccountResponse(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    user_id: int
    username: str
    email: str
    account_enabled: bool
    auth_version: int
    membership: MembershipResponse | None


class AccountUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)
    expected_revision: int | None = Field(default=None, ge=1)
    expected_auth_version: int | None = Field(default=None, ge=0)
    role: CampusRole | None = None
    campus_status: MembershipStatus | None = None
    account_enabled: bool | None = None

    @model_validator(mode="after")
    def validate_operation(self) -> "AccountUpdateRequest":
        operations = sum(
            value is not None
            for value in (self.role, self.campus_status, self.account_enabled)
        )
        if operations != 1:
            raise ValueError("每次只能修改一项账号设置")
        if self.account_enabled is not None and self.expected_auth_version is None:
            raise ValueError("启停账号必须提供 expected_auth_version")
        if self.account_enabled is None and self.expected_revision is None:
            raise ValueError("身份变更必须提供 expected_revision")
        return self


class PasswordResetIssuedResponse(BaseModel):
    token: str
    expires_at: datetime


class AuditResponse(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    actor_user_id: int
    target_user_id: int | None
    action: str
    outcome: str
    reason: str | None
    occurred_at: datetime


class AccountPageResponse(BaseModel):
    items: list[AccountResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class InvitationPageResponse(BaseModel):
    items: list[InvitationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditPageResponse(BaseModel):
    items: list[AuditResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
