from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import (
    CampusServiceDependency,
    CurrentUser,
    SensitiveActionLimiterDependency,
)
from app.schemas.campus import (
    AccountPageResponse,
    AccountResponse,
    AccountUpdateRequest,
    AuditPageResponse,
    CampusMeResponse,
    InvitationCreateRequest,
    InvitationIssuedResponse,
    InvitationPageResponse,
    InvitationRedeemRequest,
    InvitationResponse,
    MembershipResponse,
    PasswordResetIssuedResponse,
    ReasonRequest,
)

router = APIRouter(prefix="/campus", tags=["campus"])


def client_key(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


@router.get("/me", response_model=CampusMeResponse, summary="获取本人校园身份")
def campus_me(
    current_user: CurrentUser, service: CampusServiceDependency
) -> CampusMeResponse:
    return CampusMeResponse(membership=service.me(current_user))


@router.post(
    "/invitations",
    response_model=InvitationIssuedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="签发校园邀请",
)
def create_invitation(
    payload: InvitationCreateRequest,
    current_user: CurrentUser,
    service: CampusServiceDependency,
) -> InvitationIssuedResponse:
    invitation, token = service.issue_invitation(
        current_user,
        target_user_id=payload.target_user_id,
        target_email=payload.target_email,
        role=payload.role,
        expires_in_hours=payload.expires_in_hours,
        reason=payload.reason,
    )
    return InvitationIssuedResponse(
        **InvitationResponse.model_validate(invitation).model_dump(), token=token
    )


@router.post(
    "/invitations/redeem",
    response_model=MembershipResponse,
    summary="兑换本人校园邀请",
)
def redeem_invitation(
    payload: InvitationRedeemRequest,
    request: Request,
    current_user: CurrentUser,
    service: CampusServiceDependency,
    limiter: SensitiveActionLimiterDependency,
) -> MembershipResponse:
    limiter.check(f"invite:{client_key(request)}:{current_user.id}", limit=8, window_seconds=300)
    return MembershipResponse.model_validate(
        service.redeem_invitation(current_user, token=payload.token)
    )


@router.get(
    "/admin/accounts", response_model=AccountPageResponse, summary="查询校园账号"
)
def list_accounts(
    current_user: CurrentUser,
    service: CampusServiceDependency,
    query: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> AccountPageResponse:
    items, total, total_pages = service.accounts(
        current_user, query=query, page=page, page_size=page_size
    )
    return AccountPageResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.patch(
    "/admin/accounts/{user_id}",
    response_model=AccountResponse,
    summary="变更账号或校园身份",
)
def update_account(
    user_id: int,
    payload: AccountUpdateRequest,
    current_user: CurrentUser,
    service: CampusServiceDependency,
) -> AccountResponse:
    return AccountResponse.model_validate(
        service.update_account(
            current_user,
            user_id=user_id,
            reason=payload.reason,
            expected_revision=payload.expected_revision,
            expected_auth_version=payload.expected_auth_version,
            role=payload.role,
            campus_status=payload.campus_status,
            account_enabled=payload.account_enabled,
        )
    )


@router.get(
    "/admin/invitations",
    response_model=InvitationPageResponse,
    summary="查询校园邀请",
)
def list_invitations(
    current_user: CurrentUser,
    service: CampusServiceDependency,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> InvitationPageResponse:
    items, total, total_pages = service.invitations(current_user, page=page, page_size=page_size)
    return InvitationPageResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.post(
    "/admin/invitations/{invitation_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="撤销校园邀请",
)
def revoke_invitation(
    invitation_id: int,
    payload: ReasonRequest,
    current_user: CurrentUser,
    service: CampusServiceDependency,
) -> Response:
    service.revoke_invitation(current_user, invitation_id=invitation_id, reason=payload.reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/admin/accounts/{user_id}/password-resets",
    response_model=PasswordResetIssuedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="签发一次性密码重置凭证",
)
def issue_password_reset(
    user_id: int,
    payload: ReasonRequest,
    current_user: CurrentUser,
    service: CampusServiceDependency,
) -> PasswordResetIssuedResponse:
    token, expires_at = service.issue_password_reset(current_user, user_id=user_id, reason=payload.reason)
    return PasswordResetIssuedResponse(token=token, expires_at=expires_at)


@router.get(
    "/admin/audits", response_model=AuditPageResponse, summary="查询账号管理审计"
)
def list_audits(
    current_user: CurrentUser,
    service: CampusServiceDependency,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> AuditPageResponse:
    items, total, total_pages = service.audits(current_user, page=page, page_size=page_size)
    return AuditPageResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
