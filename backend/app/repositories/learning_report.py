from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.ai import AIRequest, AIResult
from app.models.community import Comment, Favorite, Like, ProjectView
from app.models.enums import (
    AIRequestStatus,
    ProjectStatus,
    RecordType,
    ReportStatus,
    TaskStatus,
    WorkflowRunStatus,
)
from app.models.learning import DailyTask, LearningRecord, LearningReport
from app.models.project import Project
from app.models.workflow import WorkflowRun
from app.repositories.project_progress import project_progress_rows


class LearningReportPersistenceError(Exception):
    """学习报告无法按当前数据库状态保存。"""


class LearningReportAlreadyCompletedError(Exception):
    """同一用户和周期已存在完成报告。"""


class LearningReportInProgressError(Exception):
    """同一用户和周期已有未过期的生成任务。"""


class LearningReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def collect_source(
        self,
        user_id: int,
        *,
        period_start: date,
        period_end: date,
        start_at: datetime,
        end_at: datetime,
        timezone_offset: str,
    ) -> dict[str, Any]:
        local_record_date = func.date(
            func.convert_tz(LearningRecord.occurred_at, "+00:00", timezone_offset)
        )
        record_rows = self._session.execute(
            select(
                LearningRecord.record_type,
                func.count(LearningRecord.id),
                func.coalesce(func.sum(LearningRecord.duration_minutes), 0),
            )
            .where(
                LearningRecord.user_id == user_id,
                LearningRecord.occurred_at >= start_at,
                LearningRecord.occurred_at < end_at,
            )
            .group_by(LearningRecord.record_type)
        )
        by_type = {record_type.value: 0 for record_type in RecordType}
        record_count = 0
        total_minutes = 0
        for record_type, count, minutes in record_rows:
            key = getattr(record_type, "value", str(record_type))
            by_type[key] = int(count)
            record_count += int(count)
            total_minutes += int(minutes)
        active_days = int(
            self._session.scalar(
                select(func.count(distinct(local_record_date))).where(
                    LearningRecord.user_id == user_id,
                    LearningRecord.occurred_at >= start_at,
                    LearningRecord.occurred_at < end_at,
                )
            )
            or 0
        )

        task_total = self._count(
            DailyTask.id,
            DailyTask.user_id == user_id,
            DailyTask.scheduled_date >= period_start,
            DailyTask.scheduled_date <= period_end,
        )
        task_completed = self._count(
            DailyTask.id,
            DailyTask.user_id == user_id,
            DailyTask.scheduled_date >= period_start,
            DailyTask.scheduled_date <= period_end,
            DailyTask.status == TaskStatus.COMPLETED,
        )

        project_status_rows = self._session.execute(
            select(Project.status, func.count(Project.id))
            .where(Project.owner_id == user_id)
            .group_by(Project.status)
        )
        project_by_status = {status.value: 0 for status in ProjectStatus}
        for status, count in project_status_rows:
            project_by_status[getattr(status, "value", str(status))] = int(count)
        project_total = sum(project_by_status.values())
        progress_rows = project_progress_rows()
        average_progress = self._session.scalar(
            select(func.avg(progress_rows.c.progress)).where(progress_rows.c.owner_id == user_id)
        )

        workflow_total = self._count(
            WorkflowRun.id,
            WorkflowRun.started_by_id == user_id,
            WorkflowRun.created_at >= start_at,
            WorkflowRun.created_at < end_at,
        )
        workflow_completed = self._count(
            WorkflowRun.id,
            WorkflowRun.started_by_id == user_id,
            WorkflowRun.created_at >= start_at,
            WorkflowRun.created_at < end_at,
            WorkflowRun.status == WorkflowRunStatus.COMPLETED,
        )
        workflow_failed = self._count(
            WorkflowRun.id,
            WorkflowRun.started_by_id == user_id,
            WorkflowRun.created_at >= start_at,
            WorkflowRun.created_at < end_at,
            WorkflowRun.status == WorkflowRunStatus.FAILED,
        )

        ai_base = (
            AIRequest.user_id == user_id,
            AIRequest.requested_at >= start_at,
            AIRequest.requested_at < end_at,
            AIRequest.request_type != "learning_report",
        )
        ai_request_count = self._count(AIRequest.id, *ai_base)
        ai_completed = self._count(
            AIRequest.id, *ai_base, AIRequest.status == AIRequestStatus.COMPLETED
        )
        ai_failed = self._count(
            AIRequest.id, *ai_base, AIRequest.status == AIRequestStatus.FAILED
        )
        token_row = self._session.execute(
            select(
                func.coalesce(func.sum(AIRequest.prompt_tokens), 0),
                func.coalesce(func.sum(AIRequest.completion_tokens), 0),
            ).where(*ai_base)
        ).one()

        return {
            "period_start": period_start,
            "period_end": period_end,
            "learning": {
                "record_count": record_count,
                "total_minutes": total_minutes,
                "active_days": active_days,
                "by_type": by_type,
            },
            "tasks": {
                "total": task_total,
                "completed": task_completed,
                "completion_rate": self._percentage(task_completed, task_total),
            },
            "projects": {
                "total": project_total,
                "published": self._count(
                    Project.id,
                    Project.owner_id == user_id,
                    Project.is_published.is_(True),
                ),
                "completed": project_by_status[ProjectStatus.COMPLETED.value],
                "average_progress": round(float(average_progress or 0), 1),
                "by_status": project_by_status,
            },
            "workflows": {
                "total_runs": workflow_total,
                "completed_runs": workflow_completed,
                "failed_runs": workflow_failed,
                "success_rate": self._percentage(workflow_completed, workflow_total),
            },
            "ai_usage": {
                "request_count": ai_request_count,
                "completed_count": ai_completed,
                "failed_count": ai_failed,
                "prompt_tokens": int(token_row[0]),
                "completion_tokens": int(token_row[1]),
            },
            "community": {
                "comments": self._count(
                    Comment.id,
                    Comment.user_id == user_id,
                    Comment.created_at >= start_at,
                    Comment.created_at < end_at,
                    Comment.is_deleted.is_(False),
                ),
                "likes": self._count(
                    Like.id,
                    Like.user_id == user_id,
                    Like.created_at >= start_at,
                    Like.created_at < end_at,
                ),
                "favorites": self._count(
                    Favorite.id,
                    Favorite.user_id == user_id,
                    Favorite.created_at >= start_at,
                    Favorite.created_at < end_at,
                ),
                "project_views": self._count(
                    ProjectView.id,
                    ProjectView.user_id == user_id,
                    ProjectView.viewed_at >= start_at,
                    ProjectView.viewed_at < end_at,
                ),
            },
        }

    def prepare_generation(
        self,
        user_id: int,
        *,
        period_start: date,
        period_end: date,
        provider: str,
        model: str,
        input_hash: str,
        source_bytes: int,
        stale_after: timedelta,
    ) -> tuple[LearningReport, AIRequest]:
        now = datetime.now(UTC)
        report = self._session.scalar(
            select(LearningReport)
            .where(
                LearningReport.user_id == user_id,
                LearningReport.period_start == period_start,
                LearningReport.period_end == period_end,
            )
            .with_for_update()
        )
        if report is not None and report.status == ReportStatus.COMPLETED:
            raise LearningReportAlreadyCompletedError
        if (
            report is not None
            and report.status == ReportStatus.PENDING
            and report.updated_at >= now - stale_after
        ):
            raise LearningReportInProgressError
        if report is None:
            report = LearningReport(
                user_id=user_id,
                period_start=period_start,
                period_end=period_end,
                status=ReportStatus.PENDING,
            )
            self._session.add(report)
            self._session.flush()
        else:
            self._fail_prior_running_requests(report.id, now)
            report.status = ReportStatus.PENDING
            report.ai_result_id = None
            report.summary = None
            report.achievements = None
            report.problems = None
            report.suggestions = None
            report.structured_data = None
            report.generated_at = None

        request = AIRequest(
            user_id=user_id,
            project_id=None,
            workflow_run_id=None,
            provider=provider,
            model=model,
            request_type="learning_report",
            status=AIRequestStatus.RUNNING,
            input_hash=input_hash,
            input_summary=(
                f"learning_report {report.id} period {period_start.isoformat()}:{period_end.isoformat()}"
            ),
            request_metadata={
                "learning_report_id": report.id,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "source_bytes": source_bytes,
                "agent_rounds": 1,
            },
        )
        self._session.add(request)
        self._commit_or_raise()
        return self._reload_report(report.id), self._reload_request(request.id)

    def complete_generation(
        self,
        report_id: int,
        request_id: int,
        *,
        result: dict[str, Any],
        content_hash: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        latency_ms: int,
        finish_reason: str | None,
        total_tokens: int | None,
    ) -> LearningReport:
        report = self._required_report(report_id)
        request = self._required_request(request_id)
        ai_result = AIResult(
            request_id=request.id,
            result_type="learning_report",
            structured_result=result,
            text_summary=str(result["summary"]),
            content_hash=content_hash,
        )
        self._session.add(ai_result)
        self._session.flush()
        now = datetime.now(UTC)
        request.status = AIRequestStatus.COMPLETED
        request.prompt_tokens = prompt_tokens
        request.completion_tokens = completion_tokens
        request.latency_ms = latency_ms
        request.finished_at = now
        metadata = dict(request.request_metadata or {})
        metadata.update({"finish_reason": finish_reason, "total_tokens": total_tokens})
        request.request_metadata = metadata
        report.ai_result_id = ai_result.id
        report.status = ReportStatus.COMPLETED
        report.summary = str(result["summary"])
        report.achievements = result["achievement"]
        report.problems = result["problems"]
        report.suggestions = result["suggestions"]
        report.structured_data = result["structured_data"]
        report.generated_at = now
        self._commit_or_raise()
        return self._reload_report(report.id)

    def fail_generation(
        self,
        report_id: int,
        request_id: int,
        *,
        error_code: str,
        error_message: str,
    ) -> LearningReport:
        report = self._required_report(report_id)
        request = self._required_request(request_id)
        now = datetime.now(UTC)
        request.status = AIRequestStatus.FAILED
        request.error_code = error_code
        request.error_message = error_message
        request.finished_at = now
        report.status = ReportStatus.FAILED
        report.ai_result_id = None
        report.summary = "学习报告生成失败，可在服务恢复后重试。"
        report.achievements = None
        report.problems = None
        report.suggestions = None
        report.structured_data = {
            "error": {"code": error_code, "message": error_message}
        }
        report.generated_at = None
        self._commit_or_raise()
        return self._reload_report(report.id)

    def count_for_user(self, user_id: int) -> int:
        return self._count(LearningReport.id, LearningReport.user_id == user_id)

    def list_for_user(
        self, user_id: int, *, offset: int, limit: int
    ) -> list[LearningReport]:
        statement = (
            select(LearningReport)
            .options(joinedload(LearningReport.ai_result))
            .where(LearningReport.user_id == user_id)
            .order_by(LearningReport.period_end.desc(), LearningReport.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def get_for_user(self, report_id: int, user_id: int) -> LearningReport | None:
        return self._session.scalar(
            select(LearningReport)
            .options(joinedload(LearningReport.ai_result))
            .where(LearningReport.id == report_id, LearningReport.user_id == user_id)
            .execution_options(populate_existing=True)
        )

    def _fail_prior_running_requests(self, report_id: int, now: datetime) -> None:
        requests = self._session.scalars(
            select(AIRequest).where(
                AIRequest.request_type == "learning_report",
                AIRequest.input_summary.like(f"learning_report {report_id} period %"),
                AIRequest.status == AIRequestStatus.RUNNING,
            )
        )
        for request in requests:
            request.status = AIRequestStatus.FAILED
            request.error_code = "generation_recovered"
            request.error_message = "学习报告生成进程中断，已允许重试"
            request.finished_at = now

    def _required_report(self, report_id: int) -> LearningReport:
        report = self._session.get(LearningReport, report_id)
        if report is None:
            raise RuntimeError("学习报告记录不存在")
        return report

    def _required_request(self, request_id: int) -> AIRequest:
        request = self._session.get(AIRequest, request_id)
        if request is None:
            raise RuntimeError("学习报告 AI 请求不存在")
        return request

    def _reload_report(self, report_id: int) -> LearningReport:
        report = self._session.scalar(
            select(LearningReport)
            .options(joinedload(LearningReport.ai_result))
            .where(LearningReport.id == report_id)
            .execution_options(populate_existing=True)
        )
        if report is None:
            raise RuntimeError("学习报告保存后无法重新加载")
        return report

    def _reload_request(self, request_id: int) -> AIRequest:
        request = self._session.get(AIRequest, request_id)
        if request is None:
            raise RuntimeError("AI 请求保存后无法重新加载")
        return request

    def _count(self, column: Any, *conditions: Any) -> int:
        return int(self._session.scalar(select(func.count(column)).where(*conditions)) or 0)

    @staticmethod
    def _percentage(part: int, total: int) -> float:
        return round(part * 100 / total, 1) if total else 0.0

    def _commit_or_raise(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise LearningReportPersistenceError from exc
