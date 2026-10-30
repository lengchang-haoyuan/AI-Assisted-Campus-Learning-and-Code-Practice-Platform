"""显式运行一个固定快照并与独立Python完整答案比较；不连接数据库。"""

import argparse
from pathlib import Path

from analytics.practice_answers import calculate_answers
from analytics.snapshot_files import write_json
from analytics.spark_job import load_input, make_session, run_job
from analytics.verify_s04 import compare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    args = parser.parse_args()
    manifest, tables = load_input(args.input)
    expected = calculate_answers(tables, manifest)
    spark = make_session()
    spark.sparkContext.setLogLevel("ERROR")
    try:
        final, actual, metadata = run_job(spark, args.input, args.output, args.job_id, manifest["rule_version"])
        compare(actual, {str(manifest["owner_user_id"]): expected})
        write_json(args.acceptance, {"job_id": args.job_id, "snapshot_id": manifest["snapshot_id"],
            "independent_answers_matched": True, "all_frozen_data_assertions_passed": True,
            "output": str(final), "spark_version": spark.version, "versions": {k: manifest[k] for k in
                ("schema_version", "metric_version", "rule_version")}, "whole_answers_compared": True})
        write_json(args.acceptance.with_name(args.acceptance.stem + "-independent-answers.json"), expected)
        print(f"passed: {args.job_id}; independent full answer matched")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
