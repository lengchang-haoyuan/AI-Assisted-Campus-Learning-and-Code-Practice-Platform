from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import CurrentUser, LearningServiceDependency
from app.api.presenters import (
    to_learning_record_list_v2_response,
    to_learning_record_v2_response,
    to_learning_task_list_response,
    to_learning_task_v2_response,
    to_plan_list_response,
    to_plan_response,
)
from app.schemas.learning import (
    LearningRecordCreate,
    LearningRecordListResponse,
    LearningRecordResponse,
    LearningRecordUpdate,
    LearningTaskCreate,
    LearningTaskListResponse,
    LearningTaskResponse,
    LearningTaskUpdate,
    PlanCreate,
    PlanListResponse,
    PlanResponse,
    PlanUpdate,
)
from app.services.learning import (
    PlanCreateData,
    PlanUpdateData,
    RecordCreateData,
    RecordUpdateData,
    TaskCreateData,
    TaskUpdateData,
)

router = APIRouter(prefix="/learning", tags=["learning"])
ResourceId = Annotated[int, Path(ge=1)]


@router.get("/plans", response_model=PlanListResponse, summary="获取学习计划列表")
def list_plans(
    current_user: CurrentUser,
    service: LearningServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PlanListResponse:
    return to_plan_list_response(
        service.list_plans(current_user.id, page=page, page_size=page_size)
    )


@router.post(
    "/plans",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建学习计划",
)
def create_plan(
    payload: PlanCreate,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> PlanResponse:
    return to_plan_response(
        service.create_plan(current_user.id, PlanCreateData(**payload.model_dump()))
    )


@router.get("/plans/{plan_id}", response_model=PlanResponse, summary="获取学习计划详情")
def get_plan(
    plan_id: ResourceId,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> PlanResponse:
    return to_plan_response(service.get_plan(plan_id, current_user.id))


@router.put("/plans/{plan_id}", response_model=PlanResponse, summary="更新学习计划")
def update_plan(
    plan_id: ResourceId,
    payload: PlanUpdate,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> PlanResponse:
    data = PlanUpdateData(payload.model_dump(exclude_unset=True))
    return to_plan_response(service.update_plan(plan_id, current_user.id, data))


@router.delete(
    "/plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除学习计划",
)
def delete_plan(
    plan_id: ResourceId,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> Response:
    service.delete_plan(plan_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks", response_model=LearningTaskListResponse, summary="获取每日任务列表")
def list_tasks(
    current_user: CurrentUser,
    service: LearningServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    scheduled_date: date | None = None,
    plan_id: Annotated[int | None, Query(ge=1)] = None,
) -> LearningTaskListResponse:
    return to_learning_task_list_response(
        service.list_tasks(
            current_user.id,
            page=page,
            page_size=page_size,
            scheduled_date=scheduled_date,
            plan_id=plan_id,
        )
    )


@router.post(
    "/tasks",
    response_model=LearningTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建每日任务",
)
def create_task(
    payload: LearningTaskCreate,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> LearningTaskResponse:
    return to_learning_task_v2_response(
        service.create_task(current_user.id, TaskCreateData(**payload.model_dump()))
    )


@router.get("/tasks/{task_id}", response_model=LearningTaskResponse, summary="获取任务详情")
def get_task(
    task_id: ResourceId,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> LearningTaskResponse:
    return to_learning_task_v2_response(service.get_task(task_id, current_user.id))


@router.put("/tasks/{task_id}", response_model=LearningTaskResponse, summary="更新每日任务")
def update_task(
    task_id: ResourceId,
    payload: LearningTaskUpdate,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> LearningTaskResponse:
    data = TaskUpdateData(payload.model_dump(exclude_unset=True))
    return to_learning_task_v2_response(
        service.update_task(task_id, current_user.id, data)
    )


@router.post(
    "/tasks/{task_id}/complete",
    response_model=LearningTaskResponse,
    summary="完成每日任务",
)
def complete_task(
    task_id: ResourceId,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> LearningTaskResponse:
    return to_learning_task_v2_response(service.complete_task(task_id, current_user.id))


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除每日任务",
)
def delete_task(
    task_id: ResourceId,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> Response:
    service.delete_task(task_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/records", response_model=LearningRecordListResponse, summary="获取学习记录列表")
def list_records(
    current_user: CurrentUser,
    service: LearningServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LearningRecordListResponse:
    return to_learning_record_list_v2_response(
        service.list_records(current_user.id, page=page, page_size=page_size)
    )


@router.post(
    "/records",
    response_model=LearningRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建学习记录",
)
def create_record(
    payload: LearningRecordCreate,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> LearningRecordResponse:
    return to_learning_record_v2_response(
        service.create_record(current_user.id, RecordCreateData(**payload.model_dump()))
    )


@router.get("/records/{record_id}", response_model=LearningRecordResponse, summary="获取学习记录详情")
def get_record(
    record_id: ResourceId,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> LearningRecordResponse:
    return to_learning_record_v2_response(
        service.get_record(record_id, current_user.id)
    )


@router.put("/records/{record_id}", response_model=LearningRecordResponse, summary="更新学习记录")
def update_record(
    record_id: ResourceId,
    payload: LearningRecordUpdate,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> LearningRecordResponse:
    data = RecordUpdateData(payload.model_dump(exclude_unset=True))
    return to_learning_record_v2_response(
        service.update_record(record_id, current_user.id, data)
    )


@router.delete(
    "/records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除学习记录",
)
def delete_record(
    record_id: ResourceId,
    current_user: CurrentUser,
    service: LearningServiceDependency,
) -> Response:
    service.delete_record(record_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
