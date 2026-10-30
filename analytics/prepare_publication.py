"""离线读取已完成Spark DWD，补齐S01已定的每日发布字段。"""

import argparse
import json
from pathlib import Path

from pyspark.sql import functions as F

from analytics.snapshot_files import write_json
from analytics.spark_job import V2, make_session


def prepare(job_id):
    selected = None
    for index_name, jobs_root, inputs_root, acceptance_name, sources_name in (
        ("S04-S05交接索引.json", "S04-产物/jobs", "S05-发布输入", "S04-数据验收.json", "S03-输入索引.json"),
        ("S06-发布清单.json", "S06-产物/jobs", "S06-发布输入", "S06-数据验收.json", "S06-输入索引.json"),
        ("S10-发布清单.json", "S10-产物/jobs", "S10-发布输入", "S10-数据验收.json", "S10-输入索引.json"),
    ):
        if not (V2 / index_name).exists():
            continue
        index = json.loads((V2/index_name).read_text(encoding="utf-8"))
        for key in ("primary", "boundary"):
            if key in index and index[key]["job_id"] == job_id:
                selected = index[key], jobs_root, inputs_root, acceptance_name, sources_name
    if selected is None:
        raise ValueError("job_not_in_controlled_registry")
    entry, jobs_root, inputs_root, acceptance_name, sources_name = selected
    job = (V2/entry["relative_path"]).resolve()
    if not job.is_relative_to((V2/jobs_root).resolve()) or job.name != job_id:
        raise ValueError("job_outside_controlled_root")
    m = json.loads((job/"manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((job/"quality.json").read_text(encoding="utf-8"))
    acceptance = json.loads((V2/acceptance_name).read_text(encoding="utf-8"))
    if m["state"]!="computed" or m["dataset_kind"]!="controlled" or quality["fatal_errors"] or not quality["reconciled"] or not acceptance["all_frozen_data_assertions_passed"]:
        raise ValueError("job_not_validated")
    if acceptance_name in ("S06-数据验收.json", "S10-数据验收.json") and acceptance.get("jobs", {}).get(job_id, {}).get("independent_answers_matched") is not True:
        raise ValueError("independent_answers_not_matched")
    source_index=json.loads((V2/sources_name).read_text(encoding="utf-8"))
    source=next(s for s in source_index["controlled_snapshots"] if s["snapshot_id"]==m["snapshot_id"])
    sm=json.loads((V2/source["path"]/"manifest.json").read_text(encoding="utf-8"))
    answer=json.loads((job/"ads/answers.json").read_text(encoding="utf-8"))[str(m["owner_user_id"])]
    spark=make_session();spark.sparkContext.setLogLevel("ERROR")
    try:
        facts=spark.read.parquet(str(job/"dwd/record_facts"))
        daily=facts.groupBy("metric_date").agg(F.count("id").alias("records"),F.sum("duration_minutes").alias("known_minutes"),
            F.count("duration_minutes").alias("known_duration_count"),F.sum(F.when(F.col("duration_minutes").isNull(),1).otherwise(0)).alias("missing_duration_count"),
            F.sum(F.when(F.col("duration_minutes")==0,1).otherwise(0)).alias("known_zero_count"),
            *[F.sum(F.when(F.col("source_kind")==kind,1).otherwise(0)).alias(name) for kind,name in
              [("ordinary","ordinary_count"),("trusted_teaching","trusted_teaching_count"),("unverified_claim","unverified_claim_count")]])
        enriched={r.metric_date.isoformat():r.asDict() for r in daily.collect()}
        rows=[]
        for row in answer["daily"]:
            computed=enriched.get(row["date"],{})
            for key in ("records","known_minutes","known_duration_count","missing_duration_count"):
                if row[key]!=(computed.get(key) or 0):
                    raise ValueError("DWD_ADS_daily_mismatch")
            result={"metric_date":row["date"]}
            for key in ("records","known_minutes","known_duration_count","missing_duration_count","completed","cancelled","overdue_unfinished"):
                result[key]=row[key]
            result.update(task_total=row["tasks"],cohort_count=row["cohort"],revised_count=row["revised"],confirmed_count=row["confirmed"])
            result.update({key:computed.get(key,0) for key in ("known_zero_count","ordinary_count","trusted_teaching_count","unverified_claim_count")})
            rows.append(result)
        payload={key:m[key] for key in ("snapshot_id","job_id","owner_user_id","dataset_kind","period_start","period_end","business_timezone","source_cutoff","schema_version","metric_version","rule_version")}
        payload.update(dataset_id=sm["dataset_id"],source_counts={r["table_name"]:r["raw_rows"] for r in quality["tables"]},
                       quality={"fatal_errors":0,"reconciled":True},records_summary=answer["records"],tasks_summary=answer["tasks"],topic_summary=answer["topic"],daily=rows)
        if acceptance_name in ("S06-数据验收.json", "S10-数据验收.json"):
            payload["quality"]["independent_answers_matched"] = True
        if m["schema_version"] == "scholarhub-source-2.0":
            payload["quality"]["practice_cross_clock_creation_observations"] = quality["practice_cross_clock_creation_observations"]
        target=V2/inputs_root/job_id;target.mkdir(parents=True,exist_ok=False)
        write_json(target/"payload.json",payload)
        write_json(target/"preparation.json",{"job_id":job_id,"snapshot_id":m["snapshot_id"],"spark_version":spark.version,
                   "mode":"read_completed_DWD_and_project_approved_fields","DWD_ADS_crosscheck":True,"daily_rows":len(rows),"source_recomputed":False})
        print(json.dumps({"job_id":job_id,"daily_rows":len(rows),"DWD_ADS_crosscheck":True}))
    finally:spark.stop()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--job-id",required=True)
    prepare(parser.parse_args().job_id)
