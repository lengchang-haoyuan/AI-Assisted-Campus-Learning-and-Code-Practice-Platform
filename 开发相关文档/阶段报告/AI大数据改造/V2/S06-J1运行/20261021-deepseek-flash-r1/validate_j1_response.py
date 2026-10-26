"""按冻结的 judge-r2 契约离线检查响应；不执行输入中的代码。"""

import json
import re


ANALYSIS_ARTIFACT_ID = "S06-analysis-b96ea63e-v1"
DIMENSION_IDS = (
    "problem_cohort",
    "numeric_evidence",
    "patterns_counterexamples",
    "conclusion_boundary",
)
STATUSES = ("scored", "abstain", "invalid")


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _same_value(actual: object, expected: object) -> bool:
    # Python 的 True == 1，冻结答案比较必须同时检查类型。
    return type(actual) is type(expected) and actual == expected


def validate_response(
    input_obj: dict, response_obj: dict, expected: dict | None = None
) -> dict:
    """返回结构、身份、引用、校准及专题门槛结果，不回显响应正文。

    expected 可传某一校准 case 行或含 cases 的完整冻结答案文档。
    引用可定位只说明文本存在，不证明其语义正确或分值合理。
    """
    result = {
        "mode": None,
        "status": "invalid",
        "response_status": None,
        "structure_valid": False,
        "binding_valid": False,
        "references_valid": False,
        "reference_checks": [],
        "expected_matches": {},
        "calibration_pass": False,
        "analysis_total": None,
        "analysis_pass": False,
        "errors": [],
    }
    errors = result["errors"]
    if not isinstance(input_obj, dict):
        errors.append("input must be an object")
        return result
    mode = input_obj.get("mode")
    data = input_obj.get("data")
    if mode not in ("analysis", "feedback") or not isinstance(data, dict):
        errors.append("input mode/data is invalid")
        return result
    result["mode"] = mode
    if not isinstance(response_obj, dict):
        errors.append("response must be an object")
        return result

    def fields(value: object, required: set[str], path: str) -> bool:
        if not isinstance(value, dict):
            errors.append(f"{path} must be an object")
            return False
        if set(value) != required:
            errors.append(f"{path} fields do not match the frozen contract")
        return True

    def reason(value: object, path: str) -> None:
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path} must be a nonempty string")

    def score(value: object, maximum: int, path: str, scored: bool) -> None:
        if scored:
            if type(value) is not int or not 0 <= value <= maximum:
                errors.append(f"{path} must be an integer from 0 to {maximum}")
        elif value is not None:
            errors.append(f"{path} must be null when not scored")

    def flag(value: object, path: str, scored: bool) -> None:
        if scored and type(value) is not bool:
            errors.append(f"{path} must be a boolean when scored")
        elif not scored and value is not None:
            errors.append(f"{path} must be null when not scored")

    status = response_obj.get("status")
    valid_status = isinstance(status, str) and status in STATUSES
    if not valid_status:
        errors.append("response.status must be scored, abstain or invalid")
    else:
        result["response_status"] = status
    scored = status == "scored"
    reason(response_obj.get("reason"), "response.reason")
    quote_items = []

    if mode == "analysis":
        fields(
            response_obj,
            {"artifact_id", "status", "dimensions", "causal_or_ability_overclaim", "reason"},
            "response",
        )
        artifact_id = response_obj.get("artifact_id")
        result["binding_valid"] = (
            type(artifact_id) is str
            and artifact_id == ANALYSIS_ARTIFACT_ID
            and artifact_id == data.get("artifact_id")
        )
        dimensions = response_obj.get("dimensions")
        if not isinstance(dimensions, list) or len(dimensions) != 4:
            errors.append("response.dimensions must contain exactly four items")
        dimension_ids = []
        if isinstance(dimensions, list):
            for index, item in enumerate(dimensions):
                path = f"response.dimensions[{index}]"
                if not fields(item, {"dimension_id", "score", "quote", "reason"}, path):
                    continue
                dimension_id = item.get("dimension_id")
                if not isinstance(dimension_id, str) or dimension_id not in DIMENSION_IDS:
                    errors.append(f"{path}.dimension_id is not a frozen dimension")
                else:
                    dimension_ids.append(dimension_id)
                score(item.get("score"), 2, f"{path}.score", scored)
                reason(item.get("reason"), f"{path}.reason")
                if not isinstance(item.get("quote"), str):
                    errors.append(f"{path}.quote must be a string")
                quote_items.append((path + ".quote", item.get("quote")))
            if sorted(dimension_ids) != sorted(DIMENSION_IDS):
                errors.append("response dimensions are duplicated or missing")
        flag(
            response_obj.get("causal_or_ability_overclaim"),
            "response.causal_or_ability_overclaim",
            scored,
        )
        corpus = [data.get("explanation", "")]
        if isinstance(data.get("source_numbers"), dict):
            corpus.append(json.dumps(data["source_numbers"], ensure_ascii=False, indent=2))
    else:
        fields(
            response_obj,
            {"case_id", "status", "criterion_evidence", "actionability_score", "unsupported_claim", "reason"},
            "response",
        )
        case_id = response_obj.get("case_id")
        result["binding_valid"] = (
            type(case_id) is str
            and case_id in ("G01", "G02", "G03")
            and case_id == data.get("case_id")
        )
        criteria = response_obj.get("criterion_evidence")
        if not isinstance(criteria, list) or len(criteria) != 1:
            errors.append("response.criterion_evidence must contain exactly one item")
        if isinstance(criteria, list):
            for index, item in enumerate(criteria):
                path = f"response.criterion_evidence[{index}]"
                if not fields(item, {"criterion_id", "evidence_valid", "quote", "reason"}, path):
                    continue
                if item.get("criterion_id") != "C01":
                    errors.append(f"{path}.criterion_id must be C01")
                flag(item.get("evidence_valid"), f"{path}.evidence_valid", scored)
                reason(item.get("reason"), f"{path}.reason")
                if not isinstance(item.get("quote"), str):
                    errors.append(f"{path}.quote must be a string")
                quote_items.append((path + ".quote", item.get("quote")))
        score(response_obj.get("actionability_score"), 3, "response.actionability_score", scored)
        flag(response_obj.get("unsupported_claim"), "response.unsupported_claim", scored)
        corpus = [data.get("student_code", ""), data.get("candidate_feedback", "")]
        if isinstance(data.get("reference"), dict):
            corpus.append(json.dumps(data["reference"], ensure_ascii=False, indent=2))

    # 先单列结构结果，身份或引用失败仍将有效状态置为 invalid。
    result["structure_valid"] = not errors
    if not result["binding_valid"]:
        errors.append("response identity does not bind to the current frozen input")
    normalized_corpus = [_normalized(text) for text in corpus if isinstance(text, str)]
    for path, quote in quote_items:
        is_string = isinstance(quote, str)
        normalized_quote = _normalized(quote) if is_string else ""
        nonempty = bool(normalized_quote)
        present = nonempty and any(normalized_quote in text for text in normalized_corpus)
        valid = is_string and (present or (not scored and not nonempty))
        result["reference_checks"].append(
            {"path": path, "nonempty": nonempty, "present": present, "valid": valid}
        )
        if not valid:
            errors.append(f"{path} is empty, non-string or absent from the current input")
    result["references_valid"] = bool(quote_items) and all(
        item["valid"] for item in result["reference_checks"]
    )
    if not errors:
        result["status"] = status

    if mode == "feedback" and isinstance(expected, dict):
        case_expected = expected
        if isinstance(expected.get("cases"), list):
            matching = [
                row for row in expected["cases"]
                if isinstance(row, dict) and row.get("calibration_id") == data.get("case_id")
            ]
            case_expected = matching[0] if len(matching) == 1 else {}
        criteria = response_obj.get("criterion_evidence")
        criterion = criteria[0] if isinstance(criteria, list) and len(criteria) == 1 else {}
        if not isinstance(criterion, dict):
            criterion = {}
        actual = {
            "expected_status": status,
            "expected_actionability_score": response_obj.get("actionability_score"),
            "expected_criterion": criterion.get("criterion_id"),
            "expected_evidence_valid": criterion.get("evidence_valid"),
            "expected_unsupported_claim": response_obj.get("unsupported_claim"),
        }
        result["expected_matches"] = {
            key: key in case_expected and _same_value(value, case_expected[key])
            for key, value in actual.items()
        }
        result["expected_matches"]["expected_case_id"] = _same_value(
            data.get("case_id"), case_expected.get("calibration_id")
        )
        result["calibration_pass"] = not errors and all(result["expected_matches"].values())
    elif mode == "analysis" and not errors and scored:
        result["analysis_total"] = sum(item["score"] for item in response_obj["dimensions"])
        result["analysis_pass"] = (
            result["analysis_total"] >= 6
            and response_obj["causal_or_ability_overclaim"] is False
        )
    return result
