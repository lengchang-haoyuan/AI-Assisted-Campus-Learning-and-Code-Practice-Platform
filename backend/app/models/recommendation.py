"""本人明确采纳建议的原子任务来源映射。"""

from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, JSON, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, MYSQL_TABLE_OPTIONS, UTCDateTime


class PracticeRecommendationApplication(Base):
    __tablename__ = "practice_recommendation_applications"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "batch_id", "candidate_key", name="uq_practice_application_candidate"),
        UniqueConstraint("owner_user_id", "request_key", name="uq_practice_application_request"),
        MYSQL_TABLE_OPTIONS,
    )
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    batch_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("analytics_batches.batch_id", ondelete="RESTRICT",
        name="fk_practice_recommendation_applications_batch_id_analyti_3c13"), nullable=False)
    candidate_key: Mapped[str] = mapped_column(String(255, collation="utf8mb4_bin"), nullable=False)
    request_key: Mapped[str] = mapped_column(String(64, collation="utf8mb4_bin"), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    task_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("daily_tasks.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)"))
