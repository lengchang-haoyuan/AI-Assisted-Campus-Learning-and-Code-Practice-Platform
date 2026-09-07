from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import ceil
from secrets import token_urlsafe
from typing import TypeVar

from app.core.exceptions import (
    AppError,
    AuthenticationRequiredError,
    ConflictError,
    InputError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.core.security import SecurityService
from app.models.campus import (
    AccountAudit,
    CampusInvitation,
    CampusMembership,
    CampusRole,
    InvitationStatus,
    MembershipStatus,
    PasswordReset,
)
from app.models.user import User
from app.repositories.campus import CampusRepository
from app.services.auth import UserIdentity

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class MembershipData:
    id: int
    role: CampusRole
    status: MembershipStatus
    revision: int
    verified_at: datetime


@dataclass(frozen=True, slots=True)
class AccountData:
    user_id: int
    username: str
    email: str
    account_enabled: bool
    auth_version: int
    membership: MembershipData | None


@dataclass(frozen=True, slots=True)
class InvitationData:
    id: int
    target_user_id: int | None
    target_email: str | None
    role: CampusRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuditData:
    id: int
    actor_user_id: int
    target_user_id: int | None
    action: str
    outcome: str
    reason: str | None
    occurred_at: datetime


class CampusService:
    def __init__(
        self, repository: CampusRepository, security: SecurityService
    ) -> None:
        self._repository = repository
        self._security = security

    @staticmethod
    def _digest(token: str) -> bytes:
        return sha256(token.encode("utf-8")).digest()

    @staticmethod
    def _membership_data(value: CampusMembership | None) -> MembershipData | None:
        if value is None:
            return None
        return MembershipData(
            id=value.id,
            role=value.role,
            status=value.status,
            revision=value.revision,
            verified_at=value.verified_at,
        )

    @classmethod
    def _required_membership_data(cls, value: CampusMembership) -> MembershipData:
        result = cls._membership_data(value)
        if result is None:
            raise RuntimeError("校园身份映射失败")
        return result

    @classmethod
    def _account_data(
        cls, user: User, membership: CampusMembership | None
    ) -> AccountData:
        return AccountData(
            user_id=user.id,
            username=user.username,
            email=user.email,
            account_enabled=user.is_active,
            auth_version=user.auth_version or 0,
            membership=cls._membership_data(membership),
        )

    def _fresh_actor(self, actor: UserIdentity, *, admin: bool = False) -> User:
        user = self._repository.user(actor.id)
        if user is None or not user.is_active:
            raise AuthenticationRequiredError("登录状态无效或已过期")
        if (user.auth_version or 0) != actor.auth_version:
            raise AuthenticationRequiredError("会话已撤销，请重新登录")
        if admin:
            membership = self._repository.membership(user.id)
            if (
                membership is None
                or membership.status != MembershipStatus.ACTIVE
                or membership.role != CampusRole.ADMINISTRATOR
            ):
                raise PermissionDeniedError("需要有效的校园管理员身份")
        return user

    def _audit(
        self,
        *,
        actor_user_id: int,
        target_user_id: int | None,
        action: str,
        outcome: str,
        reason: str | None,
    ) -> None:
        self._repository.add(
            AccountAudit(
                actor_user_id=actor_user_id,
                target_user_id=target_user_id,
                action=action,
                outcome=outcome,
                reason=reason,
                occurred_at=datetime.now(UTC),
            )
        )

    def _mutate(
        self,
        *,
        actor: UserIdentity,
        action: str,
        target_user_id: int | None,
        reason: str | None,
        admin: bool,
        work: Callable[[User], T],
    ) -> T:
        try:
            with self._repository.transaction():
                actor_user = self._fresh_actor(actor, admin=admin)
                result = work(actor_user)
                self._audit(
                    actor_user_id=actor_user.id,
                    target_user_id=target_user_id,
                    action=action,
                    outcome="success",
                    reason=reason,
                )
                return result
        except AppError as exc:
            try:
                with self._repository.transaction():
                    if self._repository.user(actor.id) is not None:
                        self._audit(
                            actor_user_id=actor.id,
                            target_user_id=(
                                target_user_id
                                if target_user_id is not None
                                and self._repository.user(target_user_id) is not None
                                else None
                            ),
                            action=action,
                            outcome="rejected",
                            reason=exc.code,
                        )
            except AppError:
                pass
            raise

    def me(self, actor: UserIdentity) -> MembershipData | None:
        self._fresh_actor(actor)
        return self._membership_data(self._repository.membership(actor.id))

    def register_with_invitation(
        self, *, username: str, email: str, password: str, token: str
    ) -> UserIdentity:
        now = datetime.now(UTC)
        with self._repository.transaction():
            if (
                self._repository.user_by_username(username) is not None
                or self._repository.user_by_email(email) is not None
            ):
                raise ConflictError("用户名或邮箱已被使用")
            invitation = self._repository.invitation(self._digest(token))
            if (
                invitation is None
                or invitation.status != InvitationStatus.PENDING
                or invitation.expires_at <= now
            ):
                raise ConflictError("邀请凭证无效或已失效")
            if invitation.target_user_id is not None or invitation.target_email != email:
                raise PermissionDeniedError("邀请凭证不属于当前注册邮箱")
            issuer = self._repository.user(invitation.issued_by_user_id)
            issuer_membership = self._repository.membership(invitation.issued_by_user_id)
            if (
                issuer is None
                or not issuer.is_active
                or issuer_membership is None
                or issuer_membership.role != CampusRole.ADMINISTRATOR
                or issuer_membership.status != MembershipStatus.ACTIVE
            ):
                raise ConflictError("邀请签发人已不具备核验资格")
            user = User(
                username=username,
                email=email,
                password_hash=self._security.hash_password(password),
                auth_version=0,
            )
            self._repository.add(user)
            membership = CampusMembership(
                user_id=user.id,
                role=invitation.role,
                status=MembershipStatus.ACTIVE,
                verified_by_user_id=issuer.id,
                verified_at=now,
                revision=1,
            )
            self._repository.add(membership)
            invitation.status = InvitationStatus.CONSUMED
            invitation.consumed_by_user_id = user.id
            invitation.consumed_at = now
            self._audit(
                actor_user_id=user.id,
                target_user_id=user.id,
                action="register_with_invitation",
                outcome="success",
                reason=None,
            )
            return UserIdentity(
                id=user.id,
                username=user.username,
                email=user.email,
                avatar_url=user.avatar_url,
                bio=user.bio,
                is_active=user.is_active,
                created_at=user.created_at,
                auth_version=user.auth_version,
            )

    def accounts(
        self, actor: UserIdentity, *, query: str | None, page: int, page_size: int
    ) -> tuple[list[AccountData], int, int]:
        self._fresh_actor(actor, admin=True)
        rows, total = self._repository.account_page(
            query=query, page=page, page_size=page_size
        )
        return [self._account_data(user, membership) for user, membership in rows], total, ceil(total / page_size)

    def invitations(
        self, actor: UserIdentity, *, page: int, page_size: int
    ) -> tuple[list[InvitationData], int, int]:
        self._fresh_actor(actor, admin=True)
        values, total = self._repository.invitation_page(page=page, page_size=page_size)
        now = datetime.now(UTC)
        items = [
            InvitationData(
                id=value.id,
                target_user_id=value.target_user_id,
                target_email=value.target_email,
                role=value.role,
                status=(
                    InvitationStatus.EXPIRED
                    if value.status == InvitationStatus.PENDING and value.expires_at <= now
                    else value.status
                ),
                expires_at=value.expires_at,
                created_at=value.created_at,
            )
            for value in values
        ]
        return items, total, ceil(total / page_size)

    def audits(
        self, actor: UserIdentity, *, page: int, page_size: int
    ) -> tuple[list[AuditData], int, int]:
        self._fresh_actor(actor, admin=True)
        values, total = self._repository.audit_page(page=page, page_size=page_size)
        return [AuditData(value.id, value.actor_user_id, value.target_user_id, value.action, value.outcome, value.reason, value.occurred_at) for value in values], total, ceil(total / page_size)

    def issue_invitation(
        self,
        actor: UserIdentity,
        *,
        target_user_id: int | None,
        target_email: str | None,
        role: CampusRole,
        expires_in_hours: int,
        reason: str,
    ) -> tuple[InvitationData, str]:
        if (target_user_id is None) == (target_email is None):
            raise InputError("必须且只能指定目标账号或目标邮箱")
        if not 1 <= expires_in_hours <= 72:
            raise InputError("邀请有效期必须在 1 到 72 小时之间")
        if role == CampusRole.ADMINISTRATOR:
            raise InputError("管理员身份不能通过邀请授予")
        token = token_urlsafe(32)
        now = datetime.now(UTC)

        def work(admin_user: User) -> tuple[InvitationData, str]:
            if target_user_id is not None:
                target = self._repository.user(target_user_id)
                if target is None or not target.is_active:
                    raise ResourceNotFoundError("目标账号不存在或不可用")
            invitation = CampusInvitation(
                issued_by_user_id=admin_user.id,
                target_user_id=target_user_id,
                target_email=target_email,
                role=role,
                token_digest=self._digest(token),
                expires_at=now + timedelta(hours=expires_in_hours),
                status=InvitationStatus.PENDING,
            )
            self._repository.add(invitation)
            return InvitationData(invitation.id, invitation.target_user_id, invitation.target_email, invitation.role, invitation.status, invitation.expires_at, invitation.created_at), token

        return self._mutate(actor=actor, action="issue_invitation", target_user_id=target_user_id, reason=reason, admin=True, work=work)

    def redeem_invitation(self, actor: UserIdentity, *, token: str) -> MembershipData:
        now = datetime.now(UTC)

        def work(user: User) -> MembershipData:
            invitation = self._repository.invitation(self._digest(token))
            if invitation is None:
                raise ResourceNotFoundError("邀请凭证无效")
            if invitation.status == InvitationStatus.CONSUMED:
                if invitation.consumed_by_user_id == user.id:
                    membership = self._repository.membership(user.id)
                    if membership is not None:
                        return self._required_membership_data(membership)
                raise ConflictError("邀请凭证已使用")
            if invitation.status != InvitationStatus.PENDING or invitation.expires_at <= now:
                raise ConflictError("邀请凭证已失效")
            if invitation.target_user_id is not None and invitation.target_user_id != user.id:
                raise PermissionDeniedError("邀请凭证不属于当前账号")
            if invitation.target_email is not None and invitation.target_email != user.email.lower():
                raise PermissionDeniedError("邀请凭证不属于当前邮箱")
            issuer = self._repository.user(invitation.issued_by_user_id)
            issuer_membership = self._repository.membership(invitation.issued_by_user_id)
            if issuer is None or not issuer.is_active or issuer_membership is None or issuer_membership.role != CampusRole.ADMINISTRATOR or issuer_membership.status != MembershipStatus.ACTIVE:
                raise ConflictError("邀请签发人已不具备核验资格")
            membership = self._repository.membership(user.id)
            if membership is not None:
                if membership.role != invitation.role or membership.status != MembershipStatus.ACTIVE:
                    raise ConflictError("当前校园身份与邀请不一致")
            else:
                membership = CampusMembership(user_id=user.id, role=invitation.role, status=MembershipStatus.ACTIVE, verified_by_user_id=issuer.id, verified_at=now, revision=1)
                self._repository.add(membership)
                user.auth_version = (user.auth_version or 0) + 1
            invitation.status = InvitationStatus.CONSUMED
            invitation.consumed_by_user_id = user.id
            invitation.consumed_at = now
            self._repository.flush()
            return self._required_membership_data(membership)

        return self._mutate(actor=actor, action="redeem_invitation", target_user_id=actor.id, reason=None, admin=False, work=work)

    def revoke_invitation(self, actor: UserIdentity, *, invitation_id: int, reason: str) -> None:
        def work(_: User) -> None:
            invitation = self._repository.invitation_by_id(invitation_id)
            if invitation is None:
                raise ResourceNotFoundError("邀请不存在")
            if invitation.status == InvitationStatus.CONSUMED:
                raise ConflictError("已使用的邀请不能撤销")
            invitation.status = InvitationStatus.REVOKED

        self._mutate(actor=actor, action="revoke_invitation", target_user_id=None, reason=reason, admin=True, work=work)

    def update_account(
        self,
        actor: UserIdentity,
        *,
        user_id: int,
        reason: str,
        expected_revision: int | None,
        expected_auth_version: int | None,
        role: CampusRole | None,
        campus_status: MembershipStatus | None,
        account_enabled: bool | None,
    ) -> AccountData:
        operations = sum(value is not None for value in (role, campus_status, account_enabled))
        if operations != 1:
            raise InputError("每次只能修改角色、校园状态或账号状态中的一项")

        def work(_: User) -> AccountData:
            target = self._repository.user(user_id)
            if target is None:
                raise ResourceNotFoundError("账号不存在")
            membership = self._repository.membership(user_id)
            if account_enabled is not None:
                if expected_auth_version != (target.auth_version or 0):
                    raise ConflictError("账号已被其他操作更新")
                target.is_active = account_enabled
            else:
                if membership is None:
                    raise ConflictError("账号尚无校园身份")
                if expected_revision != membership.revision:
                    raise ConflictError("校园身份已被其他操作更新")
                if membership.status == MembershipStatus.REVOKED:
                    raise ConflictError("已撤销身份需通过新的核验流程恢复")
                if role is not None:
                    membership.role = role
                if campus_status is not None:
                    membership.status = campus_status
                membership.revision += 1
                membership.verified_by_user_id = actor.id
                membership.verified_at = datetime.now(UTC)
            target.auth_version = (target.auth_version or 0) + 1
            self._repository.revoke_pending_resets(user_id, datetime.now(UTC))
            self._repository.flush()
            if not self._repository.active_administrators():
                raise ConflictError("必须保留至少一名有效管理员")
            return self._account_data(target, membership)

        return self._mutate(actor=actor, action="update_account", target_user_id=user_id, reason=reason, admin=True, work=work)

    def change_password(self, actor: UserIdentity, *, current_password: str, new_password: str) -> None:
        def work(user: User) -> None:
            if not self._security.verify_password(current_password, user.password_hash):
                raise InputError("当前密码不正确")
            user.password_hash = self._security.hash_password(new_password)
            user.auth_version = (user.auth_version or 0) + 1
            self._repository.revoke_pending_resets(user.id, datetime.now(UTC))

        self._mutate(actor=actor, action="change_password", target_user_id=actor.id, reason=None, admin=False, work=work)

    def logout_all(self, actor: UserIdentity) -> None:
        def work(user: User) -> None:
            user.auth_version = (user.auth_version or 0) + 1

        self._mutate(actor=actor, action="logout_all", target_user_id=actor.id, reason=None, admin=False, work=work)

    def issue_password_reset(self, actor: UserIdentity, *, user_id: int, reason: str) -> tuple[str, datetime]:
        token = token_urlsafe(32)
        now = datetime.now(UTC)

        def work(admin_user: User) -> tuple[str, datetime]:
            target = self._repository.user(user_id)
            if target is None or not target.is_active:
                raise ResourceNotFoundError("目标账号不存在或不可用")
            self._repository.revoke_pending_resets(user_id, now)
            reset = PasswordReset(user_id=user_id, issued_by_user_id=admin_user.id, token_digest=self._digest(token), expires_at=now + timedelta(minutes=30))
            self._repository.add(reset)
            return token, reset.expires_at

        return self._mutate(actor=actor, action="issue_password_reset", target_user_id=user_id, reason=reason, admin=True, work=work)

    def reset_password(self, *, token: str, new_password: str) -> None:
        now = datetime.now(UTC)
        with self._repository.transaction():
            reset = self._repository.password_reset(self._digest(token))
            if reset is None or reset.consumed_at is not None or reset.revoked_at is not None or reset.expires_at <= now:
                raise ConflictError("重置凭证无效或已失效")
            issuer = self._repository.user(reset.issued_by_user_id)
            issuer_membership = self._repository.membership(reset.issued_by_user_id)
            if issuer is None or not issuer.is_active or issuer_membership is None or issuer_membership.role != CampusRole.ADMINISTRATOR or issuer_membership.status != MembershipStatus.ACTIVE:
                raise ConflictError("重置凭证签发人已不具备核验资格")
            target = self._repository.user(reset.user_id)
            if target is None or not target.is_active:
                raise ConflictError("目标账号当前不可用")
            target.password_hash = self._security.hash_password(new_password)
            target.auth_version = (target.auth_version or 0) + 1
            reset.consumed_at = now
            self._audit(actor_user_id=target.id, target_user_id=target.id, action="reset_password", outcome="success", reason=None)

    def initialize_first_admin(self, *, user_id: int, reason: str) -> MembershipData:
        now = datetime.now(UTC)
        with self._repository.transaction():
            if self._repository.active_administrators():
                raise ConflictError("首个管理员已经初始化")
            user = self._repository.user(user_id)
            if user is None or not user.is_active:
                raise ResourceNotFoundError("指定账号不存在或不可用")
            if self._repository.membership(user_id) is not None:
                raise ConflictError("指定账号已经具有校园身份")
            membership = CampusMembership(user_id=user_id, role=CampusRole.ADMINISTRATOR, status=MembershipStatus.ACTIVE, verified_by_user_id=user_id, verified_at=now, revision=1)
            self._repository.add(membership)
            user.auth_version = (user.auth_version or 0) + 1
            self._audit(actor_user_id=user_id, target_user_id=user_id, action="initialize_first_admin", outcome="success", reason=reason)
            return self._required_membership_data(membership)
