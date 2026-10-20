from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.analytics import AnalyticsBatch, AnalyticsDailyMetric
from app.models.user import User


class AnalyticsRepository:
    def __init__(self, session: Session):
        self.session = session

    def owner_exists(self, owner):
        return self.session.scalar(select(User.id).where(User.id == owner, User.is_active.is_(True))) is not None

    def reserve(self, values):
        row = AnalyticsBatch(**values, state="prepared")
        self.session.add(row)
        try:
            self.session.commit()
            # CLI使用默认expire_on_commit；读取过期ORM对象会提前建立RR快照。
            # 直接返回已知主键，让下一次取锁成为新事务的首次读取。
            return values["batch_id"]
        except IntegrityError:
            self.session.rollback()
            row = self.session.scalar(select(AnalyticsBatch).where(
                AnalyticsBatch.owner_user_id == values["owner_user_id"],
                AnalyticsBatch.artifact_ref == values["artifact_ref"],
                AnalyticsBatch.metric_version == values["metric_version"],
                AnalyticsBatch.rule_version == values["rule_version"],
            ))
            identity = row.batch_id if row is not None else None
            # 结束冲突恢复查询的RR快照，再锁批次并读取其日汇总。
            # 否则锁读看见completed，而普通日表读取仍停留在prepared之前。
            self.session.commit()
            return identity

    def lock(self, batch_id):
        return self.session.scalar(select(AnalyticsBatch).where(AnalyticsBatch.batch_id == batch_id)
                                   .with_for_update().execution_options(populate_existing=True))

    def get_visible(self, batch_id, owner):
        return self.session.scalar(select(AnalyticsBatch).where(
            AnalyticsBatch.batch_id == batch_id, AnalyticsBatch.owner_user_id == owner,
            AnalyticsBatch.state == "completed").execution_options(populate_existing=True))

    def daily(self, batch_id):
        return list(self.session.scalars(select(AnalyticsDailyMetric).where(
            AnalyticsDailyMetric.batch_id == batch_id).order_by(AnalyticsDailyMetric.metric_date)))

    def list_visible(self, owner, filters):
        where = [AnalyticsBatch.owner_user_id == owner, AnalyticsBatch.state == "completed",
                 AnalyticsBatch.dataset_kind == filters.dataset_kind]
        available = self.session.scalar(select(func.count()).select_from(AnalyticsBatch).where(*where))
        if filters.period_start is not None:
            where += [AnalyticsBatch.period_start >= filters.period_start, AnalyticsBatch.period_end <= filters.period_end]
        total = self.session.scalar(select(func.count()).select_from(AnalyticsBatch).where(*where))
        rows = list(self.session.scalars(select(AnalyticsBatch).where(*where).order_by(
            AnalyticsBatch.source_cutoff.desc(), AnalyticsBatch.batch_id.desc())
            .offset((filters.page-1)*filters.page_size).limit(filters.page_size)))
        return rows, total, available

    def replace_unpublished_daily(self, row, values, daily, before_complete=None):
        if row.state == "completed":
            raise ValueError("completed_batch_immutable")
        for key, value in values.items():
            if key != "batch_id":
                setattr(row, key, value)
        self.session.execute(delete(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id == row.batch_id))
        for i, value in enumerate(daily):
            self.session.add(AnalyticsDailyMetric(batch_id=row.batch_id, **value))
            if i == 0 and before_complete is not None:
                self.session.flush()
                before_complete(row.batch_id)
        self.session.flush()
        actual = self.session.scalar(select(func.count()).select_from(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id == row.batch_id))
        if actual != len(daily):
            raise ValueError("daily_row_count_mismatch")
        row.state = "completed"
        from datetime import UTC
        row.published_at = datetime.now(UTC)
        self.session.commit()

    def fail_unpublished(self, batch_id):
        self.session.rollback()
        row = self.lock(batch_id)
        if row is not None and row.state != "completed":
            row.state = "failed"
            row.quality = {**row.quality, "publish_error_count": 1}
        self.session.commit()
