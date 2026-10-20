from datetime import UTC
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.core.exceptions import ConflictError, InputError, ResourceNotFoundError
from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import BatchDetail, BatchInfo, BatchPage, DailyMetric, PublicationPayload


def validate_payload(payload: PublicationPayload):
    r, t, c = payload.records_summary, payload.tasks_summary, payload.topic_summary
    if payload.quality.get("fatal_errors") != 0 or payload.quality.get("reconciled") is not True:
        raise InputError("离线质量未通过")
    if r.known_duration_count+r.missing_duration_count != r.valid_unique_rows or r.ordinary_count+r.trusted_teaching_count+r.unverified_claim_count != r.valid_unique_rows:
        raise InputError("记录覆盖或来源不一致")
    if r.known_zero_count > r.known_duration_count or (r.known_duration_count == 0 and r.known_minutes != 0):
        raise InputError("未知时长与分钟不一致")
    if t.completed+t.cancelled > t.total or t.overdue_unfinished > t.total-t.completed-t.cancelled:
        raise InputError("任务分母不一致")
    if c.confirmed_count+c.pending_latest_count > c.cohort_count or c.revised_count > c.cohort_count or c.first_pass_confirmed_count+c.revised_confirmed_count != c.confirmed_count or c.revised_confirmed_count > c.revised_count:
        raise InputError("提交群组不一致")
    for rate, n, d in [(t.completion_rate,t.completed,t.total), (c.revised_rate,c.revised_count,c.cohort_count),
                       (c.confirmation_rate,c.confirmed_count,c.cohort_count), (c.revised_confirmation_rate,c.revised_confirmed_count,c.revised_count)]:
        percent = str((Decimal(n)*100/d).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP)) if d else None
        if (rate.numerator,rate.denominator,rate.percent) != (n,d,percent):
            raise InputError("比例与分子分母不一致")
    bins = {"[0,60)","[60,240)","[240,1440)","[1440,+inf)"}
    if set(c.first_review_histogram) != bins or sum(c.first_review_histogram.values()) != c.first_review_covered or c.first_review_covered > c.cohort_count:
        raise InputError("反馈等待覆盖不一致")
    mean = str((Decimal(str(c.first_review_wait_sum_minutes))/c.first_review_covered).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP)) if c.first_review_covered else None
    if mean != c.first_review_wait_mean_minutes:
        raise InputError("反馈等待均值不一致")
    dates = [d.metric_date for d in payload.daily]
    if len(set(dates)) != len(dates) or dates != sorted(dates) or any(not payload.period_start <= d <= payload.period_end for d in dates):
        raise InputError("日期重复或超出批次窗口")
    for d in payload.daily:
        if d.known_duration_count+d.missing_duration_count != d.records or d.ordinary_count+d.trusted_teaching_count+d.unverified_claim_count != d.records or d.known_zero_count>d.known_duration_count or d.completed+d.cancelled>d.task_total or d.revised_count>d.cohort_count or d.confirmed_count>d.cohort_count:
            raise InputError("日汇总内部不一致")
    checks = [("records",r.valid_unique_rows),("known_minutes",r.known_minutes),("known_duration_count",r.known_duration_count),
              ("missing_duration_count",r.missing_duration_count),("known_zero_count",r.known_zero_count),
              ("ordinary_count",r.ordinary_count),("trusted_teaching_count",r.trusted_teaching_count),("unverified_claim_count",r.unverified_claim_count),
              ("task_total",t.total),("completed",t.completed),("cancelled",t.cancelled),("overdue_unfinished",t.overdue_unfinished),
              ("cohort_count",c.cohort_count),("revised_count",c.revised_count),("confirmed_count",c.confirmed_count)]
    if any(sum(getattr(d,key) for d in payload.daily) != total for key,total in checks) or sum(d.records>0 for d in payload.daily)!=r.active_days:
        raise InputError("日汇总与专题总数不一致")


def batch_values(p, batch_id):
    return {"batch_id":batch_id,"owner_user_id":p.owner_user_id,"period_start":p.period_start,"period_end":p.period_end,
            "business_timezone":p.business_timezone,"source_cutoff":p.source_cutoff.astimezone(UTC),"schema_version":p.schema_version,
            "metric_version":p.metric_version,"rule_version":p.rule_version,"dataset_kind":p.dataset_kind,
            "artifact_ref":p.snapshot_id+"/"+p.job_id,
            "input_counts":{"dataset_id":p.dataset_id,"snapshot_id":p.snapshot_id,"job_id":p.job_id,"source_counts":p.source_counts,
                            "records_summary":p.records_summary.model_dump(mode="json"),"tasks_summary":p.tasks_summary.model_dump(mode="json")},
            "quality":p.quality,"topic_summary":p.topic_summary.model_dump(mode="json")}


class AnalyticsService:
    def __init__(self, repository: AnalyticsRepository):
        self.repository = repository

    def publish(self, payload: PublicationPayload, batch_id=None, before_complete=None):
        repo = self.repository
        if not repo.owner_exists(payload.owner_user_id):
            raise InputError("分析归属不存在或已停用")
        values = batch_values(payload, batch_id or str(uuid4()))
        identity = repo.reserve(values)
        if identity is None:
            raise ConflictError("批次编号冲突")
        try:
            row = repo.lock(identity)
            values["batch_id"] = identity
            daily = [d.model_dump() for d in payload.daily]
            if row.state == "completed":
                prior = [DailyMetric.model_validate({k:getattr(d,k) for k in DailyMetric.model_fields}).model_dump() for d in repo.daily(identity)]
                if any(getattr(row,k)!=v for k,v in values.items() if k!="batch_id") or prior!=daily:
                    raise ConflictError("已完成批次内容不同，禁止覆盖")
                repo.session.commit()
                return identity, True
            validate_payload(payload)
            repo.replace_unpublished_daily(row, values, daily, before_complete)
            return identity, False
        except Exception:
            repo.fail_unpublished(identity)
            raise

    @staticmethod
    def info(row):
        return BatchInfo.model_validate({k:getattr(row,k) for k in BatchInfo.model_fields})

    def list_batches(self, owner, filters):
        rows,total,available = self.repository.list_visible(owner, filters)
        reason = None if rows else "page_empty" if total else "no_matching_batch" if available else "no_completed_batch"
        return BatchPage(items=[self.info(row) for row in rows],total=total,page=filters.page,page_size=filters.page_size,empty_reason=reason)

    def get_batch(self, owner, batch_id):
        row = self.repository.get_visible(str(batch_id), owner)
        if row is None:
            raise ResourceNotFoundError("分析批次不存在")
        return BatchDetail(**self.info(row).model_dump(),source={k:row.input_counts[k] for k in ("dataset_id","snapshot_id","job_id")},
                           records_summary=row.input_counts["records_summary"],tasks_summary=row.input_counts["tasks_summary"],
                           topic_summary=row.topic_summary,quality=row.quality,
                           daily=[{k:getattr(d,k) for k in DailyMetric.model_fields} for d in self.repository.daily(row.batch_id)])
