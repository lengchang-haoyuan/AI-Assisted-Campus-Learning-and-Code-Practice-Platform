"""S06 固定快照实验编排；复用 S04 作业和独立标准库答案，不连接数据库。"""

import argparse
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from analytics.snapshot_files import read_snapshot, write_json

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "开发相关文档/阶段报告/AI大数据改造/V2"
SEED = 20261020


class MemoryProbe:
    """Linux /proc 一秒采样；进程树 RSS 含共享页重复计数，非精确峰值。"""

    def __init__(self):
        self.done = threading.Event()
        self.peak = 0
        self.samples = 0
        self.thread = threading.Thread(target=self.poll, daemon=True)

    def poll(self):
        while not self.done.is_set():
            pending, seen, total = [os.getpid()], set(), 0
            while pending:
                pid = pending.pop()
                if pid in seen:
                    continue
                seen.add(pid)
                try:
                    pending.extend(int(v) for v in Path(f"/proc/{pid}/task/{pid}/children").read_text().split())
                    total += int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    continue
            self.peak = max(self.peak, total)
            self.samples += 1
            self.done.wait(1)

    def start(self):
        self.thread.start()

    def stop(self):
        self.done.set()
        self.thread.join()
        return {"sample_seconds": 1, "samples": self.samples,
                "peak_process_tree_rss_bytes": self.peak,
                "method": "/proc statm: Python plus descendants; sampled RSS sum, shared pages may be counted twice"}


def compare(actual, expected, path=""):
    """全主体全字段核对，只有等待分钟的未舍入浮点允许 1e-10 容差。"""
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise AssertionError(f"{path}: fields differ")
        return sum(compare(actual[key], value, f"{path}.{key}") for key, value in expected.items())
    if isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError(f"{path}: length differs")
        return sum(compare(a, b, f"{path}[{i}]") for i, (a, b) in enumerate(zip(actual, expected)))
    if isinstance(expected, float):
        valid = math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10)
    else:
        valid = actual == expected
    if not valid:
        raise AssertionError(f"{path}: {actual!r} != {expected!r}")
    return 1


def expected_totals(answers):
    return {
        "records": sum(v["records"]["valid_unique_rows"] for v in answers.values()),
        "known_minutes": sum(v["records"]["known_minutes"] for v in answers.values()),
        "known_duration_count": sum(v["records"]["known_duration_count"] for v in answers.values()),
        "missing_duration_count": sum(v["records"]["missing_duration_count"] for v in answers.values()),
        "known_zero_count": sum(v["records"]["known_zero_count"] for v in answers.values()),
        "tasks": sum(v["tasks"]["total"] for v in answers.values()),
        "cohort_count": sum(v["topic"]["cohort_count"] for v in answers.values()),
        "confirmed_count": sum(v["topic"]["confirmed_count"] for v in answers.values()),
        "revised_count": sum(v["topic"]["revised_count"] for v in answers.values()),
        "trusted_teaching_count": sum(v["records"]["trusted_teaching_count"] for v in answers.values()),
    }


def prepare(output):
    """将两个档位都放同一 Linux 文件系统，旧的一万输入逐字节复制。"""
    from analytics.prepare_samples import FIXTURE, generate_scale

    output.mkdir(parents=True, exist_ok=True)
    inputs = output / "inputs"
    inputs.mkdir(exist_ok=True)
    target = inputs / "snapshots/synthetic-10000-seed-20261020-v1"
    source = V2 / "S03-样本/snapshots" / target.name
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        shutil.copytree(source, target)
    same = all((target / p.relative_to(source)).read_bytes() == p.read_bytes()
               for p in source.rglob("*") if p.is_file())
    if not same:
        raise AssertionError("existing_10000_input_changed")
    expected = V2 / "S03-样本" / f"{target.name}-expected.json"
    if not (inputs / expected.name).exists():
        shutil.copyfile(expected, inputs / expected.name)
    tenfold = inputs / "snapshots/synthetic-100000-seed-20261020-v1"
    if not tenfold.exists():
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        generate_scale(fixture, inputs, count=100000, seed=SEED)
    manifests = {str(n): read_snapshot(inputs / "snapshots" / f"synthetic-{n}-seed-{SEED}-v1")[0]
                 for n in (10000, 100000)}
    evidence = {"prepared_at": datetime.now(UTC).isoformat(), "seed": SEED,
                "original_10000_bytes_equal": same, "manifests": manifests,
                "python": sys.version, "platform": platform.platform(), "logical_cpus": os.cpu_count(),
                "meminfo": Path("/proc/meminfo").read_text(),
                "disk_available_bytes": shutil.disk_usage(output).free,
                "storage": "both scale snapshots copied/generated on the same Linux filesystem",
                "not_run": ["Spark during preparation", "database", "model", "million scale"]}
    if not (output / "preparation.json").exists():
        write_json(output / "preparation.json", evidence)
    return evidence


