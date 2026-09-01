from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import CourseServiceDependency, CurrentUser
from app.api.presenters import to_course_list_response, to_course_response
from app.schemas.course import (
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
)
from app.services.course import CourseCreateData, CourseUpdateData

router = APIRouter(prefix="/courses", tags=["courses"])
CourseId = Annotated[int, Path(ge=1)]


@router.get("", response_model=CourseListResponse, summary="获取我的课程")
async def list_courses(
    current_user: CurrentUser,
    service: CourseServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CourseListResponse:
    return to_course_list_response(
        service.list_courses(current_user.id, page=page, page_size=page_size)
    )


@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建课程",
)
async def create_course(
    payload: CourseCreate,
    current_user: CurrentUser,
    service: CourseServiceDependency,
) -> CourseResponse:
    return to_course_response(
        service.create_course(current_user.id, CourseCreateData(**payload.model_dump()))
    )


@router.get("/{course_id}", response_model=CourseResponse, summary="获取课程详情")
async def get_course(
    course_id: CourseId,
    current_user: CurrentUser,
    service: CourseServiceDependency,
) -> CourseResponse:
    return to_course_response(service.get_course(course_id, current_user.id))


@router.put("/{course_id}", response_model=CourseResponse, summary="更新课程")
async def update_course(
    course_id: CourseId,
    payload: CourseUpdate,
    current_user: CurrentUser,
    service: CourseServiceDependency,
) -> CourseResponse:
    return to_course_response(
        service.update_course(
            course_id,
            current_user.id,
            CourseUpdateData(payload.model_dump(exclude_unset=True)),
        )
    )


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: CourseId,
    current_user: CurrentUser,
    service: CourseServiceDependency,
) -> Response:
    service.delete_course(course_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
