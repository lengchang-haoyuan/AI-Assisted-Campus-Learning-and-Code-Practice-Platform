import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from math import ceil

from pydantic import ValidationError

from app.agents.base import AgentOutputValidationError
from app.agents.learning_report import LearningReportAgent
from app.agents.learning_report_schemas import (
    LearningReportResult,
    LearningReportSource,
    LearningReportStructuredData,
)
from app.ai.provider import AIClientError, AIFailureCategory
from app.core.exceptions import ConflictError, InputError, ResourceNotFoundError
from app.models.enums import ReportStatus
from app.models.learning import LearningReport
from app.repositories.learning_report import (
    LearningReportAlreadyCompletedError,
    LearningReportInProgressError,
    LearningReportPersistenceError,
    LearningReportRepository,
)

MAX_REPORT_PERIOD_DAYS = 90
REPORT_GENERATION_STALE_AFTER = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class LearningReportErrorData:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class LearningReportData:
    id: int
    period_start: date
    period_end: date
    status: ReportStatus
    summary: str | None
    achievement: list[str]
    problems: list[str]
    suggestions: list[str]
    structured_data: LearningReportStructuredData | None
    error: LearningReportErrorData | None
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class LearningReportPage:
    items: list[LearningReportData]
    total: int
    page: int
    page_size: int
    total_pages: int