def python_round(input_path, round_root, expected_path, compare_path=None):
    from analytics.fixture_answers import calculate

    tick = time.perf_counter()
    manifest, tables = read_snapshot(input_path)
    loaded = time.perf_counter()
    subjects = sorted({r["user_id"] for r in tables["learning_records"]} |
                      {r["user_id"] for r in tables["daily_tasks"]})
    answers = {}
    for owner in subjects:
        answer = calculate(tables, dict(manifest, owner_user_id=owner))
        answer["records"].pop("raw_rows")
        answer["records"].pop("exact_duplicates")
        answers[str(owner)] = answer
    calculated = time.perf_counter()
    totals = expected_totals(answers)
    frozen = json.loads(expected_path.read_text(encoding="utf-8"))
    for key, value in totals.items():
        if frozen[key] != value:
            raise AssertionError((key, frozen[key], value))
    assertions = None
    if compare_path:
        assertions = compare(answers, json.loads(compare_path.read_text(encoding="utf-8")))
    checked = time.perf_counter()
    write_json(round_root / "answers.json", answers)
    finished = time.perf_counter()
    return {"subjects": len(subjects), "input_load_seconds": loaded-tick,
            "compute_seconds": calculated-loaded, "validation_seconds": checked-calculated,
            "output_seconds": finished-checked, "round_total_seconds": finished-tick,
            "totals": totals, "equal_reference_leaf_assertions": assertions,
            "reference_implementation": "unmodified analytics.fixture_answers.calculate for each subject on all same input tables; repeated deduplication/relation checks are included, not optimized SQL"}


def spark_round(spark, input_path, round_root, expected_path):
    from analytics.spark_job import run_job

    tick = time.perf_counter()
    job_id = round_root.name
    final, answers, metadata = run_job(spark, input_path, round_root, job_id)
    completed = time.perf_counter()
    assertions = compare(answers, json.loads(expected_path.read_text(encoding="utf-8")))
    verified = time.perf_counter()
    quality = json.loads((final / "quality.json").read_text(encoding="utf-8"))
    if quality["fatal_errors"] != 0 or not quality["reconciled"]:
        raise AssertionError("quality_failed")
    # S04 内部质量/事实包含读取，其后为 ADS 收集和落盘，边界分开且不重复累计。
    output_seconds = metadata["elapsed_seconds"] - metadata["quality_and_dwd_seconds"] - metadata["ads_collect_seconds"]
    return {"job_id": job_id, "snapshot_id": metadata["snapshot_id"], "subjects": len(answers),
            "input_load_seconds": metadata["input_load_seconds"],
            "compute_seconds": metadata["quality_and_dwd_seconds"]-metadata["input_load_seconds"]+metadata["ads_collect_seconds"],
            "quality_and_dwd_seconds": metadata["quality_and_dwd_seconds"],
            "ads_collect_seconds": metadata["ads_collect_seconds"], "output_seconds": output_seconds,
            "job_total_seconds": completed-tick, "validation_seconds": verified-completed,
            "round_total_seconds": verified-tick,
            "equal_reference_leaf_assertions": assertions, "quality_reconciled": True,
            "output": str(final), "totals": expected_totals(answers),
            "spark": {key: metadata[key] for key in ("spark_version", "python_version", "master", "shuffle_partitions", "driver_memory", "java_version", "timezone")}}


def worker(args):
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    startup_seconds = 0.0
    spark = None
    results = []
    probe = MemoryProbe()
    probe.start()
    status, error = "completed", None
    try:
        if args.engine == "spark":
            from analytics.spark_job import make_session

            session_tick = time.perf_counter()
            spark = make_session()
            spark.sparkContext.setLogLevel("ERROR")
            startup_seconds = time.perf_counter()-session_tick
            conf = spark.sparkContext.getConf()
            if (spark.sparkContext.master != "local[2]" or
                    spark.conf.get("spark.sql.shuffle.partitions") != "8" or
                    conf.get("spark.driver.memory", "default") != "2g"):
                raise RuntimeError("benchmark_requires_local2_driver2g_shuffle8")
        rounds = [("warmup", False)] + [(f"hot-{n}", True) for n in (1, 2, 3)] if args.lifecycle == "hot" else [(args.output.name, True)]
        for label, measured in rounds:
            root = args.output / label
            root.mkdir()
            tick = time.perf_counter()
            round_probe = MemoryProbe()
            round_probe.start()
            try:
                if args.engine == "spark":
                    result = spark_round(spark, args.input, root, args.reference)
                else:
                    result = python_round(args.input, root, args.expected, args.reference)
            finally:
                round_memory = round_probe.stop()
            result.update(label=label, measured=measured, lifecycle=args.lifecycle,
                          wall_seconds=time.perf_counter()-tick, memory=round_memory,
                          sample_finished_at=datetime.now(UTC).isoformat())
            write_json(root / "result.json", result)
            results.append(result)
            print(json.dumps({"engine": args.engine, "label": label, "seconds": result["round_total_seconds"]}), flush=True)
    except Exception as failure:
        status, error = "failed", {"type": type(failure).__name__, "message": str(failure)[:500]}
        raise
    finally:
        if spark is not None:
            spark.stop()
        memory = probe.stop()
        write_json(args.output / "worker.json", {"status": status, "error": error, "engine": args.engine,
                   "lifecycle": args.lifecycle, "session_startup_seconds": startup_seconds,
                   "worker_total_seconds": time.perf_counter()-started, "memory": memory,
                   "rounds": results, "argv": sys.argv, "pid": os.getpid(),
                   "python": sys.version, "executable": sys.executable})


