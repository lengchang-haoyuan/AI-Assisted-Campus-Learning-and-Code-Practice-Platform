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
    GovernanceAppealCreate,
    GovernanceCaseDecisionRequest,
    GovernanceCasePageResponse,
    GovernanceCaseResponse,
    GovernanceCaseStatus,
    GovernanceReportCreate,
    InteractionResponse,
    PublicationDecisionRequest,
    PublicationPageResponse,
    PublicationRequestCreate,
    PublicationResponse,
    PublicationWithdrawRequest,
    PublishProjectRequest,
    TagSummaryResponse,
    ViewResponse,
)

router = APIRouter(tags=["community"])
ResourceId = Annotated[int, Path(ge=1)]


@router.get("/community/projects", response_model=CommunityProjectListResponse, summary="浏览校园社区项目")
def list_community_projects(
    current_user: CurrentUser,
    service: CommunityServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=48)] = 12,
    tag: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
) -> CommunityProjectListResponse:
    return to_community_project_list_response(
        service.list_projects(
            current_user, page=page, page_size=page_size, tag_slug=tag
        )
    )


@router.get("/community/projects/{project_id}", response_model=CommunityProjectResponse, summary="获取社区项目详情")
def get_community_project(
    project_id: ResourceId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> CommunityProjectResponse:
    return to_community_project_response(service.get_project(project_id, current_user))


@router.get("/community/tags", response_model=list[TagSummaryResponse], summary="获取社区项目标签")
def list_community_tags(
    current_user: CurrentUser, service: CommunityServiceDependency
) -> list[TagSummaryResponse]:
    return [to_tag_summary_response(tag) for tag in service.list_tags(current_user)]


@router.post("/projects/{project_id}/publication-requests", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED, summary="申请发布或更新社区作品")
def request_publication(
    project_id: ResourceId,
    payload: PublicationRequestCreate,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> PublicationResponse:
    return PublicationResponse.model_validate(
        service.request_publication(
            current_user,
            project_id=project_id,
            request_key=payload.request_key,
            expected_project_updated_at=payload.expected_project_updated_at,
            kind=payload.kind,
            tag_names=payload.tags,
            attribution=payload.attribution,
            source_license_statement=payload.source_license_statement,
            ai_assistance_statement=payload.ai_assistance_statement,
            human_review_statement=payload.human_review_statement,
        )
    )


@router.get("/projects/{project_id}/publication", response_model=PublicationResponse, summary="查询本人项目发布进度")
def get_project_publication(
    project_id: ResourceId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> PublicationResponse:
    return PublicationResponse.model_validate(
        service.get_publication(current_user, project_id=project_id)
    )


@router.get("/community/publications/mine", response_model=PublicationPageResponse, summary="查询本人发布申请")
def list_my_publications(
    current_user: CurrentUser,
    service: CommunityServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PublicationPageResponse:
    return PublicationPageResponse.model_validate(
        service.publication_list(
            current_user, moderation_queue=False, page=page, page_size=page_size
        )
    )


@router.post("/community/publications/{publication_id}/withdraw", response_model=PublicationResponse, summary="撤回社区发布")
def withdraw_publication(
    publication_id: ResourceId,
    payload: PublicationWithdrawRequest,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> PublicationResponse:
    return PublicationResponse.model_validate(
        service.withdraw_publication(
            current_user,
            publication_id=publication_id,
            expected_revision=payload.expected_revision,
            reason=payload.reason,
        )
    )


@router.get("/community/moderation/publications", response_model=PublicationPageResponse, summary="查询待审核社区作品")
def list_moderation_publications(
    current_user: CurrentUser,
    service: CommunityServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PublicationPageResponse:
    return PublicationPageResponse.model_validate(
        service.publication_list(
            current_user, moderation_queue=True, page=page, page_size=page_size
        )
    )


@router.post("/community/moderation/publications/{publication_id}/decisions", response_model=PublicationResponse, summary="审核或下架社区作品")
def decide_publication(
    publication_id: ResourceId,
    payload: PublicationDecisionRequest,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> PublicationResponse:
    return PublicationResponse.model_validate(
        service.decide_publication(
            current_user,
            publication_id=publication_id,
            expected_revision=payload.expected_revision,
            decision=payload.decision,
            reason=payload.reason,
        )
    )


@router.post("/community/reports", response_model=GovernanceCaseResponse, status_code=status.HTTP_201_CREATED, summary="举报社区项目或评论")
def create_report(
    payload: GovernanceReportCreate,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> GovernanceCaseResponse:
    return GovernanceCaseResponse.model_validate(
        service.report(
            current_user,
            request_key=payload.request_key,
            target_type=payload.target_type,
            target_id=payload.target_id,
            reason=payload.reason,
        )
    )


@router.get("/community/governance/cases", response_model=GovernanceCasePageResponse, summary="查询本人相关或管理员待处理案件")
def list_governance_cases(
    current_user: CurrentUser,
    service: CommunityServiceDependency,
    case_status: Annotated[GovernanceCaseStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> GovernanceCasePageResponse:
    return GovernanceCasePageResponse.model_validate(
        service.case_list(
            current_user, status=case_status, page=page, page_size=page_size
        )
    )


@router.post("/community/moderation/actions/{action_id}/appeals", response_model=GovernanceCaseResponse, status_code=status.HTTP_201_CREATED, summary="对下架或隐藏动作申请复核")
def create_appeal(
    action_id: ResourceId,
    payload: GovernanceAppealCreate,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> GovernanceCaseResponse:
    return GovernanceCaseResponse.model_validate(
        service.appeal(
            current_user,
            action_id=action_id,
            request_key=payload.request_key,
            reason=payload.reason,
        )
    )


@router.post("/community/moderation/cases/{case_id}/decisions", response_model=GovernanceCaseResponse, summary="处理举报或复核")
def decide_governance_case(
    case_id: ResourceId,
    payload: GovernanceCaseDecisionRequest,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> GovernanceCaseResponse:
    return GovernanceCaseResponse.model_validate(
        service.decide_case(
            current_user,
            case_id=case_id,
            expected_revision=payload.expected_revision,
            decision=payload.decision,
            reason=payload.reason,
        )
    )


@router.post("/projects/{project_id}/publish", summary="旧发布入口")
def legacy_publish_project(
    project_id: ResourceId,
    payload: PublishProjectRequest,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> None:
    del project_id, payload, current_user
    service.reject_legacy_publish()


@router.delete("/projects/{project_id}/publish", status_code=status.HTTP_204_NO_CONTENT, summary="兼容撤回社区项目")
def legacy_unpublish_project(
    project_id: ResourceId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> Response:
    service.withdraw_by_project(current_user, project_id=project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/projects/{project_id}/view", response_model=ViewResponse, summary="记录项目浏览")
def record_project_view(
    project_id: ResourceId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> ViewResponse:
    return ViewResponse(view_count=service.record_view(project_id, current_user))


@router.get("/projects/{project_id}/comments", response_model=CommentListResponse, summary="获取项目评论")
def list_project_comments(
    project_id: ResourceId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CommentListResponse:
    return to_comment_list_response(
        service.list_comments(
            project_id, current_user, page=page, page_size=page_size
        )
    )


@router.post("/projects/{project_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED, summary="发表评论")
def create_project_comment(
    project_id: ResourceId,
    payload: CommentCreate,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> CommentResponse:
    return to_comment_response(
        service.create_comment(project_id, current_user, payload.content)
    )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除自己的评论")
def delete_comment(
    comment_id: ResourceId,
    current_user: CurrentUser,
    service: CommunityServiceDependency,
) -> Response:
    service.delete_comment(comment_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/projects/{project_id}/like", response_model=InteractionResponse, summary="点赞项目")
def like_project(project_id: ResourceId, current_user: CurrentUser, service: CommunityServiceDependency) -> InteractionResponse:
    result = service.set_like(project_id, current_user, active=True)
    return InteractionResponse(active=result.active, count=result.count)


@router.delete("/projects/{project_id}/like", response_model=InteractionResponse, summary="取消点赞项目")
def unlike_project(project_id: ResourceId, current_user: CurrentUser, service: CommunityServiceDependency) -> InteractionResponse:
    result = service.set_like(project_id, current_user, active=False)
    return InteractionResponse(active=result.active, count=result.count)


@router.post("/projects/{project_id}/favorite", response_model=InteractionResponse, summary="收藏项目")
def favorite_project(project_id: ResourceId, current_user: CurrentUser, service: CommunityServiceDependency) -> InteractionResponse:
    result = service.set_favorite(project_id, current_user, active=True)
    return InteractionResponse(active=result.active, count=result.count)


@router.delete("/projects/{project_id}/favorite", response_model=InteractionResponse, summary="取消收藏项目")
def unfavorite_project(project_id: ResourceId, current_user: CurrentUser, service: CommunityServiceDependency) -> InteractionResponse:
    result = service.set_favorite(project_id, current_user, active=False)
    return InteractionResponse(active=result.active, count=result.count)
