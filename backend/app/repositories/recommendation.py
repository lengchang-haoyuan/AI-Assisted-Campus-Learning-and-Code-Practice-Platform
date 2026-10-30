"""锁序为批次→应用/新任务；不获取Practice行锁。"""

from contextlib import contextmanager

from sqlalchemy import select

from app.models.analytics import AnalyticsBatch
from app.models.practice import PracticeAttempt, PracticeEvent, PracticeSession
from app.models.project import Project
from app.models.recommendation import PracticeRecommendationApplication as Application


class RecommendationRepository:
    def __init__(self, session):
        self.session = session

    @contextmanager
    def transaction(self):
        if self.session.new or self.session.dirty or self.session.deleted:
            raise RuntimeError("建议应用前存在未提交修改")
        if self.session.in_transaction():
            self.session.rollback()
        with self.session.begin():
            yield

    def lock_batch(self, owner, batch_id):
        return self.session.scalar(select(AnalyticsBatch).where(
            AnalyticsBatch.batch_id == batch_id, AnalyticsBatch.owner_user_id == owner,
            AnalyticsBatch.state == "completed").with_for_update().execution_options(populate_existing=True))

    def by_request(self, owner, request_key):
        return self.session.scalar(select(Application).where(
            Application.owner_user_id == owner, Application.request_key == request_key)
            .with_for_update().execution_options(populate_existing=True))

    def by_candidate(self, owner, batch_id, key):
        return self.session.scalar(select(Application).where(
            Application.owner_user_id == owner, Application.batch_id == batch_id,
            Application.candidate_key == key).with_for_update())

    def current_source(self, owner, session_id):
        session = self.session.execute(select(
            PracticeSession.id, PracticeSession.project_id, PracticeSession.template_id,
            PracticeSession.template_version, PracticeSession.context_version,
            PracticeSession.revision, PracticeSession.status, PracticeSession.current_step_key,
        ).join(Project, Project.id == PracticeSession.project_id).where(
            PracticeSession.id == session_id, PracticeSession.owner_user_id == owner,
            Project.owner_id == owner)).mappings().one_or_none()
        latest = self.session.execute(select(
            PracticeAttempt.id, PracticeAttempt.attempt_no,
            PracticeAttempt.feedback["ai_static_review"]["operation_id"].as_string().label("operation_id"),
            PracticeAttempt.feedback["ai_static_review"]["ai_request_id"].as_integer().label("ai_request_id"),
        ).where(PracticeAttempt.session_id == session_id)
            .order_by(PracticeAttempt.attempt_no.desc(), PracticeAttempt.id.desc()).limit(1)).mappings().one_or_none()
        return session, latest

    def source_events(self, session_id, ids):
        return list(self.session.execute(select(
            PracticeEvent.id, PracticeEvent.attempt_id, PracticeEvent.event_type,
            PracticeEvent.criterion_id, PracticeEvent.issue_type,
            PracticeEvent.occurred_at,
            PracticeEvent.action_payload["operation_id"].as_string().label("operation_id"),
            PracticeEvent.action_payload["ai_request_id"].as_integer().label("ai_request_id"),
        ).where(PracticeEvent.session_id == session_id, PracticeEvent.id.in_(ids))).mappings())

    def save_application(self, application):
        self.session.add(application)
        self.session.flush()
