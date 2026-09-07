from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.deps import CurrentUser, TeachingServiceDependency
from app.schemas.teaching import (
    AssignmentTransitionRequest,
    ClassMemberCreateRequest,
    ClassMemberPageResponse,
    ClassMemberResponse,
    ClassMemberUpdateRequest,
    TeachingAssignmentCreateRequest,
    TeachingAssignmentPageResponse,
    TeachingAssignmentResponse,
    TeachingAssignmentUpdateRequest,
    TeachingClassCreateRequest,
    TeachingClassPageResponse,
    TeachingClassResponse,
    TeachingClassUpdateRequest,
)

router = APIRouter(prefix="/campus", tags=["campus-teaching"])
ResourceId = Annotated[int, Path(ge=1)]


@router.get(
    "/classes", response_model=TeachingClassPageResponse, summary="查询可访问的教学班"
)
def list_classes(
    current_user: CurrentUser,
    service: TeachingServiceDependency,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> TeachingClassPageResponse:
    result = service.classes(current_user, page=page, page_size=page_size)
    return TeachingClassPageResponse(
        items=result.items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.post(
    "/classes",
    response_model=TeachingClassResponse,
    status_code=status.HTTP_201_CREATED,
    summary="教师创建教学班",
)
def create_class(
    payload: TeachingClassCreateRequest,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> TeachingClassResponse:
    return TeachingClassResponse.model_validate(
        service.create_class(current_user, **payload.model_dump())
    )


@router.get(
    "/classes/{class_id}",
    response_model=TeachingClassResponse,
    summary="获取教学班详情",
)
def get_class(
    class_id: ResourceId,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> TeachingClassResponse:
    return TeachingClassResponse.model_validate(
        service.get_class(current_user, class_id=class_id)
    )


@router.patch(
    "/classes/{class_id}",
    response_model=TeachingClassResponse,
    summary="编辑或归档教学班",
)
def update_class(
    class_id: ResourceId,
    payload: TeachingClassUpdateRequest,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> TeachingClassResponse:
    return TeachingClassResponse.model_validate(
        service.update_class(
            current_user,
            class_id=class_id,
            expected_revision=payload.expected_revision,
            values=payload.model_dump(
                exclude={"expected_revision"}, exclude_none=True
            ),
        )
    )


@router.get(
    "/classes/{class_id}/members",
    response_model=ClassMemberPageResponse,
    summary="查询教学班成员",
)
def list_members(
    class_id: ResourceId,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ClassMemberPageResponse:
    result = service.members(
        current_user, class_id=class_id, page=page, page_size=page_size
    )
    return ClassMemberPageResponse(
        items=result.items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.post(
    "/classes/{class_id}/members",
    response_model=ClassMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="增加教学班成员",
)
def add_member(
    class_id: ResourceId,
    payload: ClassMemberCreateRequest,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> ClassMemberResponse:
    return ClassMemberResponse.model_validate(
        service.add_member(current_user, class_id=class_id, **payload.model_dump())
    )


@router.patch(
    "/classes/{class_id}/members/{member_id}",
    response_model=ClassMemberResponse,
    summary="退出或移除教学班成员",
)
def update_member(
    class_id: ResourceId,
    member_id: ResourceId,
    payload: ClassMemberUpdateRequest,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> ClassMemberResponse:
    return ClassMemberResponse.model_validate(
        service.update_member(
            current_user,
            class_id=class_id,
            member_id=member_id,
            **payload.model_dump(),
        )
    )


@router.get(
    "/classes/{class_id}/assignments",
    response_model=TeachingAssignmentPageResponse,
    summary="查询教学班任务",
)
def list_assignments(
    class_id: ResourceId,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> TeachingAssignmentPageResponse:
    result = service.assignments(
        current_user, class_id=class_id, page=page, page_size=page_size
    )
    return TeachingAssignmentPageResponse(
        items=result.items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.post(
    "/classes/{class_id}/assignments",
    response_model=TeachingAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建教学任务草稿",
)
def create_assignment(
    class_id: ResourceId,
    payload: TeachingAssignmentCreateRequest,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> TeachingAssignmentResponse:
    return TeachingAssignmentResponse.model_validate(
        service.create_assignment(
            current_user, class_id=class_id, **payload.model_dump()
        )
    )


@router.get(
    "/assignments/{assignment_id}",
    response_model=TeachingAssignmentResponse,
    summary="获取教学任务详情",
)
def get_assignment(
    assignment_id: ResourceId,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> TeachingAssignmentResponse:
    return TeachingAssignmentResponse.model_validate(
        service.get_assignment(current_user, assignment_id=assignment_id)
    )


@router.patch(
    "/assignments/{assignment_id}",
    response_model=TeachingAssignmentResponse,
    summary="修改教学任务",
)
def update_assignment(
    assignment_id: ResourceId,
    payload: TeachingAssignmentUpdateRequest,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> TeachingAssignmentResponse:
    return TeachingAssignmentResponse.model_validate(
        service.update_assignment(
            current_user,
            assignment_id=assignment_id,
            expected_revision=payload.expected_revision,
            values=payload.model_dump(
                exclude={"expected_revision"}, exclude_unset=True
            ),
        )
    )


@router.post(
    "/assignments/{assignment_id}/publish",
    response_model=TeachingAssignmentResponse,
    summary="发布教学任务",
)
def publish_assignment(
    assignment_id: ResourceId,
    payload: AssignmentTransitionRequest,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> TeachingAssignmentResponse:
    return TeachingAssignmentResponse.model_validate(
        service.publish_assignment(
            current_user,
            assignment_id=assignment_id,
            expected_revision=payload.expected_revision,
        )
    )


@router.post(
    "/assignments/{assignment_id}/close",
    response_model=TeachingAssignmentResponse,
    summary="关闭教学任务",
)
def close_assignment(
    assignment_id: ResourceId,
    payload: AssignmentTransitionRequest,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> TeachingAssignmentResponse:
    return TeachingAssignmentResponse.model_validate(
        service.close_assignment(
            current_user,
            assignment_id=assignment_id,
            expected_revision=payload.expected_revision,
        )
    )


@router.post(
    "/assignments/{assignment_id}/archive",
    response_model=TeachingAssignmentResponse,
    summary="归档教学任务",
)
def archive_assignment(
    assignment_id: ResourceId,
    payload: AssignmentTransitionRequest,
    current_user: CurrentUser,
    service: TeachingServiceDependency,
) -> TeachingAssignmentResponse:
    return TeachingAssignmentResponse.model_validate(
        service.archive_assignment(
            current_user,
            assignment_id=assignment_id,
            expected_revision=payload.expected_revision,
        )
    )
