"""仅离线发布CLI使用；只读API不导入或读取产物文件。"""

import json
from pathlib import Path

from app.core.exceptions import InputError
from app.schemas.analytics import PublicationPayload
from app.services.analytics import validate_payload

V2=Path(__file__).resolve().parents[3]/"开发相关文档/阶段报告/AI大数据改造/V2"


def load_publication(job_id: str) -> PublicationPayload:
    # S06仅增加本轮批准的两份固定任务；API仍不能传入文件路径。
    selected = None
    for index_name, jobs_root, inputs_root, acceptance_name in (
        ("S04-S05交接索引.json", "S04-产物/jobs", "S05-发布输入", "S04-数据验收.json"),
        ("S06-发布清单.json", "S06-产物/jobs", "S06-发布输入", "S06-数据验收.json"),
    ):
        index_path = V2 / index_name
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for key in ("primary", "boundary"):
            entry = index[key]
            if entry["job_id"] == job_id:
                selected = entry, jobs_root, inputs_root, acceptance_name
    if selected is None:
        raise InputError("任务不在受控发布清单，禁止合成或测试向量发布")
    entry, jobs_root, inputs_root, acceptance_name = selected
    job=(V2/entry["relative_path"]).resolve()
    root=(V2/jobs_root).resolve()
    if not job.is_relative_to(root) or job.name!=job_id:
        raise InputError("产物引用不在受控完成目录")
    manifest=json.loads((job/"manifest.json").read_text(encoding="utf-8"))
    quality=json.loads((job/"quality.json").read_text(encoding="utf-8"))
    acceptance=json.loads((V2/acceptance_name).read_text(encoding="utf-8"))
    if manifest["state"]!="computed" or quality["fatal_errors"]!=0 or quality["reconciled"] is not True or acceptance["all_frozen_data_assertions_passed"] is not True:
        raise InputError("离线任务或独立验收未完成")
    if acceptance_name == "S06-数据验收.json" and acceptance.get("jobs", {}).get(job_id, {}).get("independent_answers_matched") is not True:
        raise InputError("本轮任务尚未通过独立答案核对")
    payload=PublicationPayload.model_validate_json((V2/inputs_root/job_id/"payload.json").read_text(encoding="utf-8"))
    for key in ("job_id","snapshot_id","owner_user_id","dataset_kind","period_start","period_end","business_timezone","source_cutoff","schema_version","metric_version","rule_version"):
        actual=payload.model_dump(mode="json")[key]
        if key=="source_cutoff":
            from datetime import datetime
            equal=payload.source_cutoff==datetime.fromisoformat(manifest[key].replace("Z","+00:00"))
        else:equal=actual==manifest[key]
        if not equal:
            raise InputError("发布输入与任务标识或版本不一致")
    if manifest["snapshot_id"].startswith("fixture-") or payload.dataset_kind=="synthetic":
        raise InputError("实验输入禁止本人发布")
    answers=json.loads((job/"ads/answers.json").read_text(encoding="utf-8"))
    if set(answers)!={str(payload.owner_user_id)}:
        raise InputError("任务主体覆盖与归属不一致")
    expected=answers[str(payload.owner_user_id)]
    for field,source in (("records_summary","records"),("tasks_summary","tasks"),("topic_summary","topic")):
        if payload.model_dump(mode="json")[field]!=expected[source]:
            raise InputError("发布汇总不等于已核对ADS")
    if payload.source_counts!={r["table_name"]:r["raw_rows"] for r in quality["tables"]}:
        raise InputError("来源行数不一致")
    if len(payload.daily)!=len(expected["daily"]):
        raise InputError("每日覆盖不一致")
    for row,source in zip(payload.daily,expected["daily"]):
        mapping={"metric_date":"date","task_total":"tasks","cohort_count":"cohort","revised_count":"revised","confirmed_count":"confirmed"}
        for key in ("metric_date","records","known_minutes","known_duration_count","missing_duration_count","task_total","completed","cancelled","overdue_unfinished","cohort_count","revised_count","confirmed_count"):
            if row.model_dump(mode="json")[key]!=source[mapping.get(key,key)]:
                raise InputError("日汇总与ADS不一致")
    validate_payload(payload)
    return payload
