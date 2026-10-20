"""ODS 文件协议：未完成目录与可消费快照分开，完成目录不覆盖。"""

import json
import re
from pathlib import Path
from uuid import uuid4


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def begin_snapshot(root, snapshot_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", snapshot_id):
        raise ValueError("invalid_snapshot_id")
    root = Path(root)
    final = root / "snapshots" / snapshot_id
    if final.exists():
        raise FileExistsError("completed_snapshot_exists")
    pending = root / ".incomplete" / f"{snapshot_id}-{uuid4().hex}"
    pending.mkdir(parents=True, exist_ok=False)
    final.parent.mkdir(parents=True, exist_ok=True)
    return pending, final


def publish_snapshot(pending, final, tables, manifest):
    counts, sizes = {}, {}
    for table, rows in tables.items():
        if not re.fullmatch(r"[a-z_]+", table):
            raise ValueError("invalid_table_name")
        path = pending / f"{table}.jsonl"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        counts[table], sizes[table] = len(rows), path.stat().st_size
    manifest = dict(manifest, extraction_status="complete", state="prepared",
                    row_counts=counts, input_bytes=sizes, total_input_bytes=sum(sizes.values()))
    write_json(pending / "manifest.json", manifest)
    if final.exists():
        raise FileExistsError("completed_snapshot_exists")
    # 同一文件系统目录改名；消费者只接受 snapshots 下含完整 manifest 的目录。
    pending.rename(final)
    return manifest


def read_snapshot(path):
    path = Path(path)
    if path.parent.name != "snapshots":
        raise ValueError("not_published_snapshot")
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest["extraction_status"] != "complete" or manifest["snapshot_id"] != path.name:
        raise ValueError("incomplete_snapshot")
    tables = {}
    for table, count in manifest["row_counts"].items():
        if not re.fullmatch(r"[a-z_]+", table):
            raise ValueError("invalid_table_name")
        source = path / f"{table}.jsonl"
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
        if len(rows) != count or source.stat().st_size != manifest["input_bytes"][table]:
            raise ValueError("snapshot_size_mismatch")
        tables[table] = rows
    return manifest, tables
