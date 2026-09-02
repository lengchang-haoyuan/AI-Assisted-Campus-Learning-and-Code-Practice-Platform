from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.ai import AIRequest, AIResult
from app.models.enums import AIRequestStatus
from app.models.project import Project


class AgentPersistenceError(Exception):
    """Agent 调用记录无法按当前数据库约束保存。"""


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_project(self, project_id: int) -> Project | None:
        statement = (
            select(Project)
            .where(Project.id == project_id)
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(statement)

    def create_request(self, request: AIRequest) -> AIRequest:
        self._session.add(request)
        self._commit_or_raise()
        return self._reload_request(request.id)

    def complete_request(
        self,
        request_id: int,
        *,
        result_type: str,
        structured_result: dict[str, Any],
        text_summary: str,
        content_hash: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        latency_ms: int,
        finish_reason: str | None,
        total_tokens: int | None,
    ) -> AIRequest:
        request = self._required_request(request_id)
        request.status = AIRequestStatus.COMPLETED
        request.prompt_tokens = prompt_tokens
        request.completion_tokens = completion_tokens
        request.latency_ms = latency_ms
        request.finished_at = datetime.now(UTC)
        request.error_code = None
        request.error_message = None
        metadata = dict(request.request_metadata or {})
        metadata.update(
            {
                "finish_reason": finish_reason,
                "total_tokens": total_tokens,
            }
        )
        request.request_metadata = metadata
        self._session.add(
            AIResult(
                request_id=request.id,
                result_type=result_type,
                structured_result=structured_result,
                text_summary=text_summary,
                content_hash=content_hash,
            )
        )
        self._commit_or_raise()
        return self._reload_request(request.id)

    def fail_request(
        self,
        request_id: int,
        *,
        error_code: str,
        error_message: str,
    ) -> AIRequest:
        request = self._required_request(request_id)
        request.status = AIRequestStatus.FAILED
        request.error_code = error_code
        request.error_message = error_message
        request.finished_at = datetime.now(UTC)
        self._commit_or_raise()
        return self._reload_request(request.id)

    def get_request_for_user(
        self, request_id: int, user_id: int
    ) -> AIRequest | None:
        statement = (
            select(AIRequest)
            .options(joinedload(AIRequest.result))
            .where(AIRequest.id == request_id, AIRequest.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(statement)

    def _required_request(self, request_id: int) -> AIRequest:
        request = self._session.get(AIRequest, request_id)
        if request is None:
            raise RuntimeError("Agent 运行记录不存在")
        return request

    def _reload_request(self, request_id: int) -> AIRequest:
        statement = (
            select(AIRequest)
            .options(joinedload(AIRequest.result))
            .where(AIRequest.id == request_id)
            .execution_options(populate_existing=True)
        )
        request = self._session.scalar(statement)
        if request is None:
            raise RuntimeError("Agent 运行记录保存后无法重新加载")
        return request

    def _commit_or_raise(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise AgentPersistenceError from exc
