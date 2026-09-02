import asyncio
from datetime import UTC, datetime, timedelta, timezone
import json
from secrets import token_hex

from sqlalchemy import delete, select

from app.agents.learning_report import LearningReportAgent
from app.ai.client import AIClient
from app.ai.provider import (
    AICompletionRequest,
    AIProvider,
    AIProviderResult,
    AIUsage,
)
from app.core.config import get_security_settings
from app.core.database import get_session_factory
from app.core.security import SecurityService
from app.models.ai import AIRequest
from app.models.community import Comment, Favorite, Like, ProjectView
from app.models.enums import (
    AIRequestStatus,
    ProjectDifficulty,
    ProjectStatus,
    RecordType,
    ReportStatus,
    TaskPriority,
    TaskStatus,
    WorkflowRunStatus,
    WorkflowStatus,
)
from app.models.learning import DailyTask, LearningRecord, LearningReport
from app.models.project import Project
from app.models.user import User
from app.models.workflow import Workflow, WorkflowRun
from app.repositories.learning_report import LearningReportRepository
from app.repositories.statistics import StatisticsRepository
from app.services.learning_report import LearningReportService
from app.services.statistics import StatisticsService


class ReportProvider(AIProvider):
    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request_data: AICompletionRequest) -> AIProviderResult:
        result = {
            "result_type": "learning_report",
            "summary": "本周期完成了可验证的学习、任务和项目实践。",
            "achievement": ["累计学习 120 分钟", "完成 1 项任务"],
            "problems": ["Workflow 样本仍较少"],
            "suggestions": ["下一周期保持学习记录并复盘 Workflow"],
            "structured_data": {
                "performance_level": "steady",
                "total_learning_minutes": 120,
                "active_days": 1,
                "task_completion_rate": 100,
                "project_average_progress": 100,
                "workflow_success_rate": 100,
                "ai_request_count": 1,
                "focus_areas": ["项目实践", "Workflow"],
                "recommended_weekly_minutes": 180,
            },
        }
        return AIProviderResult(
            provider="fake",
            model=request_data.model,
            content=json.dumps(result, ensure_ascii=False),
            finish_reason="stop",
            usage=AIUsage(prompt_tokens=100, completion_tokens=80, total_tokens=180),
        )


