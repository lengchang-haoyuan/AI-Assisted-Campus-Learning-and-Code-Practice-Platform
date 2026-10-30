"""确定性重复建议提醒；不把模型标签变成代码错误或教学结论。"""

from collections import defaultdict

from app.models.practice import PracticeSessionStatus
from app.schemas.practice_analytics import PracticeSummary, RecommendationCandidate

RULE_VERSION = "B-R1-advisory-1.0"


def build_recommendations(summary: PracticeSummary) -> list[RecommendationCandidate]:
    candidates = []
    for session in summary.sessions:
        if (session.personal_reviewed or session.status in {
            PracticeSessionStatus.COMPLETED, PracticeSessionStatus.CANCELLED,
            PracticeSessionStatus.RUNNING, PracticeSessionStatus.FAILED,
        } or session.current_step_key != "implement" or session.latest_attempt_id is None):
            continue
        groups = defaultdict(dict)
        for ref in session.advice:
            groups[(ref.criterion_id, ref.issue_type)][ref.attempt_id] = ref
        for (criterion, issue), attempts in sorted(groups.items()):
            current = attempts.get(session.latest_attempt_id)
            if (len(attempts) < 2 or current is None
                    or current.operation_id != session.latest_operation_id
                    or current.ai_request_id != session.latest_ai_request_id):
                continue
            refs = sorted(attempts.values(), key=lambda ref: (ref.attempt_no, str(ref.attempt_id)))
            key = "|".join((RULE_VERSION, session.template_id, session.template_version,
                            str(session.session_id), criterion, issue))
            candidates.append(RecommendationCandidate(
                candidate_key=key, rule_version=RULE_VERSION, source="ai_report",
                session_id=session.session_id, project_id=session.project_id,
                template_id=session.template_id, template_version=session.template_version,
                context_version=session.context_version, session_revision=session.revision,
                attempt_id=session.latest_attempt_id, attempt_no=session.latest_attempt_no,
                criterion_id=criterion, issue_type=issue, references=refs,
                title=f"补充 {criterion} 的边界自测",
                explanation=f"同一会话的{len(refs)}次不同提交中，AI重复报告了{issue}线索；"
                            "当前提交尚未由本人审阅结束，可自行选择补一个边界自测。",
            ))
    return candidates


def validate_practice_summary(summary: PracticeSummary) -> None:
    """发布时交叉检查有界专题，防止摘要与来源引用相互矛盾。"""
    sessions = summary.sessions
    checks = {
        "session_count": len(sessions),
        "attempt_count": sum(item.attempt_count for item in sessions),
        "no_submission_count": sum(item.attempt_count == 0 for item in sessions),
        "submission_event_count": sum(item.event_counts.get("attempt_submitted", 0) for item in sessions),
        "personal_end_count": sum(item.event_counts.get("session_completed", 0) for item in sessions),
        "request_count": sum(sum(item.event_counts.get(kind, 0) for kind in
                                 ("session_started", "guidance_requested", "review_started")) for item in sessions),
        "cancel_count": sum(item.event_counts.get("session_cancelled", 0) for item in sessions),
        "resume_count": sum(item.event_counts.get("session_resumed", 0) for item in sessions),
    }
    if any(getattr(summary, key) != value for key, value in checks.items()):
        raise ValueError("实践专题计数与会话不一致")
    if len({item.session_id for item in sessions}) != len(sessions):
        raise ValueError("实践会话引用重复")
    if len(build_recommendations(summary)) > 500:
        raise ValueError("实践候选超出首版有界摘要上限")
    for item in sessions:
        if ((item.latest_attempt_id is None) != (item.latest_attempt_no is None)
                or (item.attempt_count == 0) != (item.latest_attempt_id is None)
                or item.latest_attempt_no is not None and item.latest_attempt_no > item.attempt_count):
            raise ValueError("实践尝试覆盖不一致")
        seen = set()
        for ref in item.advice:
            identity = (ref.attempt_id, ref.criterion_id)
            if identity in seen or ref.attempt_no > item.attempt_count:
                raise ValueError("实践建议重复或尝试引用无效")
            seen.add(identity)
