"""实践会话持久化；事务由单步用例明确划分，查询不隐式写入。"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError
from app.models.ai import AIRequest
from app.models.practice import PracticeAttempt, PracticeEvent, PracticeSession
from app.models.project import Project


class PracticeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._session.new or self._session.dirty or self._session.deleted:
            raise RuntimeError("实践事务开始前存在未提交修改")
        # 鉴权SELECT可能已开启RR事务；先结束干净只读事务，再按父锁开始当前读。
        if self._session.in_transaction():
            self._session.rollback()
        try:
            with self._session.begin():
                yield
        except IntegrityError as exc:
            raise ConflictError("实践会话请求与现有记录冲突") from exc

    def get_project(
        self, project_id: int, owner_id: int, lock: bool = False
    ) -> Project | None:
        statement = select(Project).where(
            Project.id == project_id, Project.owner_id == owner_id
        )
        if lock:
            statement = statement.with_for_update()
        with self._session.no_autoflush:
            return self._session.scalar(
                statement.execution_options(populate_existing=True)
            )

    def get_session(
        self, session_id: str, owner_id: int, lock: bool = False
    ) -> PracticeSession | None:
        # 调用方在写用例中先锁Project；这里不反向获取父锁。
        statement = select(PracticeSession).where(
            PracticeSession.id == session_id,
            PracticeSession.owner_user_id == owner_id,
        )
        if lock:
            statement = statement.with_for_update()
        with self._session.no_autoflush:
            return self._session.scalar(
                statement.execution_options(populate_existing=True)
            )

    def get_session_project_id(self, session_id: str, owner_id: int) -> int | None:
        with self._session.no_autoflush:
            return self._session.scalar(
                select(PracticeSession.project_id).where(
                    PracticeSession.id == session_id,
                    PracticeSession.owner_user_id == owner_id,
                )
            )

    def list_sessions(
        self, project_id: int, owner_id: int, offset: int, limit: int
    ) -> list[PracticeSession]:
        statement = (
            select(PracticeSession)
            .where(
                PracticeSession.project_id == project_id,
                PracticeSession.owner_user_id == owner_id,
            )
            .order_by(PracticeSession.created_at.desc(), PracticeSession.id.desc())
            .offset(offset)
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        with self._session.no_autoflush:
            return list(self._session.scalars(statement))

    def get_attempt(
        self, session_id: str, attempt_id: str, lock: bool = False
    ) -> PracticeAttempt | None:
        statement = select(PracticeAttempt).where(
            PracticeAttempt.session_id == session_id,
            PracticeAttempt.id == attempt_id,
        )
        if lock:
            statement = statement.with_for_update()
        with self._session.no_autoflush:
            return self._session.scalar(
                statement.execution_options(populate_existing=True)
            )

    def get_attempt_by_request_key(
        self, session_id: str, request_key: str, lock: bool = False
    ) -> PracticeAttempt | None:
        statement = select(PracticeAttempt).where(
            PracticeAttempt.session_id == session_id,
            PracticeAttempt.request_key == request_key,
        )
        if lock:
            statement = statement.with_for_update()
        with self._session.no_autoflush:
            return self._session.scalar(
                statement.execution_options(populate_existing=True)
            )

    def latest_attempt(
        self, session_id: str, step_key: str = "implement", lock: bool = False
    ) -> PracticeAttempt | None:
        if lock:
            # 多行先按ID统一取锁，再在内存选最大attempt_no，避免倒序锁住不同前缀。
            attempts = self.get_attempts_for_update(session_id)
            return max(
                (item for item in attempts if item.step_key == step_key),
                key=lambda item: (item.attempt_no, item.id),
                default=None,
            )
        statement = (
            select(PracticeAttempt)
            .where(
                PracticeAttempt.session_id == session_id,
                PracticeAttempt.step_key == step_key,
            )
            .order_by(PracticeAttempt.attempt_no.desc(), PracticeAttempt.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        with self._session.no_autoflush:
            return self._session.scalar(statement)

    def list_attempts(self, session_id: str) -> list[PracticeAttempt]:
        statement = (
            select(PracticeAttempt)
            .where(PracticeAttempt.session_id == session_id)
            .order_by(PracticeAttempt.attempt_no, PracticeAttempt.id)
            .execution_options(populate_existing=True)
        )
        with self._session.no_autoflush:
            return list(self._session.scalars(statement))

    def get_attempts_for_update(self, session_id: str) -> list[PracticeAttempt]:
        # 调用方已持Project和Session锁；Event查询必须放在本方法之后。
        statement = (
            select(PracticeAttempt)
            .where(PracticeAttempt.session_id == session_id)
            .order_by(PracticeAttempt.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        with self._session.no_autoflush:
            return list(self._session.scalars(statement))

    def get_event(self, session_id: str, event_key: str) -> PracticeEvent | None:
        # 事件在父锁及会话锁之后读取，使用当前读避免RR旧快照漏掉重放。
        statement = (
            select(PracticeEvent)
            .where(
                PracticeEvent.session_id == session_id,
                PracticeEvent.event_key == event_key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        with self._session.no_autoflush:
            return self._session.scalar(statement)

    def get_creation_event(
        self, project_id: int, owner_id: int, event_key: str
    ) -> PracticeEvent | None:
        # 此入口是新事务的首个一致读，调用方已持Project锁；所有创建均先持同父锁。
        # 不在定位旧会话前反向锁Event，随后由调用方按Project→Session加锁。
        statement = (
            select(PracticeEvent)
            .join(PracticeSession, PracticeEvent.session_id == PracticeSession.id)
            .where(
                PracticeSession.project_id == project_id,
                PracticeSession.owner_user_id == owner_id,
                PracticeEvent.event_key == event_key,
            )
            .order_by(PracticeSession.id, PracticeEvent.id)
            .limit(1)
            .execution_options(populate_existing=True)
        )
        with self._session.no_autoflush:
            return self._session.scalar(statement)

    def latest_event(
        self, session_id: str, event_type: str
    ) -> PracticeEvent | None:
        statement = (
            select(PracticeEvent)
            .where(
                PracticeEvent.session_id == session_id,
                PracticeEvent.event_type == event_type,
            )
            .order_by(PracticeEvent.occurred_at.desc(), PracticeEvent.id.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        with self._session.no_autoflush:
            return self._session.scalar(statement)

    def get_request(self, request_id: int, lock: bool = False) -> AIRequest | None:
        statement = (
            select(AIRequest)
            .options(joinedload(AIRequest.result))
            .where(AIRequest.id == request_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        with self._session.no_autoflush:
            return self._session.scalar(statement)

    def add(self, value: object) -> None:
        self._session.add(value)

    def flush(self) -> None:
        self._session.flush()
