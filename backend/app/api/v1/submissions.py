from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import CurrentUser, SubmissionServiceDependency
from app.schemas.submission import (
    FeedbackCreateRequest,
    FeedbackResponse,
    NotificationPageResponse,
    NotificationResponse,
    PendingAssignmentPageResponse,
    SubmissionCreateRequest,
    SubmissionPageResponse,
    SubmissionResponse,
    SubmissionVersionPageResponse,
)

router = APIRouter(tags=["campus-submissions"])
ResourceId = Annotated[int, Path(ge=1)]
VersionNumber = Annotated[int, Path(ge=1)]


@router.post(
    "/campus/assignments/{assignment_id}/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="提交成果或追加版本",
)
def submit_assignment(
    assignment_id: ResourceId,
    payload: SubmissionCreateRequest,
    response: Response,
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
) -> SubmissionResponse:
    result, replayed = service.submit(
        current_user, assignment_id=assignment_id, **payload.model_dump()
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return SubmissionResponse.model_validate(result)


@router.get(
    "/campus/assignments/{assignment_id}/submissions",
    response_model=SubmissionPageResponse,
    summary="查询指定任务的提交",
)
def list_assignment_submissions(
    assignment_id: ResourceId,
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SubmissionPageResponse:
    return SubmissionPageResponse.model_validate(
        service.submissions(
            current_user,
            assignment_id=assignment_id,
            pending_only=False,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/campus/submissions",
    response_model=SubmissionPageResponse,
    summary="查询本人提交或教师待评列表",
)
def list_submissions(
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
    pending_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SubmissionPageResponse:
    return SubmissionPageResponse.model_validate(
        service.submissions(
            current_user,
            assignment_id=None,
            pending_only=pending_only,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/campus/submissions/pending-assignments",
    response_model=PendingAssignmentPageResponse,
    summary="查询学生待提交或待修改任务",
)
def list_pending_assignments(
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PendingAssignmentPageResponse:
    return PendingAssignmentPageResponse.model_validate(
        service.pending_assignments(
            current_user,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/campus/submissions/{submission_id}",
    response_model=SubmissionResponse,
    summary="获取提交详情",
)
def get_submission(
    submission_id: ResourceId,
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
) -> SubmissionResponse:
    return SubmissionResponse.model_validate(
        service.get_submission(current_user, submission_id=submission_id)
    )


@router.get(
    "/campus/submissions/{submission_id}/versions",
    response_model=SubmissionVersionPageResponse,
    summary="分页查询提交版本历史",
)
def list_submission_versions(
    submission_id: ResourceId,
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SubmissionVersionPageResponse:
    return SubmissionVersionPageResponse.model_validate(
        service.versions(
            current_user,
            submission_id=submission_id,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/campus/submissions/{submission_id}/versions/{version_number}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="教师退回或确认通过指定版本",
)
def create_feedback(
    submission_id: ResourceId,
    version_number: VersionNumber,
    payload: FeedbackCreateRequest,
    response: Response,
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
) -> FeedbackResponse:
    result, replayed = service.feedback(
        current_user,
        submission_id=submission_id,
        version_number=version_number,
        **payload.model_dump(),
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return FeedbackResponse.model_validate(result)


@router.delete(
    "/campus/submissions/{submission_id}/versions/{version_number}/project-reference",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="本人解除提交版本的项目来源关联",
)
def detach_project_reference(
    submission_id: ResourceId,
    version_number: VersionNumber,
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
) -> Response:
    service.detach_project(
        current_user,
        submission_id=submission_id,
        version_number=version_number,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/notifications",
    response_model=NotificationPageResponse,
    summary="查询本人站内通知",
)
def list_notifications(
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> NotificationPageResponse:
    return NotificationPageResponse.model_validate(
        service.notifications(
            current_user,
            unread_only=unread_only,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    summary="标记本人通知为已读",
)
def read_notification(
    notification_id: ResourceId,
    current_user: CurrentUser,
    service: SubmissionServiceDependency,
) -> NotificationResponse:
    return NotificationResponse.model_validate(
        service.read_notification(current_user, notification_id=notification_id)
    )
