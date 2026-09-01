from app.schemas.community import (
    CommentAuthorResponse,
    CommentListResponse,
    CommentResponse,
    CommunityOwnerResponse,
    CommunityProjectListResponse,
    CommunityProjectResponse,
    TagResponse,
    TagSummaryResponse,
)
from app.schemas.project import (
    ProjectListResponse,
    ProjectOwnerResponse,
    ProjectResponse,
)
from app.schemas.user import UserResponse
from app.services.auth import UserIdentity
from app.services.community import (
    CommentData,
    CommentPage,
    CommunityProjectData,
    CommunityProjectPage,
    TagSummaryData,
)
from app.services.project import ProjectData, ProjectPage


def to_user_response(user: UserIdentity) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        bio=user.bio,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def to_project_response(project: ProjectData) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        difficulty=project.difficulty,
        language=project.language,
        framework=project.framework,
        frontend=project.frontend,
        backend=project.backend,
        database=project.database,
        requirements=project.requirements,
        output_requirement=project.output_requirement,
        owner=ProjectOwnerResponse(
            id=project.owner.id,
            username=project.owner.username,
        ),
        tags=[TagResponse(id=tag[0], name=tag[1], slug=tag[2]) for tag in project.tags],
        is_published=project.is_published,
        published_at=project.published_at,
        view_count=project.view_count,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def to_project_list_response(page: ProjectPage) -> ProjectListResponse:
    return ProjectListResponse(
        items=[to_project_response(project) for project in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_community_project_response(
    project: CommunityProjectData,
) -> CommunityProjectResponse:
    return CommunityProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        difficulty=project.difficulty,
        status=project.status,
        language=project.language,
        framework=project.framework,
        frontend=project.frontend,
        backend=project.backend,
        database=project.database,
        owner=CommunityOwnerResponse(
            id=project.owner.id,
            username=project.owner.username,
            avatar_url=project.owner.avatar_url,
        ),
        tags=[TagResponse(id=tag.id, name=tag.name, slug=tag.slug) for tag in project.tags],
        published_at=project.published_at,
        updated_at=project.updated_at,
        view_count=project.view_count,
        comment_count=project.comment_count,
        like_count=project.like_count,
        favorite_count=project.favorite_count,
        liked=project.liked,
        favorited=project.favorited,
    )


def to_community_project_list_response(
    page: CommunityProjectPage,
) -> CommunityProjectListResponse:
    return CommunityProjectListResponse(
        items=[to_community_project_response(project) for project in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_tag_summary_response(tag: TagSummaryData) -> TagSummaryResponse:
    return TagSummaryResponse(
        id=tag.id,
        name=tag.name,
        slug=tag.slug,
        project_count=tag.project_count,
    )


def to_comment_response(comment: CommentData) -> CommentResponse:
    return CommentResponse(
        id=comment.id,
        project_id=comment.project_id,
        author=CommentAuthorResponse(
            id=comment.author.id,
            username=comment.author.username,
            avatar_url=comment.author.avatar_url,
        ),
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        can_delete=comment.can_delete,
    )


def to_comment_list_response(page: CommentPage) -> CommentListResponse:
    return CommentListResponse(
        items=[to_comment_response(comment) for comment in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )
from app.schemas.community import (
    CommentAuthorResponse,
    CommentListResponse,
    CommentResponse,
    CommunityOwnerResponse,
    CommunityProjectListResponse,
    CommunityProjectResponse,
    TagResponse,
    TagSummaryResponse,
)
