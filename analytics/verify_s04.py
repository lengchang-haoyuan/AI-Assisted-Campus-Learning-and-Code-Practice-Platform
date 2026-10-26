"""真实 Spark 验收：冻结样例、独立 Python、规模与任务生命周期。"""

import argparse
import json
import math
import os
import threading
import time
from pathlib import Path

from analytics.fixture_answers import assert_subset, calculate
from analytics.snapshot_files import write_json
from analytics.spark_job import QualityFailure, V2, load_input, make_session, run_job


def compare(actual, expected, path=""):
    for key, value in expected.items():
        target = actual[key]
        name = path+"."+key
        if isinstance(value, dict):
            compare(target, value, name)
        elif isinstance(value, list):
            if len(target) != len(value):
                raise AssertionError(name+" length")
            for a, e in zip(target, value):
                compare(a, e, name)
        elif isinstance(value, float):
            if not math.isclose(target, value, rel_tol=1e-10, abs_tol=1e-10):
                raise AssertionError((name, target, value))
        elif target != value:
            raise AssertionError((name, target, value))


class MemoryProbe:
    def __init__(self):
        self.done = threading.Event()
        self.peak = 0
        self.peak_by_process = {}
        self.samples = 0
        self.thread = threading.Thread(target=self.poll, daemon=True)

    def poll(self):
        while not self.done.is_set():
            pending, pids = [os.getpid()], set()
            while pending:
                pid = pending.pop()
                if pid in pids:
                    continue
                pids.add(pid)
                try:
                    pending += [int(v) for v in Path(f"/proc/{pid}/task/{pid}/children").read_text().split()]
                except (FileNotFoundError, PermissionError):
                    pass
            total = 0
            for pid in pids:
                try:
                    rss = int(Path(f"/proc/{pid}/statm").read_text().split()[1])*os.sysconf("SC_PAGE_SIZE")
                    name = Path(f"/proc/{pid}/comm").read_text().strip()
                    total += rss
                    self.peak_by_process[f"{pid}:{name}"] = max(rss, self.peak_by_process.get(f"{pid}:{name}", 0))
                except (FileNotFoundError, PermissionError):
                    pass
            self.peak = max(self.peak, total)
            self.samples += 1
            self.done.wait(1)

    def start(self):
        self.thread.start()

    def stop(self):
        self.done.set(); self.thread.join()
        return {"sample_seconds": 1, "samples": self.samples, "peak_process_tree_rss_bytes": self.peak,
                "per_process_peak_bytes": self.peak_by_process, "method": "/proc statm; Python driver + descendant JVM/workers; sampled peak, not exact maximum"}


