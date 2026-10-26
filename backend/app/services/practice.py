"""固定两步实践：短事务预约，事务外调用，按操作身份提交结果。"""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.agents.base import AgentInputValidationError, AgentOutputValidationError
from app.ai.provider import AIClientError
from app.context.context_schema import CORE_PROJECT_FIELD_MAP
from app.context.project_context import InvalidProjectContextError, ProjectContext
from app.core.exceptions import AgentOutputError, ConflictError, InputError, ResourceNotFoundError
from app.models.ai import AIRequest, AIResult
from app.models.enums import AIRequestStatus
from app.models.practice import PracticeAttempt, PracticeEvent, PracticeSession, PracticeSessionStatus as Status
from app.practice.agent import PRACTICE_CONTEXT_FIELDS, PracticeGuidanceAgent, PracticeGuidanceOutput
from app.practice.evidence import bind_review, initial_evidence
from app.practice.review import PracticeReviewResult, PRACTICE_REVIEW_SCHEMA_VERSION
from app.practice.templates import get_template
from app.repositories.practice import PracticeRepository
from app.services.ai import raise_ai_application_error


class PracticeService:
    def __init__(self, repository: PracticeRepository, agent: PracticeGuidanceAgent,
                 *, provider_name: str, model: str, operation_timeout_seconds: float = 120,
                 review_agent=None, code_guidance_agent=None) -> None:
        self.repo = repository
        self.agent = agent
        self.provider_name = provider_name
        self.model = model
        self.review_agent = review_agent
        self.code_guidance_agent = code_guidance_agent
        self.operation_timeout_seconds = operation_timeout_seconds
        if operation_timeout_seconds <= 0:
            raise ValueError("模型总超时必须为正数")

    def create(self, owner_id: int, project_id: int, template_id: str,
               template_version: str, expected_context_version: int, request_key: str) -> dict:
        if (template_id, template_version) != ("python-learning-csv", "1.0"):
            raise HTTPException(422, "本阶段只支持固定CSV模板1.0")
        payload = {"template_id": template_id, "template_version": template_version,
                   "expected_context_version": expected_context_version}
        with self.repo.transaction():
            project = self.repo.get_project(project_id, owner_id, lock=True)
            if project is None:
                raise ResourceNotFoundError("项目不存在")
            prior = self.repo.get_creation_event(project_id, owner_id, request_key + ":create")
            if prior is not None:
                if prior.action_payload["request"] != payload:
                    raise ConflictError("同一幂等键已用于不同创建载荷")
                item = self.repo.get_session(prior.session_id, owner_id, lock=True)
                return self._detail(item, prior, replayed=True)
            try:
                context = ProjectContext.from_storage(project.context_data)
            except InvalidProjectContextError as exc:
                raise ConflictError("请先初始化有效的项目Context") from exc
            if context.version != expected_context_version:
                raise ConflictError("项目Context版本已变化")
            if any(getattr(project, p) != getattr(context.values, c)
                   for c, p in CORE_PROJECT_FIELD_MAP.items()):
                raise ConflictError("项目Context已过期，请先同步项目字段")
            snapshot = context.to_storage()
            snapshot["values"] = context.values.model_dump(mode="json", include=PRACTICE_CONTEXT_FIELDS)
            # 保留版本/来源元数据；被排除的正文值完全不落实践快照。
            item = PracticeSession(id=str(uuid4()), owner_user_id=owner_id, project_id=project_id,
                template_id=template_id, template_version=template_version,
                context_version=context.version, context_snapshot=snapshot,
                current_step_key="understand", status=Status.READY, revision=1, step_outputs={})
            self.repo.add(item)
            self.repo.flush()
            event = self._event(item, request_key + ":create", "session_created", payload)
            self.repo.flush()
            return self._detail(item, event)

    def list(self, owner_id: int, project_id: int, offset: int = 0, limit: int = 20) -> list[dict]:
        with self.repo.transaction():
            if self.repo.get_project(project_id, owner_id) is None:
                raise ResourceNotFoundError("项目不存在")
            return [self._detail(item) for item in self.repo.list_sessions(
                project_id, owner_id, offset=offset, limit=limit)]

    def get(self, owner_id: int, session_id: str) -> dict:
        with self.repo.transaction():
            item = self.repo.get_session(session_id, owner_id)
            if item is None:
                raise ResourceNotFoundError("实践会话不存在")
            return self._detail(item)

    def submit_attempt(self, owner_id: int, session_id: str, expected_revision: int,
                       step_key: str, request_key: str, code: str,
                       declared_output: dict, self_statement: bool | None) -> dict:
        # 直接Service入口也复用边界校验，载荷原文仅存本人私有attempt，不进事件。
        from app.schemas.practice import PracticeAttemptSubmission
        try:
            validated = PracticeAttemptSubmission.model_validate({
                "expected_revision": expected_revision, "step_key": step_key,
                "request_key": request_key, "code": code,
                "declared_output": declared_output, "self_statement": self_statement})
        except ValidationError as exc:
            raise HTTPException(422, "提交结构、代码或声明输出不符合固定练习要求") from exc
        request_key = validated.request_key
        project_id = self.repo.get_session_project_id(session_id, owner_id)
        with self.repo.transaction():
            item = self._lock(owner_id, session_id, project_id)
            attempts = self.repo.get_attempts_for_update(item.id)
            prior = next((entry for entry in attempts if entry.request_key == request_key), None)
            if prior:
                binding = (prior.feedback or {}).get("binding", {})
                if (prior.step_key != step_key or prior.code_text != code
                    or json.dumps(prior.declared_output, sort_keys=True, ensure_ascii=False) !=
                       json.dumps(declared_output, sort_keys=True, ensure_ascii=False)
                    or prior.self_statement is not self_statement
                    or binding.get("submitted_revision") != expected_revision):
                    raise ConflictError("同一提交幂等键已用于不同载荷")
                data = self._detail(item, replayed=True)
                data["submission"] = self._submission_result(prior, binding["submitted_revision"] + 1, True)
                return data
            if item.revision != expected_revision:
                raise ConflictError("会话版本已变化，请先查询当前尝试")
            if item.current_step_key != "implement" or item.status not in (
                Status.WAITING_SUBMISSION, Status.WAITING_REVISION,
                Status.WAITING_CONFIRMATION, Status.FAILED):
                raise ConflictError("当前状态不能提交实现；请先完成理解或恢复安全等待点")
            attempt_id = str(uuid4())
            attempt_no = max((entry.attempt_no for entry in attempts), default=0) + 1
            attempt = PracticeAttempt(id=attempt_id, session_id=item.id, step_key="implement",
                attempt_no=attempt_no, request_key=request_key, code_text=code,
                declared_output=deepcopy(declared_output), self_statement=self_statement, status="submitted",
                feedback=initial_evidence(attempt_id=attempt_id, attempt_no=attempt_no,
                    template_version=item.template_version, context_version=item.context_version,
                    submitted_revision=expected_revision, self_statement=self_statement,
                    declared_output=declared_output))
            self.repo.add(attempt)
            # 新尝试使依赖旧实现的当前候选待更新，保留理解及历史请求/反馈。
            item.step_outputs = {key: value for key, value in item.step_outputs.items() if key != "implement"}
            item.active_operation_id = item.active_action = item.active_ai_request_id = None
            item.revision += 1
            item.status = self._implement_wait(attempt, item)
            self.repo.flush()
            event = self._event(item, request_key + ":submit", "attempt_submitted",
                {"expected_revision": expected_revision, "step_key": step_key}, attempt=attempt)
            self.repo.flush()
            data = self._detail(item, event)
            data["submission"] = self._submission_result(attempt, item.revision, False)
            return data

    @staticmethod
    def _submission_result(attempt: PracticeAttempt, revision: int, replayed: bool) -> dict:
        return {"attempt_id": attempt.id, "attempt_no": attempt.attempt_no,
                "session_revision": revision, "replayed": replayed}

    async def action(self, owner_id: int, session_id: str, action: str,
                     expected_revision: int, request_key: str, attempt_id: str | None = None) -> dict:
        payload = {"action": action, "expected_revision": expected_revision, "attempt_id": attempt_id}
        event_key = request_key + ":action"
        # 这里只定位父ID；transaction会结束该只读快照，避免等待父锁后仍读到旧请求。
        project_id = self.repo.get_session_project_id(session_id, owner_id)
        with self.repo.transaction():
            item = self._lock(owner_id, session_id, project_id)
            attempts = self.repo.get_attempts_for_update(item.id)
            current = max(attempts, key=lambda entry: entry.attempt_no, default=None)
            prior = self.repo.get_event(item.id, event_key)
            if prior is not None:
                if prior.action_payload["request"] != payload:
                    raise ConflictError("同一幂等键已用于不同动作载荷")
                return self._detail(item, prior, replayed=True)
            if item.revision != expected_revision:
                raise ConflictError("会话版本已变化，请先查询当前状态")
            selected = next((entry for entry in attempts if entry.id == attempt_id), None)
            if attempt_id is not None and selected is None:
                raise ResourceNotFoundError("尝试不存在")
            if selected is not None and selected is not current:
                raise ConflictError("该尝试已被后续提交替代；历史只读，动作须绑定当前尝试")
            if action in ("cancel", "resume", "confirm"):
                prior_review_running = current is not None and current.status == "reviewing"
                self._local_action(item, action, current, selected)
                event = self._event(item, event_key, {
                    "cancel": "session_cancelled", "resume": "session_resumed",
                    "confirm": "step_confirmed"}[action], payload, attempt=current)
                if action == "confirm" and item.status == Status.COMPLETED:
                    self._event(item, event_key + ":completed", "session_completed", payload, attempt=current)
                if prior_review_running and current.status == "review_failed":
                    self._event(item, event_key + ":review_failed", "review_failed", payload, attempt=current)
                self.repo.flush()
                return self._detail(item, event)
            if action not in ("start", "hint", "explain", "review", "continue"):
                raise HTTPException(422, "不支持该实践动作")
            if action == "review" and item.current_step_key != "implement":
                raise HTTPException(422, "静态评审仅用于implement当前尝试")
            self._check_model_action(item, action)
            retry_of = None
            effective_action = action
            kind = "practice_review" if action == "review" else "practice_guidance"
            if item.current_step_key == "implement" and action in ("review", "explain") and selected is None:
                raise ConflictError("请先提交代码，并明确选择当前attempt_id；尚未执行模型")
            if item.current_step_key == "implement" and action == "hint" and current is not None and selected is None:
                raise ConflictError("已有提交时请明确选择当前attempt_id，避免提示脱离提交代码")
            if selected is not None and action in ("hint", "explain"):
                kind = "practice_code_guidance"
            if action == "continue":
                previous = self.repo.get_request(item.active_ai_request_id, lock=True)
                if previous is None or previous.status != AIRequestStatus.FAILED:
                    raise ConflictError("没有可明确重试的失败操作")
                retry_of = {"operation_id": item.active_operation_id, "ai_request_id": previous.id,
                            "action": item.active_action}
                previous_meta = previous.request_metadata or {}
                effective_action = previous_meta.get("effective_action", item.active_action)
                kind = previous.request_type
                if previous_meta.get("attempt_id") != (selected.id if selected else None):
                    raise ConflictError("continue必须明确绑定原失败操作的当前attempt_id")
                if effective_action not in ("start", "hint", "explain", "review"):
                    raise ConflictError("原操作身份无效，不能推测重试内容")
            context = ProjectContext.from_storage(item.context_snapshot)
            if kind == "practice_guidance":
                target_agent = self.agent
                input_data = {"template_id": item.template_id, "template_version": item.template_version,
                              "step_key": item.current_step_key, "action": effective_action}
            else:
                if selected is None or not selected.code_text.strip():
                    raise ConflictError("当前操作需要确切的代码提交")
                if kind == "practice_review" and (selected.feedback or {}).get("ai_static_review"):
                    raise ConflictError("该尝试已有有效评审；修改请新增尝试，不能覆盖原反馈")
                target_agent = self.review_agent if kind == "practice_review" else self.code_guidance_agent
                if target_agent is None:
                    raise HTTPException(503, "实践评审Agent尚未配置")
                input_data = {"template_id": item.template_id, "template_version": item.template_version,
                    "context_version": item.context_version, "attempt_id": selected.id,
                    "attempt_no": selected.attempt_no, "code": selected.code_text,
                    "declared_output": selected.declared_output, "self_statement": selected.self_statement}
                if kind == "practice_code_guidance":
                    input_data["action"] = effective_action
            try:
                target_agent.validate_input(input_data)
            except AgentInputValidationError as exc:
                raise HTTPException(422, "本次代码或材料超出安全输入边界") from exc
            operation_id = str(uuid4())
            now = datetime.now(UTC)
            canonical = json.dumps({"input": input_data, "context": item.context_snapshot},
                                   ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            request = AIRequest(user_id=owner_id, project_id=item.project_id,
                provider=self.provider_name, model=self.model, request_type=kind,
                status=AIRequestStatus.RUNNING, input_hash=sha256(canonical.encode()).hexdigest(),
                input_summary=f"practice {item.id} {item.current_step_key} {action}",
                request_metadata={"session_id": item.id, "operation_id": operation_id,
                    "context_version": item.context_version, "step_key": item.current_step_key,
                    "action": action, "effective_action": effective_action, "max_retries": 0,
                    "attempt_id": selected.id if selected else None,
                    "attempt_no": selected.attempt_no if selected else None,
                    "retry_of": retry_of,
                    "recover_after": (now + timedelta(seconds=self.operation_timeout_seconds + 10)).isoformat()},
                requested_at=now)
            self.repo.add(request)
            self.repo.flush()
            item.status = Status.RUNNING
            item.revision += 1
            item.active_operation_id = operation_id
            item.active_action = effective_action
            item.active_ai_request_id = request.id
            if kind == "practice_review":
                selected.status = "reviewing"
                selected.operation_id = operation_id
                selected.ai_request_id = request.id
                selected.review_schema_version = PRACTICE_REVIEW_SCHEMA_VERSION
            event = self._event(item, event_key,
                "review_started" if kind == "practice_review" else
                "session_started" if action == "start" else "guidance_requested", payload, attempt=selected)
            self.repo.flush()
            operation = {"owner_id": owner_id, "session_id": item.id, "project_id": item.project_id,
                "revision": item.revision, "operation_id": operation_id,
                "request_id": request.id, "step_key": item.current_step_key, "event_key": event_key,
                "kind": kind, "attempt_id": selected.id if selected else None,
                "attempt_no": selected.attempt_no if selected else None}
        # 此处所有数据库事务/锁均已结束。Provider中断不自动重发。
        execution = None
        try:
            async with asyncio.timeout(self.operation_timeout_seconds):
                execution = await target_agent.run(context, input_data)
            result = (PracticeReviewResult if kind == "practice_review" else PracticeGuidanceOutput).model_validate(
                execution.result.model_dump())
            if kind == "practice_review" and (
                result.attempt_id != operation["attempt_id"] or result.attempt_no != operation["attempt_no"]
                or result.template_version != input_data["template_version"]
                or result.context_version != context.version):
                raise AgentOutputValidationError("评审绑定身份不一致")
        except asyncio.CancelledError:
            self._finish(operation, error_code="interrupted")
            raise
        except TimeoutError as exc:
            self._finish(operation, error_code="total_timeout")
            from app.core.exceptions import AIUpstreamTimeoutError
            raise AIUpstreamTimeoutError() from exc
        except (AgentOutputValidationError, ValidationError) as exc:
            self._finish(operation, error_code="agent_output_invalid",
                completion=execution.completion if execution else getattr(exc, "completion", None))
            raise AgentOutputError() from exc
        except AgentInputValidationError as exc:
            self._finish(operation, error_code="agent_input_invalid")
            raise InputError("实践Context超出安全输入范围") from exc
        except AIClientError as exc:
            self._finish(operation, error_code=exc.category.value, observed_usage=exc.observed_usage)
            raise_ai_application_error(exc, "DEEPSEEK_API_KEY")
        except Exception:
            self._finish(operation, error_code="internal_error")
            raise
        return self._finish(operation, result=result.model_dump(mode="json"), completion=execution.completion)

    def _lock(self, owner_id: int, session_id: str, project_id: int | None) -> PracticeSession:
        if project_id is None or self.repo.get_project(project_id, owner_id, lock=True) is None:
            raise ResourceNotFoundError("实践会话不存在")
        item = self.repo.get_session(session_id, owner_id, lock=True)
        if item is None or item.project_id != project_id:
            raise ResourceNotFoundError("实践会话不存在")
        return item

    @staticmethod
    def _check_model_action(item: PracticeSession, action: str) -> None:
        allowed = ((action == "start" and item.status == Status.READY and item.current_step_key == "understand")
            or (action in ("hint", "explain") and item.status in (Status.WAITING_CONFIRMATION, Status.WAITING_SUBMISSION))
            or (action in ("hint", "explain", "review") and item.current_step_key == "implement"
                and item.status in (Status.WAITING_SUBMISSION, Status.WAITING_REVISION, Status.WAITING_CONFIRMATION))
            or (action == "continue" and item.status == Status.FAILED))
        if not allowed:
            raise ConflictError("当前状态不允许该模型动作；先查询状态，失败操作仅可显式continue")

    def _local_action(self, item: PracticeSession, action: str,
                      current: PracticeAttempt | None = None,
                      selected: PracticeAttempt | None = None) -> None:
        if action == "cancel":
            if item.status in (Status.CANCELLED, Status.COMPLETED):
                raise ConflictError("当前状态不能取消")
            if item.status == Status.RUNNING and item.active_ai_request_id:
                request = self.repo.get_request(item.active_ai_request_id, lock=True)
                if request and request.status == AIRequestStatus.RUNNING:
                    request.status = AIRequestStatus.FAILED
                    request.error_code = "cancelled"
                    request.error_message = "本人已取消；外部Provider可能仍返回或计费，不自动重试"
                    request.finished_at = datetime.now(UTC)
                if current and current.status == "reviewing" and current.ai_request_id == item.active_ai_request_id:
                    current.status = "review_failed"
            item.status = Status.CANCELLED
        elif action == "confirm":
            if item.current_step_key == "understand":
                if item.status != Status.WAITING_CONFIRMATION:
                    raise ConflictError("当前没有可确认的理解步骤")
                item.current_step_key = "implement"
                item.status = Status.WAITING_SUBMISSION
            else:
                if (item.status not in (Status.WAITING_SUBMISSION, Status.WAITING_REVISION,
                        Status.WAITING_CONFIRMATION, Status.FAILED)
                    or selected is None or current is not selected or not self._can_complete(current, item)):
                    raise ConflictError("结束须在安全等待点绑定当前版本的有效代码，并由本人明确确认已审阅")
                review_ref = current.feedback.get("ai_static_review")
                evidence = deepcopy(current.feedback)
                evidence["personal_confirmation"] = {
                    "source": "authenticated_practice_owner",
                    "actor_user_id": item.owner_user_id, "confirmed_at": datetime.now(UTC).isoformat(),
                    "ai_request_id": review_ref["ai_request_id"] if review_ref else None,
                    "submitted_output_ref": f"attempt:{current.id}/submitted_output_match",
                    "criteria": [{"criterion_id": criterion["criterion_id"],
                        "evidence_ref": f"ai_request:{review_ref['ai_request_id']}/criteria/{index}"}
                        for index, criterion in enumerate(review_ref["review"]["criteria"])] if review_ref else [],
                }
                current.feedback = evidence
                current.status = "confirmed"
                item.status = Status.COMPLETED
        elif item.status == Status.CANCELLED:
            item.status = (self._implement_wait(current, item) if item.current_step_key == "implement" else
                           Status.WAITING_CONFIRMATION if "understand" in item.step_outputs else Status.READY)
        elif item.status == Status.RUNNING:
            request = self.repo.get_request(item.active_ai_request_id, lock=True)
            recover_after = (request.request_metadata or {}).get("recover_after") if request else None
            if not recover_after or datetime.now(UTC) < datetime.fromisoformat(recover_after):
                raise ConflictError("操作仍在有界运行期，请查询已有操作，不能隐式重试")
            if request.status == AIRequestStatus.RUNNING:
                request.status = AIRequestStatus.FAILED
                request.error_code = "recovery_timeout"
                request.error_message = "进程中断或结果未提交；需显式continue重试，外部调用结果未知"
                request.finished_at = datetime.now(UTC)
            if current and current.status == "reviewing" and current.ai_request_id == item.active_ai_request_id:
                current.status = "review_failed"
            item.status = self._implement_wait(current, item) if item.current_step_key == "implement" else Status.FAILED
        elif item.status == Status.FAILED and item.current_step_key == "implement":
            item.status = self._implement_wait(current, item)
        elif item.status not in (Status.READY, Status.WAITING_SUBMISSION, Status.WAITING_REVISION,
                                Status.WAITING_CONFIRMATION, Status.FAILED):
            raise ConflictError("当前状态不可安全恢复")
        item.revision += 1
        # revision本身使迟到提交失效；保留operation/request引用供审计与显式重试。

    @staticmethod
    def _can_complete(attempt: PracticeAttempt, item: PracticeSession) -> bool:
        # 本人只确认已审阅当前提交；模型建议、声明值与自测声明均不裁决结束。
        binding = (attempt.feedback or {}).get("binding", {})
        submitted_revision = binding.get("submitted_revision")
        return (bool(attempt.code_text.strip()) and len(attempt.code_text) <= 12000
            and attempt.status in ("submitted", "reviewed", "review_failed")
            and item.current_step_key == attempt.step_key == "implement"
            and attempt.session_id == item.id
            and binding.get("attempt_id") == attempt.id and binding.get("attempt_no") == attempt.attempt_no
            and binding.get("template_version") == item.template_version
            and binding.get("context_version") == item.context_version
            and type(submitted_revision) is int and 1 <= submitted_revision < item.revision)

    @classmethod
    def _implement_wait(cls, current: PracticeAttempt | None, item: PracticeSession) -> Status:
        if current is not None and cls._can_complete(current, item):
            return Status.WAITING_CONFIRMATION
        return Status.WAITING_SUBMISSION

    def _finish(self, op: dict, *, result: dict | None = None, completion=None,
                error_code: str | None = None, observed_usage=None) -> dict:
        with self.repo.transaction():
            # Project删除可级联删除会话，但请求记录仍需终结；不能因404遗留running。
            project = self.repo.get_project(op["project_id"], op["owner_id"], lock=True)
            item = self.repo.get_session(op["session_id"], op["owner_id"], lock=True) if project else None
            attempts = self.repo.get_attempts_for_update(item.id) if item else []
            current = max(attempts, key=lambda entry: entry.attempt_no, default=None)
            target = next((entry for entry in attempts if entry.id == op.get("attempt_id")), None)
            request = self.repo.get_request(op["request_id"], lock=True)
            # 恢复已把旧请求终结时，迟到结果不能覆盖失败或新操作。
            if request is not None and request.status == AIRequestStatus.RUNNING:
                request.finished_at = datetime.now(UTC)
                if result is None:
                    request.status = AIRequestStatus.FAILED
                    request.error_code = error_code
                    request.error_message = "实践指导请求失败；请查询会话后显式决定是否continue"
                else:
                    request.status = AIRequestStatus.COMPLETED
            usage = completion.usage if completion is not None else observed_usage
            if request and usage is not None:
                request.prompt_tokens = usage.prompt_tokens
                request.completion_tokens = usage.completion_tokens
                if completion is not None:
                    request.latency_ms = completion.latency_ms
                request.request_metadata = {**request.request_metadata,
                    "finish_reason": completion.finish_reason if completion is not None else None,
                    "total_tokens": usage.total_tokens,
                    "late_response": request.status == AIRequestStatus.FAILED and request.error_code != error_code}
            if request and result is not None and request.result is None:
                # 取消/超时后的迟到响应仅保留审计及用量，不覆盖已终结请求或会话。
                self.repo.add(AIResult(request_id=request.id, result_type=op.get("kind", "practice_guidance"),
                    structured_result=result, text_summary=result["summary"]))
            matches = (item is not None and item.status == Status.RUNNING and item.revision == op["revision"]
                and item.active_operation_id == op["operation_id"]
                and item.active_ai_request_id == op["request_id"]
                and item.current_step_key == op["step_key"])
            if op.get("attempt_id") is not None:
                matches = (matches and target is not None and target is current
                           and target.attempt_no == op["attempt_no"])
            is_review = op.get("kind") == "practice_review"
            if is_review:
                matches = (matches and target.operation_id == op["operation_id"]
                           and target.ai_request_id == op["request_id"])
            if matches:
                item.revision += 1
                if result is None:
                    item.status = Status.FAILED
                    if is_review:
                        target.status = "review_failed"
                        target.feedback = {**target.feedback, "review_error": {
                            "source": "provider_or_structure_error", "code": error_code,
                            "ai_request_id": request.id}}
                        self._event(item, op["event_key"] + ":failed", "review_failed", {}, attempt=target)
                elif is_review:
                    target.status = "reviewed"
                    target.reviewed_at = datetime.now(UTC)
                    target.feedback = bind_review(target.feedback, result=result,
                        request_id=request.id, operation_id=op["operation_id"])
                    item.step_outputs = {**item.step_outputs, "implement": {
                        "ai_request_id": request.id, "attempt_id": target.id}}
                    item.status = self._implement_wait(target, item)
                    self._event(item, op["event_key"] + ":finished", "review_finished", {}, attempt=target)
                    for criterion in result["criteria"]:
                        if criterion["verdict"] == "fail":
                            self._event(item, op["event_key"] + ":criterion:" + criterion["criterion_id"],
                                "criterion_issue", {}, attempt=target,
                                criterion_id=criterion["criterion_id"], issue_type=criterion["issue_type"])
                elif op.get("kind") == "practice_code_guidance":
                    # 代码讲解只是建议，不替换已绑定的静态评审或当前候选。
                    item.status = self._implement_wait(current, item)
                else:
                    item.step_outputs = {**item.step_outputs, op["step_key"]: {"ai_request_id": request.id}}
                    item.status = Status.WAITING_CONFIRMATION if op["step_key"] == "understand" else Status.WAITING_SUBMISSION
            self.repo.flush()
            if item is None:
                return {"session": None, "session_missing": True, "detached": True,
                        "model_request": self._request_meta(request)}
            return self._detail(item, self.repo.get_event(item.id, op["event_key"]), detached=not matches)

    def _event(self, item: PracticeSession, key: str, kind: str, payload: dict,
               *, attempt: PracticeAttempt | None = None, criterion_id: str | None = None,
               issue_type: str | None = None) -> PracticeEvent:
        event = PracticeEvent(id=str(uuid4()), session_id=item.id, event_key=key, event_type=kind,
            attempt_id=attempt.id if attempt else None, criterion_id=criterion_id, issue_type=issue_type,
            confirmation_kind=("practice_owner" if attempt else "understanding") if kind == "step_confirmed" else None,
            occurred_at=datetime.now(UTC), action_payload={"request": payload,
                "template_id": item.template_id, "template_version": item.template_version,
                "step_key": "understand" if kind == "step_confirmed" and attempt is None else item.current_step_key,
                "context_version": item.context_version, "revision": item.revision,
                **({"attempt_no": attempt.attempt_no, "attempt_id": attempt.id} if attempt else {}),
                "operation_id": item.active_operation_id, "ai_request_id": item.active_ai_request_id,
                "status": item.status.value})
        self.repo.add(event)
        return event

    def _detail(self, item: PracticeSession, event: PracticeEvent | None = None,
                *, replayed: bool = False, detached: bool = False) -> dict:
        fields = ("id", "owner_user_id", "project_id", "template_id", "template_version",
            "context_version", "context_snapshot", "current_step_key", "revision",
            "active_operation_id", "active_action", "active_ai_request_id", "step_outputs", "created_at", "updated_at")
        data = {key: deepcopy(getattr(item, key)) for key in fields}
        data.update(status=item.status.value, template=get_template(), attempts=[], outputs={},
                    replayed=replayed, detached=detached, model_request=None, action_result=None)
        attempts = self.repo.list_attempts(item.id)
        current = max(attempts, key=lambda entry: entry.attempt_no, default=None)
        data["attempts"] = [self._attempt_detail(attempt, current, item) for attempt in attempts]
        data["current_attempt"] = self._attempt_detail(current, current, item) if current else None
        data["active_result"] = None
        for step, reference in item.step_outputs.items():
            request = self.repo.get_request(reference["ai_request_id"])
            if request and request.result:
                data["outputs"][step] = deepcopy(request.result.structured_result)
        if item.active_ai_request_id:
            request = self.repo.get_request(item.active_ai_request_id)
            data["model_request"] = self._request_meta(request)
            if request and request.result:
                data["active_result"] = deepcopy(request.result.structured_result)
        if event:
            meta = deepcopy(event.action_payload)
            request_id = meta.get("ai_request_id")
            data["action_result"] = {"event_key": event.event_key, **meta,
                "model_request": self._request_meta(self.repo.get_request(request_id)) if request_id else None}
        return data

    @classmethod
    def _attempt_detail(cls, attempt: PracticeAttempt, current: PracticeAttempt | None,
                        item: PracticeSession) -> dict:
        return {"id": attempt.id, "attempt_no": attempt.attempt_no, "step_key": attempt.step_key,
            "status": attempt.status, "code": attempt.code_text,
            "declared_output": deepcopy(attempt.declared_output), "self_statement": attempt.self_statement,
            "feedback": deepcopy(attempt.feedback), "review_schema_version": attempt.review_schema_version,
            "ai_request_id": attempt.ai_request_id, "operation_id": attempt.operation_id,
            "is_current": attempt is current, "candidate_stale": attempt is not current,
            "can_confirm": (attempt is current and item.status in (Status.WAITING_SUBMISSION,
                Status.WAITING_REVISION, Status.WAITING_CONFIRMATION, Status.FAILED)
                and cls._can_complete(attempt, item)),
            "created_at": attempt.created_at, "reviewed_at": attempt.reviewed_at}

    @staticmethod
    def _request_meta(request: AIRequest | None) -> dict | None:
        if request is None:
            return None
        return {"id": request.id, "status": request.status.value, "provider": request.provider,
            "model": request.model, "error_code": request.error_code,
            "prompt_tokens": request.prompt_tokens, "completion_tokens": request.completion_tokens,
            "latency_ms": request.latency_ms, "requested_at": request.requested_at,
            "finished_at": request.finished_at}
