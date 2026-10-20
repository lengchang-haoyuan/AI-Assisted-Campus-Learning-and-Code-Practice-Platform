"""S04 离线 PySpark 入口；只消费固定 ODS，不连接业务数据库。"""

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from pyspark.sql import SparkSession, functions as F, types as T

from analytics.snapshot_files import read_snapshot, write_json
from analytics.spark_quality import normalize, relationship_errors, source_definitions

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "开发相关文档/阶段报告/AI大数据改造/V2"


class QualityFailure(ValueError):
    pass


def load_input(path):
    path = Path(path)
    if path.is_dir():
        return read_snapshot(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if path.name != "input.json" or "tables" not in data:
        raise ValueError("explicit_snapshot_or_fixed_fixture_required")
    manifest = dict(data["manifest"], snapshot_id=f"fixture-{path.parent.name}")
    if data.get("scope") == "offline_multi_subject":
        manifest.update(owner_user_id=None, scope="offline_multi_subject", subject_coverage=data["subjects"])
    manifest["fixture"] = True
    return manifest, data["tables"]


def make_session():
    return (SparkSession.builder.appName("ScholarHub-S04").master("local[2]")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.shuffle.partitions", "8")
            .config("spark.ui.enabled", "false")
            .config("spark.ui.showConsoleProgress", "false").getOrCreate())


def percentage(n, d, value):
    return {"numerator": n, "denominator": d, "percent": str(value) if value is not None else None,
            "display": "无样本" if value is None else str(value.quantize(Decimal(".1"), rounding=ROUND_HALF_UP)) + "%"}


def collect_ads(spark, stats, manifest):
    # 所有聚合和比例均由 SQL 完成，Python 只组织接口无关的离线文件形状。
    answers = {}
    records = {r.owner_user_id: r.asDict() for r in spark.table("ads_records").collect()}
    tasks = {r.owner_user_id: r.asDict() for r in spark.table("ads_tasks").collect()}
    topics = {r.owner_user_id: r.asDict() for r in spark.table("ads_topic").collect()}
    daily = [r.asDict() for r in spark.table("ads_daily").orderBy("owner_user_id", "date").collect()]
    out_time = {r.user_id: r.n for r in spark.sql("SELECT user_id,count(*) n FROM v_learning_records "
                f"WHERE occurred_at>=TIMESTAMP '{manifest['source_cutoff']}' GROUP BY user_id").collect()}
    record_stats = next(s for s in stats if s["table_name"] == "learning_records")
    for owner, r in records.items():
        r.pop("owner_user_id")
        if manifest.get("owner_user_id") is not None:
            r.update(raw_rows=record_stats["raw_rows"], exact_duplicates=record_stats["exact_duplicates"])
        t, c = tasks[owner], topics[owner]
        t.pop("owner_user_id"); c.pop("owner_user_id")
        eligible = t.pop("eligible_to_complete_plan")
        t["completion_rate"] = percentage(t["completed"], t["total"], t.pop("percent"))
        for label, numerator, denominator in [
            ("revised", "revised_count", "cohort_count"), ("confirmation", "confirmed_count", "cohort_count"),
            ("revised_confirmation", "revised_confirmed_count", "revised_count")]:
            c[label+"_rate"] = percentage(c[numerator], c[denominator], c.pop(label+"_percent"))
        c["first_review_histogram"] = {b: c.pop(f"bucket_{i}") for i, b in enumerate(("[0,60)", "[60,240)", "[240,1440)", "[1440,+inf)"))}
        c["first_review_wait_sum_minutes"] = float(c["first_review_wait_sum_minutes"])
        c["first_review_wait_mean_minutes"] = str(c["first_review_wait_mean_minutes"]) if c["first_review_wait_mean_minutes"] is not None else None
        answers[str(owner)] = {"owner_user_id": owner, "new_batch_required": True,
            "eligible_to_complete_plan": eligible, "records": r, "tasks": t, "topic": c,
            "daily": [{k: v for k, v in row.items() if k != "owner_user_id"} for row in daily if row["owner_user_id"] == owner],
            "quality": {"outside_observation_time": out_time.get(owner, 0)}}
    return answers


def evidence_conclusions(answers, snapshot_id):
    conclusions = []
    for owner, a in answers.items():
        topic, records, tasks = a["topic"], a["records"], a["tasks"]
        for rule, condition, n, d, meaning, ref in [
            ("revision_observed", "revised_count>0", topic["revised_count"], topic["cohort_count"], "群组存在修订，不能推断修订改善能力", "dwd/cohort_facts"),
            ("first_pass_counterexample", "first_pass_confirmed_count>0", topic["first_pass_confirmed_count"], topic["cohort_count"], "存在首次通过，修订不是确认的必经步骤", "dwd/cohort_facts"),
            ("pending_review", "pending_latest_count>0", topic["pending_latest_count"], topic["cohort_count"], "最新版本仍待评，等待不补零", "dwd/cohort_facts"),
            ("unknown_duration", "missing_duration_count>0", records["missing_duration_count"], records["valid_unique_rows"], "部分记录时长未知，已知分钟仅反映已记录覆盖", "dwd/record_facts"),
            ("no_tasks", "task_total=0", int(tasks["total"] == 0), tasks["total"], "空任务集合没有完成率样本", "dwd/task_facts"),
        ]:
            conclusions.append({"owner_user_id": int(owner), "snapshot_id": snapshot_id, "rule_id": rule,
                                "condition": condition, "triggered": n > 0, "numerator": n, "denominator": d,
                                "dates": [row["date"] for row in a["daily"]], "evidence_ref": ref, "interpretation": meaning})
    return conclusions


def run_job(spark, input_path, output_root, job_id, rule_version="quality-1.0", fail_at=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", job_id):
        raise ValueError("invalid_job_id")
    output_root = Path(output_root)
    final = output_root / "jobs" / job_id
    if final.exists():
        raise FileExistsError("completed_job_exists")
    if rule_version != "quality-1.0":
        raise ValueError("unapproved_rule_version")
    started, tick = datetime.now(UTC).isoformat(), time.perf_counter()
    manifest, tables = load_input(input_path)
    input_loaded_at = time.perf_counter()
    if manifest["schema_version"] != "scholarhub-source-1.0" or manifest["rule_version"] != rule_version or manifest["metric_version"] != "learning-process-1.0":
        raise ValueError("unsupported_input_version")
    if manifest.get("business_timezone") != "Asia/Shanghai":
        raise ValueError("unsupported_business_timezone")
    if manifest["dataset_kind"] not in ("business", "controlled", "synthetic"):
        raise ValueError("unsupported_dataset_kind")
    if not manifest.get("fixture") and manifest["dataset_kind"] != "synthetic" and (
            type(manifest.get("owner_user_id")) is not int or manifest["owner_user_id"] < 1):
        raise ValueError("owner_required")
    if manifest["dataset_kind"] == "synthetic" and (manifest.get("owner_user_id") is not None or manifest.get("scope") != "offline_multi_subject"):
        raise ValueError("synthetic_scope_invalid")
    pending = output_root / ".incomplete" / f"{job_id}-{uuid4().hex}"
    pending.mkdir(parents=True, exist_ok=False)
    final.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"job_id": job_id, "snapshot_id": manifest["snapshot_id"], "input_batch_id": manifest.get("batch_id"),
                "rule_version": rule_version, "metric_version": manifest["metric_version"], "schema_version": manifest["schema_version"],
                "dataset_kind": manifest["dataset_kind"], "owner_user_id": manifest.get("owner_user_id"),
                "started_at": started, "source_cutoff": manifest["source_cutoff"],
                "period_start": manifest["period_start"], "period_end": manifest["period_end"],
                "business_timezone": manifest["business_timezone"], "input_path": str(input_path),
                "spark_version": spark.version, "python_version": sys.version,
                "master": spark.sparkContext.master, "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
                "driver_memory": spark.sparkContext.getConf().get("spark.driver.memory", "default"),
                "java_version": spark.sparkContext._jvm.java.lang.System.getProperty("java.version"),
                "timezone": spark.conf.get("spark.sql.session.timeZone"), "arguments": sys.argv}
    write_json(pending / "attempt.json", dict(metadata, state="running"))
    frames = {}
    try:
        core = json.loads((V2 / "S03-样本/data-dictionary.json").read_text(encoding="utf-8"))["tables"]
        if set(core) - set(tables):
            raise QualityFailure("missing_source_table")
        definitions = source_definitions(core)
        frames, stats, errors = normalize(spark, tables, definitions)
        if not errors:
            errors = relationship_errors(spark, manifest.get("owner_user_id"))
        for table, field in (("submission_versions", "submitted_at"), ("feedback", "created_at")):
            future = spark.sql(f"SELECT cast(id as string) source_key FROM v_{table} WHERE {field}>=TIMESTAMP '{manifest['source_cutoff']}'").collect()
            errors += [{"table_name": table, "source_key": r.source_key, "reason": "future_teaching_event"} for r in future]
        write_json(pending / "exceptions.json", errors)
        write_json(pending / "quality.json", {"tables": stats, "fatal_errors": len(errors),
                   "reconciled": all(s["raw_rows"] == s["unique_rows"] + s["exact_duplicates"] + s["invalid_rows"] for s in stats),
                   "historical_minutes_rule": "NULL unknown; zero valid; historical nonnegative integer, no API 1440 limit"})
        if errors:
            raise QualityFailure(errors[0]["reason"])
        scope = manifest.get("subject_coverage")
        if manifest.get("owner_user_id") is not None:
            subjects = [manifest["owner_user_id"]]
        elif isinstance(scope, list):
            subjects = scope
        else:
            subjects = sorted({r["user_id"] for r in tables["learning_records"]} | {r["user_id"] for r in tables["daily_tasks"]})
        spark.createDataFrame([(u,) for u in subjects], T.StructType([T.StructField("owner_user_id", T.LongType(), False)])).createOrReplaceTempView("scope")
        tz = ZoneInfo("Asia/Shanghai")
        first, last = datetime.fromisoformat(manifest["period_start"]), datetime.fromisoformat(manifest["period_end"])
        params = {"first": manifest["period_start"], "last": manifest["period_end"], "cutoff": manifest["source_cutoff"],
                  "start_utc": first.replace(tzinfo=tz).astimezone(UTC).isoformat(),
                  "end_utc": (last+timedelta(days=1)).replace(tzinfo=tz).astimezone(UTC).isoformat()}
        sql = (ROOT / "analytics/learning_process.sql").read_text(encoding="utf-8")
        parts = re.split(r"-- @view ([a-z_]+)\n", sql)
        for i in range(1, len(parts), 2):
            name, query = parts[i], parts[i+1].strip().format(**params)
            view = spark.sql(query)
            view.createOrReplaceTempView(name)
            if name in ("record_facts", "task_facts", "cohort_facts"):
                view.persist()
                view.count()
        calculated = time.perf_counter()
        answers = collect_ads(spark, stats, manifest)
        compute_finished = time.perf_counter()
        counts = {}
        def tagged(view):
            return (view.withColumn("snapshot_id", F.lit(manifest["snapshot_id"]))
                    .withColumn("job_id", F.lit(job_id)).withColumn("rule_version", F.lit(rule_version)))
        for name in ("record_facts", "task_facts", "cohort_facts"):
            view = spark.table(name)
            counts[name] = view.count()
            tagged(view).write.mode("errorifexists").parquet(str(pending / "dwd" / name))
        tagged(frames["ai_requests_aux"]).write.mode("errorifexists").parquet(str(pending / "dwd/ai_requests_aux"))
        if fail_at == "after_dwd":
            raise RuntimeError("injected_after_dwd_failure")
        for name in ("ads_records", "ads_tasks", "ads_topic", "ads_daily"):
            tagged(spark.table(name)).write.mode("errorifexists").parquet(str(pending / "ads" / name))
        for owner, answer in answers.items():
            if counts["record_facts"] < answer["records"]["valid_unique_rows"]:
                raise AssertionError("join_cardinality_mismatch")
        if counts["record_facts"] != sum(a["records"]["valid_unique_rows"] for a in answers.values()) or counts["task_facts"] != sum(a["tasks"]["total"] for a in answers.values()) or counts["cohort_facts"] != sum(a["topic"]["cohort_count"] for a in answers.values()):
            raise AssertionError("layer_reconciliation_failed")
        write_json(pending / "ads/answers.json", answers)
        write_json(pending / "ads/conclusions.json", evidence_conclusions(answers, manifest["snapshot_id"]))
        write_json(pending / "lineage.json", {"snapshot_id": manifest["snapshot_id"], "job_id": job_id,
                   "counts": counts, "key_columns": {"record_facts": ["id", "feedback_id"], "task_facts": ["id"], "cohort_facts": ["submission_id", "latest_version_id", "first_feedback_id"]},
                   "no_join_amplification": True, "task_semantics": "current_snapshot_not_historical_state_changes"})
        metadata.update(state="computed", finished_at=datetime.now(UTC).isoformat(),
                        elapsed_seconds=time.perf_counter()-tick, quality_and_dwd_seconds=calculated-tick,
                        input_load_seconds=input_loaded_at-tick,
                        ads_collect_seconds=compute_finished-calculated, output_counts=counts,
                        validation="requires independent acceptance; not database published")
        write_json(pending / "manifest.json", metadata)
        pending.rename(final)
        return final, answers, metadata
    except Exception as error:
        write_json(pending / "failure.json", dict(metadata, state="failed", error_type=type(error).__name__,
                   reason=str(error)[:200] if isinstance(error, (QualityFailure, RuntimeError, AssertionError)) else "job_exception",
                   elapsed_seconds=time.perf_counter()-tick, published=False))
        raise
    finally:
        for name in ("record_facts", "task_facts", "cohort_facts"):
            if spark.catalog.tableExists(name):
                spark.table(name).unpersist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--rule-version", default="quality-1.0")
    args = parser.parse_args()
    spark = make_session()
    spark.sparkContext.setLogLevel("ERROR")
    try:
        path, answers, metadata = run_job(spark, args.input, args.output, args.job_id, args.rule_version)
        print(json.dumps({"output": str(path), "subjects": len(answers), "elapsed_seconds": metadata["elapsed_seconds"]}))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
