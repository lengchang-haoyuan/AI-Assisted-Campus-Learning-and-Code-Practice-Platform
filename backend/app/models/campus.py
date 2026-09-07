from datetime import datetime
from enum import StrEnum

from sqlalchemy import BINARY, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, MYSQL_TABLE_OPTIONS, TimestampMixin, UTCDateTime
from app.models.enums import enum_type


class CampusRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMINISTRATOR = "administrator"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    CONSUMED = "consumed"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CampusMembership(IdMixin, TimestampMixin, Base):
    __tablename__ = "campus_memberships"
    __table_args__ = (
        Index("ix_campus_memberships_status_role_id", "status", "role", "id"),
        MYSQL_TABLE_OPTIONS,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT"), unique=True
    )
    role: Mapped[CampusRole] = mapped_column(
        enum_type(CampusRole, name="campus_role"), nullable=False
    )
    status: Mapped[MembershipStatus] = mapped_column(
        enum_type(MembershipStatus, name="campus_membership_status"),
        nullable=False,
        default=MembershipStatus.ACTIVE,
        server_default=MembershipStatus.ACTIVE.value,
    )
    verified_by_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    verified_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class CampusInvitation(IdMixin, TimestampMixin, Base):
    __tablename__ = "campus_invitations"
    __table_args__ = (
        CheckConstraint(
            "(target_user_id IS NULL) <> (target_email IS NULL)",
            name="target_identity",
        ),
        CheckConstraint("role IN ('student', 'teacher')", name="invited_role"),
        Index("ix_campus_invitations_status_expires", "status", "expires_at"),
        Index("ix_campus_invitations_issuer_created", "issued_by_user_id", "created_at"),
        MYSQL_TABLE_OPTIONS,
    )

    issued_by_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    target_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    target_email: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[CampusRole] = mapped_column(
        enum_type(CampusRole, name="campus_invitation_role"), nullable=False
    )
    token_digest: Mapped[bytes] = mapped_column(BINARY(32), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[InvitationStatus] = mapped_column(
        enum_type(InvitationStatus, name="campus_invitation_status"),
        nullable=False,
        default=InvitationStatus.PENDING,
        server_default=InvitationStatus.PENDING.value,
    )
    consumed_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class PasswordReset(IdMixin, TimestampMixin, Base):
    __tablename__ = "password_resets"
    __table_args__ = (
        CheckConstraint(
            "consumed_at IS NULL OR revoked_at IS NULL", name="single_terminal_state"
        ),
        Index("ix_password_resets_user_expires", "user_id", "expires_at"),
        MYSQL_TABLE_OPTIONS,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    issued_by_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    token_digest: Mapped[bytes] = mapped_column(BINARY(32), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class AccountAudit(IdMixin, Base):
    __tablename__ = "account_audits"
    __table_args__ = (
        Index("ix_account_audits_actor_occurred", "actor_user_id", "occurred_at"),
        Index("ix_account_audits_target_occurred", "target_user_id", "occurred_at"),
        MYSQL_TABLE_OPTIONS,
    )

    actor_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    target_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