def execute(output, scale):
    input_path = output / "inputs/snapshots" / f"synthetic-{scale}-seed-{SEED}-v1"
    expected = output / "inputs" / f"{input_path.name}-expected.json"
    runs = []
    reference = None
    for engine in ("python", "spark"):
        for lifecycle, repetition in (("process_cold", 1), ("process_cold", 2), ("process_cold", 3), ("hot", 1)):
            name = f"n{scale}-{engine}-{lifecycle}-{repetition}"
            target = output / "runs" / name
            target.parent.mkdir(exist_ok=True)
            command = [sys.executable, "-B", "-X", "utf8", "-m", "analytics.benchmark_s06", "worker",
                       "--engine", engine, "--lifecycle", lifecycle, "--input", str(input_path),
                       "--output", str(target), "--expected", str(expected)]
            if reference:
                command.extend(["--reference", str(reference)])
            tick = time.perf_counter()
            log_path = output / "runs" / f"{name}.log"
            with log_path.open("x", encoding="utf-8") as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
            elapsed = time.perf_counter()-tick
            record = {"name": name, "command": command, "exit_code": result.returncode,
                      "external_process_seconds": elapsed, "log": str(log_path)}
            if (target / "worker.json").exists():
                record["worker"] = json.loads((target / "worker.json").read_text(encoding="utf-8"))
            runs.append(record)
            write_json(output / "runs" / f"{name}-process.json", record)
            print(json.dumps({"run": name, "exit_code": result.returncode, "process_seconds": elapsed}), flush=True)
            if result.returncode:
                raise RuntimeError(f"benchmark run failed: {name}; original evidence retained")
            if reference is None:
                reference = target / name / "answers.json"
    summary = {"scale": scale, "snapshot_id": input_path.name, "seed": SEED, "dataset_kind": "synthetic",
               "runs": runs, "comparison": "same JSONL files, complete relation/window/NULL rules; all subjects and fields",
               "cache_method": "no OS cache clearing; no added or cross-round DataFrame caching; unchanged S04 job temporarily persists facts and unpersists in finally",
               "not_claimed": ["disk cold cache", "production users", "cluster", "causal learning benefit", "Spark always faster", "optimized SQL baseline"]}
    medians = {}
    for engine in ("python", "spark"):
        for lifecycle in ("process_cold", "hot"):
            selected = [item for item in runs if item["worker"]["engine"] == engine and item["worker"]["lifecycle"] == lifecycle]
            rounds = [r for item in selected for r in item["worker"]["rounds"] if r["measured"]]
            medians[f"{engine}-{lifecycle}"] = {key: statistics.median(r[key] for r in rounds)
                for key in ("input_load_seconds", "compute_seconds", "output_seconds", "validation_seconds", "round_total_seconds")}
            if lifecycle == "process_cold":
                medians[f"{engine}-{lifecycle}"].update(external_process_seconds=statistics.median(item["external_process_seconds"] for item in selected),
                    session_startup_seconds=statistics.median(item["worker"]["session_startup_seconds"] for item in selected))
    summary["medians"] = medians
    write_json(output / f"n{scale}-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "worker"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scale", type=int, choices=(10000, 100000))
    parser.add_argument("--engine", choices=("python", "spark"))
    parser.add_argument("--lifecycle", choices=("process_cold", "hot"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepared = prepare(args.output)
        print(json.dumps({"prepared": True, "row_counts": {n: m["row_counts"] for n, m in prepared["manifests"].items()}}))
    elif args.mode == "worker":
        if not args.input or not args.expected or not args.engine or not args.lifecycle or args.engine == "spark" and not args.reference:
            parser.error("worker requires input, expected, engine, lifecycle; spark additionally requires reference")
        worker(args)
    else:
        if args.scale is None:
            parser.error("run requires scale")
        execute(args.output, args.scale)


if __name__ == "__main__":
    main()
