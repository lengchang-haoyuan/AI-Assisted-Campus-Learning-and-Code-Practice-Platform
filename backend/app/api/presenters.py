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
from app.schemas.course import CourseListResponse, CourseResponse
from app.schemas.learning import (
    LearningRecordListResponse as LearningRecordListV2Response,
    LearningRecordResponse as LearningRecordV2Response,
    LearningTaskListResponse,
    LearningTaskResponse,
    PlanListResponse,
    PlanResponse,
    ResourceRefResponse,
)
from app.schemas.project import (
    ProjectListResponse,
    ProjectOwnerResponse,
    ProjectResponse,
)
from app.schemas.project_context import (
    ContextFieldMetadataResponse,
    ContextSourceResponse,
    NodeContextResponse,
    ProjectContextMutationResponse,
    ProjectContextResponse,
    ProjectContextValuesResponse,
)
from app.schemas.user import UserResponse
from app.schemas.workflow import (
    WorkflowEdgeListResponse,
    WorkflowEdgeResponse,
    WorkflowGraphResponse,
    WorkflowListResponse,
    WorkflowNodeListResponse,
    WorkflowNodeResponse,
    WorkflowProjectResponse,
    WorkflowRunErrorResponse,
    WorkflowRunListResponse,
    WorkflowRunNodeResponse,
    WorkflowRunResponse,
    WorkflowResponse,
)
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
from app.services.course import CourseData, CoursePage
from app.services.learning import (
    PlanData,
    PlanPage,
    RecordData,
    RecordPage,
    ResourceRefData,
    TaskData as LearningTaskData,
    TaskPage as LearningTaskPage,
)
from app.services.project import ProjectData, ProjectPage
from app.services.project_context import (
    NodeContextData,
    ProjectContextData,
    ProjectContextMutationData,
)
from app.services.workflow import (
    WorkflowData,
    WorkflowEdgeData,
    WorkflowGraphData,
    WorkflowNodeData,
    WorkflowPage,
    WorkflowRunData,
    WorkflowRunPage,
)
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


def to_project_context_response(context: ProjectContextData) -> ProjectContextResponse:
    values = context.values
    return ProjectContextResponse(
        project_id=context.project_id,
        version=context.version,
        values=ProjectContextValuesResponse(
            project_name=values.project_name,
            language=values.language,
            framework=values.framework,
            frontend=values.frontend,
            backend=values.backend,
            database=values.database,
            difficulty=values.difficulty,
            requirements=values.requirements,
            output_requirement=values.output_requirement,
            architecture=values.architecture,
            features=values.features,
            constraints=values.constraints,
            extensions=values.extensions,
        ),
        field_metadata={
            field_name: ContextFieldMetadataResponse(
                version=metadata.version,
                updated_at=metadata.updated_at,
                source=ContextSourceResponse(
                    type=metadata.source.type,
                    id=metadata.source.id,
                    node_key=metadata.source.node_key,
                ),
            )
            for field_name, metadata in context.field_metadata.items()
        },
        updated_at=context.updated_at,
        source=ContextSourceResponse(
            type=context.source.type,
            id=context.source.id,
            node_key=context.source.node_key,
        ),
        is_stale=context.is_stale,
        stale_fields=context.stale_fields,
        stale_node_ids=context.stale_node_ids,
    )


def to_project_context_mutation_response(
    mutation: ProjectContextMutationData,
) -> ProjectContextMutationResponse:
    return ProjectContextMutationResponse(
        context=to_project_context_response(mutation.context),
        changed_fields=mutation.changed_fields,
        stale_node_ids=mutation.stale_node_ids,
    )


def to_node_context_response(context: NodeContextData) -> NodeContextResponse:
    return NodeContextResponse(
        project_id=context.project_id,
        workflow_id=context.workflow_id,
        node_id=context.node_id,
        node_key=context.node_key,
        context_version=context.context_version,
        values=context.values,
        is_stale=context.is_stale,
    )


