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
from app.schemas.workspace import (
    LearningRecordListResponse,
    LearningRecordResponse,
    TaskListResponse,
    TaskResponse,
    WorkspaceDashboardResponse,
    WorkspaceProjectDetailResponse,
    WorkspaceProjectListResponse,
    WorkspaceProjectRefResponse,
    WorkspaceProjectResponse,
    WorkspaceStatsResponse,
)
from app.services.auth import UserIdentity
from app.services.community import (
    CommentData,
    CommentPage,
    CommunityProjectData,
    CommunityProjectPage,
    TagSummaryData,
)
from app.services.project import ProjectData, ProjectPage
from app.services.workspace import (
    LearningRecordData,
    LearningRecordPage,
    TaskData,
    TaskPage,
    WorkspaceDashboardData,
    WorkspaceProjectData,
    WorkspaceProjectDetailData,
    WorkspaceProjectPage,
)


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
        progress=project.progress,
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


def to_task_response(task: TaskData) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        status=task.status,
        scheduled_date=task.scheduled_date,
        start_time=task.start_time,
        end_time=task.end_time,
        estimated_minutes=task.estimated_minutes,
        completed_at=task.completed_at,
        project=WorkspaceProjectRefResponse(id=task.project.id, name=task.project.name)
        if task.project
        else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def to_task_list_response(page: TaskPage) -> TaskListResponse:
    return TaskListResponse(
        items=[to_task_response(task) for task in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_learning_record_response(record: LearningRecordData) -> LearningRecordResponse:
    return LearningRecordResponse(
        id=record.id,
        title=record.title,
        content=record.content,
        record_type=record.record_type,
        duration_minutes=record.duration_minutes,
        occurred_at=record.occurred_at,
        project=WorkspaceProjectRefResponse(
            id=record.project.id,
            name=record.project.name,
        )
        if record.project
        else None,
        created_at=record.created_at,
    )


def to_learning_record_list_response(
    page: LearningRecordPage,
) -> LearningRecordListResponse:
    return LearningRecordListResponse(
        items=[to_learning_record_response(record) for record in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_workspace_project_response(
    project: WorkspaceProjectData,
) -> WorkspaceProjectResponse:
    return WorkspaceProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        difficulty=project.difficulty,
        status=project.status,
        language=project.language,
        progress=project.progress,
        linked_task_count=project.linked_task_count,
        completed_task_count=project.completed_task_count,
        recorded_minutes=project.recorded_minutes,
        updated_at=project.updated_at,
    )


def to_workspace_project_list_response(
    page: WorkspaceProjectPage,
) -> WorkspaceProjectListResponse:
    return WorkspaceProjectListResponse(
        items=[to_workspace_project_response(project) for project in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_workspace_project_detail_response(
    project: WorkspaceProjectDetailData,
) -> WorkspaceProjectDetailResponse:
    return WorkspaceProjectDetailResponse(
        **to_workspace_project_response(project).model_dump(),
        recent_tasks=[to_task_response(task) for task in project.recent_tasks],
        recent_records=[
            to_learning_record_response(record) for record in project.recent_records
        ],
    )


def to_workspace_dashboard_response(
    dashboard: WorkspaceDashboardData,
) -> WorkspaceDashboardResponse:
    return WorkspaceDashboardResponse(
        date=dashboard.date,
        stats=WorkspaceStatsResponse(
            today_task_total=dashboard.stats.today_task_total,
            today_task_completed=dashboard.stats.today_task_completed,
            today_estimated_minutes=dashboard.stats.today_estimated_minutes,
            today_recorded_minutes=dashboard.stats.today_recorded_minutes,
            learning_progress=dashboard.stats.learning_progress,
            project_total=dashboard.stats.project_total,
            active_project_total=dashboard.stats.active_project_total,
        ),
        today_tasks=[to_task_response(task) for task in dashboard.today_tasks],
        recent_projects=[
            to_workspace_project_response(project)
            for project in dashboard.recent_projects
        ],
        recent_records=[
            to_learning_record_response(record) for record in dashboard.recent_records
        ],
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