def verify_one(spark, path, root, job_id, expected=None, expected_error=None):
    manifest, tables = load_input(path)
    tick = time.perf_counter()
    try:
        final, actual, metadata = run_job(spark, path, root, job_id)
    except QualityFailure as error:
        if str(error) != expected_error:
            raise
        return {"job_id": job_id, "snapshot_id": manifest["snapshot_id"], "status": "expected_rejection",
                "reason": str(error), "elapsed_seconds": time.perf_counter()-tick}
    if expected_error:
        raise AssertionError("dirty_input_accepted")
    baseline_read_started = time.perf_counter()
    baseline_manifest, baseline_tables = load_input(path)
    baseline_read_seconds = time.perf_counter()-baseline_read_started
    baseline_started = time.perf_counter()
    baseline = {owner: calculate(baseline_tables, dict(baseline_manifest, owner_user_id=int(owner))) for owner in actual}
    baseline_seconds = time.perf_counter()-baseline_started
    for owner, answer in actual.items():
        reference = baseline[owner]
        if manifest.get("owner_user_id") is None:
            reference["records"].pop("raw_rows"); reference["records"].pop("exact_duplicates")
        compare(answer, reference)
    if expected:
        if "assertions" in expected:
            for owner, assertions in expected["assertions"].items():
                assert_subset(actual[owner], assertions)
        else:
            assert_subset(next(iter(actual.values())), expected)
    acceptance = {"job_id": job_id, "snapshot_id": manifest["snapshot_id"], "state": "validated",
                  "spark_python_all_subjects_equal": True, "frozen_assertions_provided": bool(expected),
                  "frozen_assertions_passed": True if expected else None,
                  "subjects": len(actual), "spark_seconds": metadata["elapsed_seconds"],
                  "python_compute_seconds": baseline_seconds,
                  "python_input_read_seconds": baseline_read_seconds,
                  "comparison": "same files, complete relation/window/NULL rules; Python reference validates relations once per subject; not optimized SQL baseline",
                  "output": str(final)}
    write_json(root / f"{job_id}-baseline.json", baseline)
    write_json(root / f"{job_id}-acceptance.json", acceptance)
    return acceptance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=("small", "scale", "lifecycle"), required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--cases", default="")
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    probe = MemoryProbe(); probe.start()
    whole_started = time.perf_counter()
    spark = make_session(); spark.sparkContext.setLogLevel("ERROR")
    startup_seconds = time.perf_counter()-whole_started
    results = []
    try:
        if args.group == "small":
            choices = set(args.cases.split(",")) if args.cases else None
            for folder in sorted((V2 / "S03-样本/small").iterdir()):
                if not folder.is_dir() or choices is not None and folder.name not in choices:
                    continue
                expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
                if expected.get("kind") in ("publication_policy", "authorization_policy"):
                    continue
                error = expected.get("expected_assertions", {}).get("fatal_error")
                assertions = expected if folder.name == "M01" else expected.get("expected_assertions")
                result = verify_one(spark, folder / "input.json", root, args.tag+"-"+folder.name,
                                    None if error else assertions, error)
                results.append(result)
                write_json(root / f"{args.tag}-{folder.name}-check.json", result)
                print(json.dumps({"case": folder.name, "status": result.get("state", result.get("status"))}), flush=True)
            for name, snapshot, answerfile in [
                ("controlled", "s03-owner3-restored", "baseline-independent-answer.json"),
                ("boundary", "s03-owner4-boundary", "boundary-independent-answer.json")]:
                if choices:
                    continue
                expected = json.loads((V2 / "S03-验证证据" / answerfile).read_text(encoding="utf-8"))
                # 等待小数在独立实现中允许1e-10分钟误差；冻结整数和6位比例精确。
                result = verify_one(spark, V2 / "S03-ODS/snapshots" / snapshot, root, args.tag+"-"+name)
                actual = json.loads((Path(result["output"]) / "ads/answers.json").read_text(encoding="utf-8"))
                compare(next(iter(actual.values())), expected)
                results.append(result)
                print(json.dumps({"case": name, "status": "validated"}), flush=True)
        elif args.group == "scale":
            path = V2 / "S03-样本/snapshots/synthetic-10000-seed-20261020-v1"
            results.append(verify_one(spark, path, root, args.tag+"-scale"))
        else:
            path = V2 / "S03-样本/small/D00/input.json"
            job_id = args.tag+"-retry"
            try:
                run_job(spark, path, root, job_id, fail_at="after_dwd")
            except RuntimeError as error:
                assert str(error) == "injected_after_dwd_failure"
            else:
                raise AssertionError("failure_not_observed")
            assert not (root / "jobs" / job_id).exists()
            attempts = list((root / ".incomplete").glob(job_id+"-*"))
            assert len(attempts) == 1 and (attempts[0] / "failure.json").exists()
            result = verify_one(spark, path, root, job_id)
            final = root / "jobs" / job_id
            before = {p.relative_to(final).as_posix(): p.read_bytes() for p in final.rglob("*") if p.is_file()}
            for rule, target in [("quality-1.0", job_id), ("quality-1.0", job_id), ("quality-1.1", job_id)]:
                try:
                    run_job(spark, path, root, target, rule)
                except FileExistsError:
                    pass
                else:
                    raise AssertionError("completed_overwrite_allowed")
            try:
                run_job(spark, path, root, args.tag+"-new-rule", "quality-1.1")
            except ValueError as error:
                assert str(error) == "unapproved_rule_version"
            else:
                raise AssertionError("unknown_rule_accepted")
            after = {p.relative_to(final).as_posix(): p.read_bytes() for p in final.rglob("*") if p.is_file()}
            assert before == after
            results.append(dict(result, retry_new_attempt=True, failed_dwd_not_published=True,
                                duplicate_job_rejected=True, unknown_version_rejected=True, completed_bytes_unchanged=True))
    finally:
        memory = probe.stop()
        spark.stop()
        write_json(root / f"{args.tag}-{args.group}-summary.json", {"group": args.group,
                   "results": results, "spark_startup_seconds": startup_seconds,
                   "whole_process_seconds": time.perf_counter()-whole_started,
                   "memory": memory, "command": __import__("sys").argv})


if __name__ == "__main__":
    main()
