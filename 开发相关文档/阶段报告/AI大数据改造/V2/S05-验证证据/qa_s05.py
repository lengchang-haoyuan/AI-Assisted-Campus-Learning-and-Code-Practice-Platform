"""S05 文件保护、语法、交付链接及敏感输出收尾核对；不连接数据库。"""

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

root = Path.cwd().parent
v2 = root / "开发相关文档/阶段报告/AI大数据改造/V2"
evidence = v2 / "S05-验证证据"
temporary = Path(r"C:/Users/Administrator/AppData/Local/Temp/ScholarHub-S05-20261020")


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_text(path):
    data = path.read_bytes()
    return data.decode("utf-16") if data.startswith((b"\xff\xfe", b"\xfe\xff")) else data.decode("utf-8-sig")


expected_changes = {"backend/app/api/v1/router.py", "backend/app/models/__init__.py", "backend/schema.sql", "backend/tests/test_database_schema.py"}
with ZipFile(temporary / "baseline.zip") as archive:
    names = archive.namelist()
    changed = [name for name in names if not (root / name).is_file() or (root / name).read_bytes() != archive.read(name)]
    assert set(changed) == expected_changes
    schema_prefix = (root / "backend/schema.sql").read_bytes().startswith(archive.read("backend/schema.sql"))
    assert schema_prefix
log_prefix = (temporary / "log-before.bin").read_bytes()
log_unchanged_prefix = (root / "开发相关文档/开发日志/开发操作日志.md").read_bytes().startswith(log_prefix)
assert log_unchanged_prefix
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
assert head == "9320d68bdec47dbc703f85d2e88d2cf8edc5bd2c"
save(evidence / "protection.json", {
    "status": "passed", "head": head, "baseline_files": len(names), "intentionally_changed_existing_files": changed,
    "other_baseline_files_byte_identical": len(names) - len(changed), "missing_files": [],
    "old_schema_exact_prefix_preserved": schema_prefix, "old_log_exact_prefix_preserved": log_unchanged_prefix,
    "old_log_bytes": len(log_prefix), "original_frontend_and_S03_S04_files_preserved": True,
    "baseline_archive_retained_at": str(temporary / "baseline.zip"), "baseline_excludes_credentials_and_env": True,
})

new_python = [
    "analytics/prepare_publication.py", "backend/app/api/v1/analytics.py", "backend/app/models/analytics.py",
    "backend/app/repositories/analytics.py", "backend/app/schemas/analytics.py", "backend/app/services/analytics.py",
    "backend/app/services/analytics_artifacts.py", "backend/scripts/apply_s05_analytics_migration.py",
    "backend/scripts/publish_analytics.py", "backend/tests/test_analytics.py",
]
# 上述为10个Python文件，连同1份新增SQL，共11个新增代码文件。
parse_paths = new_python + [name for name in expected_changes if name.endswith(".py")]
for name in parse_paths:
    ast.parse((root / name).read_text(encoding="utf-8-sig"), filename=name)

documents = [v2 / "S05-完成报告.md", v2 / "S05-发布与接口契约.md"]
links = []
for document in documents:
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
        target = target.strip("<>").split("#")[0]
        if target.startswith(("http:", "https:")) or not target:
            continue
        resolved = (document.parent / target).resolve()
        assert resolved.is_file() or target == "S05-验证证据/final-qa.json", (document.name, target)
        links.append({"document": document.name, "target": target})

json_paths = [v2 / "S05-验收矩阵.json", v2 / "S05-S06交接索引.json"] + list((v2 / "S05-发布输入").rglob("*.json")) + list(evidence.glob("*.json"))
for path in json_paths:
    json.loads(path.read_text(encoding="utf-8"))
handoff = json.loads((v2 / "S05-S06交接索引.json").read_text(encoding="utf-8"))
assert handoff["actual_counts"] == {"batches": 11, "daily_rows": 15}
assert len(handoff["test_fixtures_excluded_from_formal_demo"]) == 9
assert len(json.loads((evidence / "checks.json").read_text(encoding="utf-8"))) == 63

credential_patterns = [
    r"Bearer\s+[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    r"mysql\+pymysql://[^\s\"']+:[^\s\"']+@", r"\bsk-[A-Za-z0-9]{20,}\b",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
]
text_paths = documents + [root / path for path in new_python] + json_paths + list(evidence.glob("*.log")) + list(evidence.glob("*.py"))
credential_hits = []
for path in text_paths:
    content = read_text(path)
    for pattern in credential_patterns:
        if re.search(pattern, content):
            credential_hits.append(str(path.relative_to(root)))
assert credential_hits == [], "sensitive values found; do not print contents"

code_text_paths = [root / path for path in new_python] + [root / "backend/migrations/20261020_s05_offline_analytics.sql"] + documents
trailing_whitespace = [str(path.relative_to(root)) for path in code_text_paths if re.search(r"[ \t]+$", read_text(path), flags=re.M)]
assert trailing_whitespace == []
diff = subprocess.run(["git", "diff", "--check"], cwd=root, capture_output=True, text=True, encoding="utf-8")
(evidence / "diff-check.log").write_text(diff.stdout + diff.stderr, encoding="utf-8")
assert diff.returncode == 0
save(evidence / "final-qa.json", {
    "status": "passed", "source_python_syntax_files": len(parse_paths), "new_python_files": len(new_python),
    "protected_existing_files": len(names), "unrelated_byte_identical": len(names) - len(changed),
    "old_schema_prefix_preserved": schema_prefix, "old_log_prefix_preserved": log_unchanged_prefix,
    "git_diff_check_exit": diff.returncode, "new_code_trailing_whitespace": trailing_whitespace,
    "verified_markdown_links": len(links), "links": links, "parsed_JSON_files": len(json_paths),
    "credential_value_scan_hits": credential_hits, "credential_value_scan_is_not_full_security_audit": True,
    "frontend_build": "not_run_no_frontend_changes", "configured_backend_lint_type_formatter": "none_detected_no_install",
    "database_or_model_calls_in_this_QA": 0,
})
shutil.copyfile(Path(__file__), evidence / "qa_s05.py")
print(json.dumps({"status": "passed", "protected": len(names), "unrelated_unchanged": len(names) - len(changed), "syntax": len(parse_paths), "links": len(links), "JSON": len(json_paths), "diff_exit": diff.returncode, "credential_hits": 0}))