def create_fixture() -> tuple[list[int], int, datetime]:
    now = datetime.now(UTC)
    suffix = token_hex(4)
    security = SecurityService(get_security_settings())
    session = get_session_factory()()
    try:
        users = [
            User(
                username=f"p14_verify_{suffix}_{index}",
                email=f"p14_verify_{suffix}_{index}@example.invalid",
                password_hash=security.hash_password(token_hex(16)),
            )
            for index in (1, 2)
        ]
        session.add_all(users)
        session.flush()
        primary, visitor = users
        project = Project(
            owner_id=primary.id,
            name=f"P14 verification {suffix}",
            difficulty=ProjectDifficulty.INTERMEDIATE,
            status=ProjectStatus.COMPLETED,
            language="Python",
            framework="FastAPI",
            frontend="Vue 3",
            backend="FastAPI",
            database="MySQL",
            progress=100,
            is_published=True,
            published_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(project)
        session.flush()
        session.add_all(
            [
                ProjectView(project_id=project.id, user_id=primary.id, viewed_at=now),
                ProjectView(project_id=project.id, user_id=visitor.id, viewed_at=now),
                Comment(
                    project_id=project.id,
                    user_id=primary.id,
                    content="P14 verification comment",
                    created_at=now,
                    updated_at=now,
                ),
                Like(project_id=project.id, user_id=primary.id, created_at=now),
                Favorite(project_id=project.id, user_id=primary.id, created_at=now),
                DailyTask(
                    user_id=primary.id,
                    project_id=project.id,
                    title="P14 verification task",
                    priority=TaskPriority.MEDIUM,
                    status=TaskStatus.COMPLETED,
                    scheduled_date=now.astimezone(timezone(timedelta(hours=8))).date(),
                    completed_at=now,
                    created_at=now,
                    updated_at=now,
                ),
                DailyTask(
                    user_id=visitor.id,
                    title="P14 visitor task",
                    priority=TaskPriority.LOW,
                    status=TaskStatus.COMPLETED,
                    scheduled_date=now.astimezone(timezone(timedelta(hours=8))).date(),
                    completed_at=now,
                    created_at=now,
                    updated_at=now,
                ),
                LearningRecord(
                    user_id=primary.id,
                    project_id=project.id,
                    record_type=RecordType.STUDY,
                    title="P14 verification record",
                    duration_minutes=120,
                    occurred_at=now,
                    created_at=now,
                ),
            ]
        )
        workflow = Workflow(
            project_id=project.id,
            name=f"P14 workflow {suffix}",
            status=WorkflowStatus.COMPLETED,
        )
        session.add(workflow)
        session.flush()
        run = WorkflowRun(
            workflow_id=workflow.id,
            started_by_id=primary.id,
            status=WorkflowRunStatus.COMPLETED,
            started_at=now,
            finished_at=now,
            created_at=now,
        )
        session.add(run)
        session.flush()
        session.add(
            AIRequest(
                user_id=primary.id,
                project_id=project.id,
                workflow_run_id=run.id,
                provider="fake",
                model="fake-model",
                request_type="project_analysis",
                status=AIRequestStatus.COMPLETED,
                input_hash="a" * 64,
                prompt_tokens=60,
                completion_tokens=30,
                requested_at=now,
                finished_at=now,
            )
        )
        session.commit()
        return [primary.id, visitor.id], primary.id, now
    finally:
        session.close()


def verify(user_id: int, now: datetime) -> int:
    session = get_session_factory()()
    try:
        statistics = StatisticsService(StatisticsRepository(session))
        today = statistics.get_today(480, now=now)
        if today.visitors < 2 or today.completed_task_users < 2:
            raise AssertionError("今日人数聚合未包含 P14 临时样本")
        if today.community_interactions < 5:
            raise AssertionError("社区互动聚合未包含浏览、评论、点赞和收藏")
        trend = statistics.get_trend(7, 480, now=now)
        if trend.items[-1].visitors < 2 or trend.items[-1].community_interactions < 5:
            raise AssertionError("趋势数据与今日临时样本不一致")
        projects = statistics.get_projects(7, 480, now=now)
        if projects.completion_trend[-1].count < 1:
            raise AssertionError("项目完成趋势未读取 completed_at")
        technologies = statistics.get_technology_stacks(10)
        language = next(item for item in technologies.dimensions if item.key == "language")
        if not any(item.name == "Python" for item in language.items):
            raise AssertionError("技术栈聚合未发现 Python")

        client = AIClient(
            ReportProvider(),
            total_timeout_seconds=2,
            max_retries=0,
            retry_base_delay_seconds=0.1,
            max_retry_delay_seconds=1,
        )
        service = LearningReportService(
            LearningReportRepository(session),
            LearningReportAgent(
                client,
                model="fake-model",
                max_tokens=1200,
                temperature=0.1,
            ),
        )
        local_today = now.astimezone(timezone(timedelta(hours=8))).date()
        report = asyncio.run(
            service.generate(
                user_id,
                period_start=local_today - timedelta(days=6),
                period_end=local_today,
                timezone_offset_minutes=480,
                now=now,
            )
        )
        if report.status != ReportStatus.COMPLETED:
            raise AssertionError("Fake Provider 学习报告未完成")
        persisted = service.get_report(report.id, user_id)
        if persisted.structured_data is None:
            raise AssertionError("学习报告刷新回读缺少 structured_data")
        print(
            "P14 真实 MySQL 验收通过：今日人数、社区互动、7 日趋势、"
            "项目完成、技术栈和 AI 学习报告持久化结果一致。"
        )
        return report.id
    finally:
        session.close()


def cleanup(user_ids: list[int]) -> None:
    session = get_session_factory()()
    try:
        session.execute(delete(LearningReport).where(LearningReport.user_id.in_(user_ids)))
        session.execute(delete(AIRequest).where(AIRequest.user_id.in_(user_ids)))
        session.execute(delete(LearningRecord).where(LearningRecord.user_id.in_(user_ids)))
        session.execute(delete(DailyTask).where(DailyTask.user_id.in_(user_ids)))
        session.execute(delete(Project).where(Project.owner_id.in_(user_ids)))
        session.execute(delete(User).where(User.id.in_(user_ids)))
        session.commit()
    finally:
        session.close()


def main() -> int:
    user_ids: list[int] = []
    try:
        user_ids, primary_user_id, now = create_fixture()
        verify(primary_user_id, now)
    finally:
        if user_ids:
            cleanup(user_ids)
    session = get_session_factory()()
    try:
        leftovers = session.scalar(
            select(User.id).where(User.username.like("p14_verify_%")).limit(1)
        )
    finally:
        session.close()
    if leftovers is not None:
        print("P14 临时数据清理失败。")
        return 1
    print("P14 临时数据已清理。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
