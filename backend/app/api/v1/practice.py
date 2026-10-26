from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, status

from app.api.deps import CurrentUser
from app.api.practice_deps import PracticeServiceDependency
from app.schemas.practice import PracticeActionRequest, PracticeSessionCreate, PracticeAttemptSubmission

router = APIRouter(tags=["practice-sessions"])

ProjectId = Annotated[int, Path(ge=1)]


@router.post(
    "/projects/{project_id}/practice-sessions",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    summary="从固定模板创建本人实践会话",
)
def create_practice_session(
    project_id: ProjectId,
    payload: PracticeSessionCreate,
    current_user: CurrentUser,
    service: PracticeServiceDependency,
) -> dict[str, object]:
    return service.create(
        owner_id=current_user.id,
        project_id=project_id,
        template_id=payload.template_id,
        template_version=payload.template_version,
        expected_context_version=payload.expected_context_version,
        request_key=payload.request_key,
    )


@router.get(
    "/projects/{project_id}/practice-sessions",
    response_model=None,
    summary="查询本人项目实践会话历史",
)
def list_practice_sessions(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: PracticeServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, object]]:
    return service.list(
        owner_id=current_user.id,
        project_id=project_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/practice-sessions/{session_id}",
    response_model=None,
    summary="恢复查询本人实践会话绑定步骤与版本",
)
def get_practice_session(
    session_id: UUID,
    current_user: CurrentUser,
    service: PracticeServiceDependency,
) -> dict[str, object]:
    return service.get(owner_id=current_user.id, session_id=str(session_id))


@router.post(
    "/practice-sessions/{session_id}/actions",
    response_model=None,
    summary="执行本人实践会话的固定单步动作",
)
async def perform_practice_action(
    session_id: UUID,
    payload: PracticeActionRequest,
    current_user: CurrentUser,
    service: PracticeServiceDependency,
) -> dict[str, object]:
    return await service.action(
        owner_id=current_user.id,
        session_id=str(session_id),
        action=payload.action,
        expected_revision=payload.expected_revision,
        request_key=payload.request_key,
        attempt_id=str(payload.attempt_id) if payload.attempt_id is not None else None,
    )


@router.post(
    "/practice-sessions/{session_id}/attempts",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    summary="追加本人固定CSV尝试，静态评审需另行明确触发",
)
def submit_practice_attempt(
    session_id: UUID,
    payload: PracticeAttemptSubmission,
    current_user: CurrentUser,
    service: PracticeServiceDependency,
) -> dict[str, object]:
    return service.submit_attempt(owner_id=current_user.id, session_id=str(session_id),
        **payload.model_dump())