class LearningReportService:
    def __init__(
        self,
        repository: LearningReportRepository,
        agent: LearningReportAgent,
    ) -> None:
        self._repository = repository
        self._agent = agent

    async def generate(
        self,
        user_id: int,
        *,
        period_start: date,
        period_end: date,
        timezone_offset_minutes: int,
        now: datetime | None = None,
    ) -> LearningReportData:
        start_at, end_at = self._validate_period(
            period_start,
            period_end,
            timezone_offset_minutes,
            now=now,
        )
        source_payload = self._repository.collect_source(
            user_id,
            period_start=period_start,
            period_end=period_end,
            start_at=start_at,
            end_at=end_at,
            timezone_offset=self._mysql_timezone_offset(timezone_offset_minutes),
        )
        source_payload["timezone_offset_minutes"] = timezone_offset_minutes
        try:
            source = LearningReportSource.model_validate(source_payload)
        except ValidationError as exc:
            raise ConflictError("学习报告聚合数据不符合当前结构") from exc
        canonical_source = json.dumps(
            source.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            report, request = self._repository.prepare_generation(
                user_id,
                period_start=period_start,
                period_end=period_end,
                provider=self._agent.provider_name,
                model=self._agent.model,
                input_hash=self._hash_text(canonical_source),
                source_bytes=len(canonical_source.encode("utf-8")),
                stale_after=REPORT_GENERATION_STALE_AFTER,
            )
        except LearningReportAlreadyCompletedError as exc:
            raise ConflictError("该周期的学习报告已生成") from exc
        except LearningReportInProgressError as exc:
            raise ConflictError("该周期的学习报告正在生成") from exc
        except LearningReportPersistenceError as exc:
            raise ConflictError("学习报告创建与当前数据状态冲突") from exc

        try:
            execution = await self._agent.run(source)
        except asyncio.CancelledError:
            self._repository.fail_generation(
                report.id,
                request.id,
                error_code="cancelled",
                error_message="学习报告生成请求已取消",
            )
            raise
        except AgentOutputValidationError:
            return self._to_data(
                self._repository.fail_generation(
                    report.id,
                    request.id,
                    error_code="agent_output_invalid",
                    error_message="AI 返回的学习报告结构无效，请重试",
                )
            )
        except AIClientError as exc:
            return self._to_data(
                self._repository.fail_generation(
                    report.id,
                    request.id,
                    error_code=exc.category.value,
                    error_message=self._safe_ai_error(exc.category),
                )
            )
        except Exception:
            self._repository.fail_generation(
                report.id,
                request.id,
                error_code="report_internal_error",
                error_message="学习报告内部处理失败，请稍后重试",
            )
            raise

        result = LearningReportResult.model_validate(
            execution.result.model_dump(mode="python")
        )
        result_payload = result.model_dump(mode="json")
        canonical_result = json.dumps(
            result_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            saved = self._repository.complete_generation(
                report.id,
                request.id,
                result=result_payload,
                content_hash=self._hash_text(canonical_result),
                prompt_tokens=execution.completion.usage.prompt_tokens,
                completion_tokens=execution.completion.usage.completion_tokens,
                latency_ms=execution.completion.latency_ms,
                finish_reason=execution.completion.finish_reason,
                total_tokens=execution.completion.usage.total_tokens,
            )
        except LearningReportPersistenceError as exc:
            raise ConflictError("学习报告保存与当前数据状态冲突") from exc
        return self._to_data(saved)

    def list_reports(
        self, user_id: int, *, page: int, page_size: int
    ) -> LearningReportPage:
        total = self._repository.count_for_user(user_id)
        reports = self._repository.list_for_user(
            user_id, offset=(page - 1) * page_size, limit=page_size
        )
        return LearningReportPage(
            items=[self._to_data(report) for report in reports],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_report(self, report_id: int, user_id: int) -> LearningReportData:
        report = self._repository.get_for_user(report_id, user_id)
        if report is None:
            raise ResourceNotFoundError("学习报告不存在")
        return self._to_data(report)

    @staticmethod
    def _validate_period(
        period_start: date,
        period_end: date,
        timezone_offset_minutes: int,
        *,
        now: datetime | None,
    ) -> tuple[datetime, datetime]:
        if period_end < period_start:
            raise InputError("学习报告结束日期不能早于开始日期")
        if (period_end - period_start).days + 1 > MAX_REPORT_PERIOD_DAYS:
            raise InputError(f"学习报告周期不能超过 {MAX_REPORT_PERIOD_DAYS} 天")
        offset_timezone = timezone(timedelta(minutes=timezone_offset_minutes))
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            raise ValueError("学习报告当前时间必须包含时区")
        if period_end > current.astimezone(offset_timezone).date():
            raise InputError("学习报告结束日期不能晚于今天")
        local_start = datetime.combine(period_start, time.min, offset_timezone)
        local_end = datetime.combine(period_end + timedelta(days=1), time.min, offset_timezone)
        return local_start.astimezone(UTC), local_end.astimezone(UTC)

    @staticmethod
    def _mysql_timezone_offset(timezone_offset_minutes: int) -> str:
        sign = "+" if timezone_offset_minutes >= 0 else "-"
        absolute = abs(timezone_offset_minutes)
        return f"{sign}{absolute // 60:02d}:{absolute % 60:02d}"

    @staticmethod
    def _safe_ai_error(category: AIFailureCategory) -> str:
        if category == AIFailureCategory.CONFIGURATION:
            return "AI 服务未配置，请联系管理员配置后重试"
        if category == AIFailureCategory.AUTHENTICATION:
            return "AI 服务凭据不可用，请联系管理员检查配置"
        if category == AIFailureCategory.RATE_LIMIT:
            return "AI 服务当前请求过多，请稍后重试"
        if category in {
            AIFailureCategory.CONNECTION_TIMEOUT,
            AIFailureCategory.RESPONSE_TIMEOUT,
            AIFailureCategory.TOTAL_TIMEOUT,
        }:
            return "AI 服务响应超时，请稍后重试"
        return "AI 服务调用失败，请稍后重试"

    @staticmethod
    def _hash_text(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _to_data(report: LearningReport) -> LearningReportData:
        structured_data = None
        error = None
        if report.status == ReportStatus.COMPLETED:
            try:
                structured_data = LearningReportStructuredData.model_validate(
                    report.structured_data
                )
            except ValidationError as exc:
                raise ConflictError("已保存的学习报告结构无效") from exc
            if report.ai_result is None:
                raise ConflictError("已完成的学习报告缺少 AI 结果")
        elif report.status == ReportStatus.FAILED:
            raw_error = (
                report.structured_data.get("error")
                if isinstance(report.structured_data, dict)
                else None
            )
            if isinstance(raw_error, dict):
                code = raw_error.get("code")
                message = raw_error.get("message")
                if isinstance(code, str) and isinstance(message, str):
                    error = LearningReportErrorData(code=code, message=message)
            if error is None:
                error = LearningReportErrorData(
                    code="report_generation_failed",
                    message="学习报告生成失败，请重试",
                )
        return LearningReportData(
            id=report.id,
            period_start=report.period_start,
            period_end=report.period_end,
            status=report.status,
            summary=report.summary,
            achievement=[str(item) for item in (report.achievements or [])],
            problems=[str(item) for item in (report.problems or [])],
            suggestions=[str(item) for item in (report.suggestions or [])],
            structured_data=structured_data,
            error=error,
            generated_at=report.generated_at,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )
