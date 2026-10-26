"""声明值核对与证据分栏；不导入、编译或执行提交代码。"""

from copy import deepcopy
from typing import Any

from app.practice.templates import get_template

FEEDBACK_SCHEMA_VERSION = "practice-feedback/1.0"


def compare_declared_outputs(declared: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for vector in get_template()["public_output_vectors"]:
        expected = vector["expected"]
        actual = declared.get(vector["test_id"])
        matches = (
            isinstance(actual, dict)
            and set(actual) == set(expected)
            and all(type(actual[key]) is int and actual[key] == value for key, value in expected.items())
        )
        checks.append({"test_id": vector["test_id"], "matched": matches})
    return {
        "source": "server_fixed_value_comparison",
        "matched": all(item["matched"] for item in checks),
        "checks": checks,
        "code_executed": False,
        "meaning": "只核对声明值，不证明代码执行、本人掌握或教师认可",
    }


def initial_evidence(*, attempt_id: str, attempt_no: int, template_version: str,
                     context_version: int, submitted_revision: int,
                     self_statement: bool | None, declared_output: dict) -> dict:
    return {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "binding": {"attempt_id": attempt_id, "attempt_no": attempt_no,
                    "template_version": template_version, "context_version": context_version,
                    "submitted_revision": submitted_revision},
        "self_statement": {"source": "student_declaration", "value": self_statement},
        "submitted_output_match": compare_declared_outputs(declared_output),
        "ai_static_review": None,
        "teacher_confirmation": None,
        "personal_confirmation": None,
    }


def bind_review(evidence: dict, *, result: dict, request_id: int, operation_id: str) -> dict:
    updated = deepcopy(evidence)
    updated["ai_static_review"] = {
        "source": "ai_static_review",
        "ai_request_id": request_id,
        "operation_id": operation_id,
        "review": deepcopy(result),
        "code_executed": False,
    }
    updated.pop("review_error", None)
    return updated
