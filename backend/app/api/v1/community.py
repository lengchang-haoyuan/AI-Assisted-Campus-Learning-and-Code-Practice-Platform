from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import CommunityServiceDependency, CurrentUser
from app.api.presenters import (
    to_comment_list_response,
    to_comment_response,
    to_community_project_list_response,
    to_community_project_response,
    to_tag_summary_response,
)
from app.schemas.community import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    CommunityProjectListResponse,
    CommunityProjectResponse,
    InteractionResponse,
    PublishProjectRequest,
    TagSummaryResponse,
    ViewResponse,
)

router = APIRouter(tags=["community"])
ProjectId = Annotated[int, Path(ge=1)]
CommentId = Annotated[int, Path(ge=1)]


@router.get(
    "/community/projects",
    response_model=CommunityProjectListResponse,
    summary="浏览校园社区项目",
)
async def list_community_projects(
    current_user: CurrentUser,
    service: CommunityServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=48)] = 12,
    tag: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
) -> CommunityProjectListResponse:
    result = service.list_projects(
        current_user.id,
        page=page,
        page_size=page_size,
        tag_slug=tag,
    )
    return to_community_project_list_response(result)


@router.get(
    "/community/projects/{project_id}",
    response_model=CommunityProjectResponse,
    summary="获取社区项目详情",
)
async def get_community_project(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> CommunityProjectResponse:
    return to_community_project_response(
        service.get_project(project_id, current_user.id)
    )


@router.get(
    "/community/tags",
    response_model=list[TagSummaryResponse],
    summary="获取社区项目标签",
)
async def list_community_tags(
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> list[TagSummaryResponse]:
    del current_user
    return [to_tag_summary_response(tag) for tag in service.list_tags()]


@router.post(
    "/projects/{project_id}/publish",
    response_model=CommunityProjectResponse,
    summary="发布项目到校园社区",
)
async def publish_project(
    project_id: ProjectId,
    payload: PublishProjectRequest,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> CommunityProjectResponse:
    return to_community_project_response(
        service.publish_project(project_id, current_user.id, payload.tags)
    )


@router.delete(
    "/projects/{project_id}/publish",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="从校园社区撤下项目",
)
async def unpublish_project(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> Response:
    service.unpublish_project(project_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/projects/{project_id}/view",
    response_model=ViewResponse,
    summary="记录项目浏览",
)
async def record_project_view(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> ViewResponse:
    return ViewResponse(view_count=service.record_view(project_id, current_user.id))


@router.get(
    "/projects/{project_id}/comments",
    response_model=CommentListResponse,
    summary="获取项目评论",
)
async def list_project_comments(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CommentListResponse:
    result = service.list_comments(
        project_id,
        current_user.id,
        page=page,
        page_size=page_size,
    )
    return to_comment_list_response(result)


@router.post(
    "/projects/{project_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="发表评论",
)
async def create_project_comment(
    project_id: ProjectId,
    payload: CommentCreate,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> CommentResponse:
    return to_comment_response(
        service.create_comment(project_id, current_user.id, payload.content)
    )


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除自己的评论",
)
async def delete_comment(
    comment_id: CommentId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> Response:
    service.delete_comment(comment_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/projects/{project_id}/like",
    response_model=InteractionResponse,
    summary="点赞项目",
)
async def like_project(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> InteractionResponse:
    result = service.set_like(project_id, current_user.id, active=True)
    return InteractionResponse(active=result.active, count=result.count)


@router.delete(
    "/projects/{project_id}/like",
    response_model=InteractionResponse,
    summary="取消点赞项目",
)
async def unlike_project(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> InteractionResponse:
    result = service.set_like(project_id, current_user.id, active=False)
    return InteractionResponse(active=result.active, count=result.count)


@router.post(
    "/projects/{project_id}/favorite",
    response_model=InteractionResponse,
    summary="收藏项目",
)
async def favorite_project(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> InteractionResponse:
    result = service.set_favorite(project_id, current_user.id, active=True)
    return InteractionResponse(active=result.active, count=result.count)


@router.delete(
    "/projects/{project_id}/favorite",
    response_model=InteractionResponse,
    summary="取消收藏项目",
)
async def unfavorite_project(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> InteractionResponse:
    result = service.set_favorite(project_id, current_user.id, active=False)
    return InteractionResponse(active=result.active, count=result.count)
