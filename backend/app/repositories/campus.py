from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models.campus import (
    AccountAudit,
    CampusInvitation,
    CampusMembership,
    CampusRole,
    MembershipStatus,
    PasswordReset,
)
from app.models.user import User


class CampusRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """串行化 P17 权限变更，保护首次和最后管理员不变量。"""
        self._session.rollback()
        lock_name = "scholarhub:campus-identity"
        uses_mysql = self._session.get_bind().dialect.name == "mysql"
        original_bind = self._session.bind
        connection = self._session.get_bind().connect() if uses_mysql else None
        if connection is not None:
            # 外部持有连接，避免 Session.commit 后连接回池，命名锁无法原连接释放。
            self._session.bind = connection
        acquired = False
        try:
            if uses_mysql:
                acquired = (
                    self._session.execute(
                        text("SELECT GET_LOCK(:lock_name, 5)"),
                        {"lock_name": lock_name},
                    ).scalar_one()
                    == 1
                )
                if not acquired:
                    raise ConflictError("校园身份正在变更，请稍后重试")
            yield
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("请求与现有账号或凭证冲突") from exc
        except BaseException:
            self._session.rollback()
            raise
        finally:
            if connection is not None:
                try:
                    if acquired:
                        connection.execute(
                            text("SELECT RELEASE_LOCK(:lock_name)"),
                            {"lock_name": lock_name},
                        )
                except BaseException:
                    # 释放失败时丢弃物理连接，防止仍持锁的连接被连接池复用。
                    connection.invalidate()
                    raise
                finally:
                    self._session.rollback()
                    self._session.bind = original_bind
                    connection.close()

    def add(self, value: object) -> None:
        self._session.add(value)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()

    def user(self, user_id: int) -> User | None:
        return self._session.execute(
            select(User).where(User.id == user_id).execution_options(populate_existing=True)
        ).scalar_one_or_none()

    def user_by_username(self, username: str) -> User | None:
        return self._session.scalar(select(User).where(User.username == username))

    def user_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))

    def membership(self, user_id: int) -> CampusMembership | None:
        return self._session.execute(
            select(CampusMembership)
            .where(CampusMembership.user_id == user_id)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    def invitation(self, digest: bytes) -> CampusInvitation | None:
        return self._session.execute(
            select(CampusInvitation)
            .where(CampusInvitation.token_digest == digest)
            .with_for_update()
        ).scalar_one_or_none()

    def invitation_by_id(self, invitation_id: int) -> CampusInvitation | None:
        return self._session.execute(
            select(CampusInvitation)
            .where(CampusInvitation.id == invitation_id)
            .with_for_update()
        ).scalar_one_or_none()

    def password_reset(self, digest: bytes) -> PasswordReset | None:
        return self._session.execute(
            select(PasswordReset)
            .where(PasswordReset.token_digest == digest)
            .with_for_update()
        ).scalar_one_or_none()

    def revoke_pending_resets(self, user_id: int, now: datetime) -> None:
        resets = self._session.execute(
            select(PasswordReset).where(
                PasswordReset.user_id == user_id,
                PasswordReset.consumed_at.is_(None),
                PasswordReset.revoked_at.is_(None),
            )
        ).scalars()
        for reset in resets:
            reset.revoked_at = now

    def active_administrators(self) -> list[CampusMembership]:
        return list(
            self._session.execute(
                select(CampusMembership)
                .join(User, User.id == CampusMembership.user_id)
                .where(
                    CampusMembership.role == CampusRole.ADMINISTRATOR,
                    CampusMembership.status == MembershipStatus.ACTIVE,
                    User.is_active.is_(True),
                )
                .order_by(CampusMembership.id)
                .with_for_update()
            ).scalars()
        )

    def account_page(
        self, *, query: str | None, page: int, page_size: int
    ) -> tuple[list[tuple[User, CampusMembership | None]], int]:
        condition = None
        if query:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            condition = or_(
                User.username.like(pattern, escape="\\"),
                User.email.like(pattern, escape="\\"),
            )
        count_statement = select(func.count(User.id))
        statement = select(User, CampusMembership).outerjoin(
            CampusMembership, CampusMembership.user_id == User.id
        )
        if condition is not None:
            count_statement = count_statement.where(condition)
            statement = statement.where(condition)
        total = int(self._session.execute(count_statement).scalar_one())
        rows = self._session.execute(
            statement.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [(row[0], row[1]) for row in rows], total

    def invitation_page(
        self, *, page: int, page_size: int
    ) -> tuple[list[CampusInvitation], int]:
        total = int(
            self._session.execute(select(func.count(CampusInvitation.id))).scalar_one()
        )
        values = list(
            self._session.execute(
                select(CampusInvitation)
                .order_by(CampusInvitation.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars()
        )
        return values, total

    def audit_page(
        self, *, page: int, page_size: int
    ) -> tuple[list[AccountAudit], int]:
        total = int(self._session.execute(select(func.count(AccountAudit.id))).scalar_one())
        values = list(
            self._session.execute(
                select(AccountAudit)
                .order_by(AccountAudit.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars()
        )
        return values, total