def to_community_project_response(
    project: CommunityProjectData,
) -> CommunityProjectResponse:
    return CommunityProjectResponse(
        id=project.id,
        publication_id=project.publication_id,
        publication_kind=project.publication_kind,
        publication_status=project.publication_status,
        publication_version=project.publication_version,
        name=project.name,
        description=project.description,
        difficulty=project.difficulty,
        status=project.status,
        language=project.language,
        framework=project.framework,
        frontend=project.frontend,
        backend=project.backend,
        database=project.database,
        repository_url=project.repository_url,
        attribution=project.attribution,
        source_license_statement=project.source_license_statement,
        ai_assistance_statement=project.ai_assistance_statement,
        human_review_statement=project.human_review_statement,
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
        revision=comment.revision,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        can_delete=comment.can_delete,
        can_report=comment.can_report,
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


def to_course_response(course: CourseData) -> CourseResponse:
    return CourseResponse(
        id=course.id,
        name=course.name,
        code=course.code,
        description=course.description,
        instructor=course.instructor,
        schedule_data=course.schedule_data,
        status=course.status,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


def to_course_list_response(page: CoursePage) -> CourseListResponse:
    return CourseListResponse(
        items=[to_course_response(course) for course in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_resource_ref_response(resource: ResourceRefData | None) -> ResourceRefResponse | None:
    if resource is None:
        return None
    return ResourceRefResponse(id=resource.id, name=resource.name)


def to_plan_response(plan: PlanData) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        title=plan.title,
        description=plan.description,
        status=plan.status,
        start_date=plan.start_date,
        end_date=plan.end_date,
        goal_data=plan.goal_data,
        progress=plan.progress,
        project=to_resource_ref_response(plan.project),
        course=to_resource_ref_response(plan.course),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def to_plan_list_response(page: PlanPage) -> PlanListResponse:
    return PlanListResponse(
        items=[to_plan_response(plan) for plan in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_learning_task_v2_response(task: LearningTaskData) -> LearningTaskResponse:
    return LearningTaskResponse(
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
        plan=to_resource_ref_response(task.plan),
        project=to_resource_ref_response(task.project),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def to_learning_task_list_response(page: LearningTaskPage) -> LearningTaskListResponse:
    return LearningTaskListResponse(
        items=[to_learning_task_v2_response(task) for task in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_learning_record_v2_response(record: RecordData) -> LearningRecordV2Response:
    return LearningRecordV2Response(
        id=record.id,
        title=record.title,
        content=record.content,
        record_type=record.record_type,
        duration_minutes=record.duration_minutes,
        occurred_at=record.occurred_at,
        project=to_resource_ref_response(record.project),
        course=to_resource_ref_response(record.course),
        task=to_resource_ref_response(record.task),
        record_metadata=record.record_metadata,
        created_at=record.created_at,
    )


def to_learning_record_list_v2_response(
    page: RecordPage,
) -> LearningRecordListV2Response:
    return LearningRecordListV2Response(
        items=[to_learning_record_v2_response(record) for record in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_workflow_response(workflow: WorkflowData) -> WorkflowResponse:
    return WorkflowResponse(
        id=workflow.id,
        project=WorkflowProjectResponse(
            id=workflow.project.id,
            name=workflow.project.name,
        ),
        name=workflow.name,
        description=workflow.description,
        status=workflow.status,
        version=workflow.version,
        node_count=workflow.node_count,
        edge_count=workflow.edge_count,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


def to_workflow_list_response(page: WorkflowPage) -> WorkflowListResponse:
    return WorkflowListResponse(
        items=[to_workflow_response(workflow) for workflow in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def to_workflow_node_response(node: WorkflowNodeData) -> WorkflowNodeResponse:
    return WorkflowNodeResponse(
        id=node.id,
        workflow_id=node.workflow_id,
        node_key=node.node_key,
        node_type=node.node_type,
        name=node.name,
        position_x=node.position_x,
        position_y=node.position_y,
        config=node.config,
        status=node.status,
        context_version=node.context_version,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def to_workflow_node_list_response(
    nodes: list[WorkflowNodeData],
) -> WorkflowNodeListResponse:
    return WorkflowNodeListResponse(
        items=[to_workflow_node_response(node) for node in nodes],
        total=len(nodes),
    )


def to_workflow_edge_response(edge: WorkflowEdgeData) -> WorkflowEdgeResponse:
    return WorkflowEdgeResponse(
        id=edge.id,
        workflow_id=edge.workflow_id,
        source_node_id=edge.source_node_id,
        target_node_id=edge.target_node_id,
        source_node_key=edge.source_node_key,
        target_node_key=edge.target_node_key,
        condition_data=edge.condition_data,
        created_at=edge.created_at,
    )


def to_workflow_edge_list_response(
    edges: list[WorkflowEdgeData],
) -> WorkflowEdgeListResponse:
    return WorkflowEdgeListResponse(
        items=[to_workflow_edge_response(edge) for edge in edges],
        total=len(edges),
    )


def to_workflow_graph_response(graph: WorkflowGraphData) -> WorkflowGraphResponse:
    return WorkflowGraphResponse(
        workflow=to_workflow_response(graph.workflow),
        nodes=[to_workflow_node_response(node) for node in graph.nodes],
        edges=[to_workflow_edge_response(edge) for edge in graph.edges],
    )


def to_workflow_run_response(run: WorkflowRunData) -> WorkflowRunResponse:
    return WorkflowRunResponse(
        id=run.id,
        workflow_id=run.workflow_id,
        status=run.status,
        context_version=run.context_version,
        error=(
            WorkflowRunErrorResponse(code=run.error.code, message=run.error.message)
            if run.error is not None
            else None
        ),
        nodes=[
            WorkflowRunNodeResponse(
                request_id=node.request_id,
                node_id=node.node_id,
                node_key=node.node_key,
                node_type=node.node_type,
                status=node.status,
                result=node.result,
                error=(
                    WorkflowRunErrorResponse(
                        code=node.error.code,
                        message=node.error.message,
                    )
                    if node.error is not None
                    else None
                ),
                prompt_tokens=node.prompt_tokens,
                completion_tokens=node.completion_tokens,
                total_tokens=node.total_tokens,
                latency_ms=node.latency_ms,
                requested_at=node.requested_at,
                finished_at=node.finished_at,
            )
            for node in run.nodes
        ],
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
    )


def to_workflow_run_list_response(page: WorkflowRunPage) -> WorkflowRunListResponse:
    return WorkflowRunListResponse(
        items=[to_workflow_run_response(run) for run in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )
