import asyncio
import json
import unittest
from copy import deepcopy

from app.api.deps import build_workflow_registry
from app.ai.client import AIClient
from app.core.exceptions import ConflictError
from app.context.context_manager import ContextManager
from app.models.enums import WorkflowRunStatus
from app.schemas.workflow import WorkflowRunResponse
from app.services.workflow import WorkflowService
from app.workflow.engine import WorkflowEngine, WorkflowEngineLimits, WorkflowRunMode
from tests.test_workflow_engine import FakeExecutionRepository, QueueProvider, make_workflow
from types import SimpleNamespace
from unittest.mock import Mock, patch
from app.models.enums import WorkflowNodeStatus, WorkflowStatus
from app.repositories.workflow import WorkflowRepository, WorkflowNodeRecord, WorkflowEdgeRecord


RESULTS = [
    dict(result_type="exercise_hint", summary="考虑字符访问顺序。", hints=["从末尾向前访问字符。"], concepts=["切片"], next_step="尝试步长 -1。"),
    dict(result_type="code_explanation", summary="切片返回倒序字符串。", steps=["text[::-1] 使用负步长倒序访问。"], concepts=["切片"], complexity="时间 O(n)，空间 O(n)。", pitfalls=["不要遗漏返回值。"]),
    dict(result_type="answer_review", summary="静态阅读符合题意，仍需自测。", verdict="looks_correct", strengths=["保留了字符。"], issues=[], suggested_tests=["输入 abc，预期 cba。"], next_step="测试空字符串。"),
]


class TeachingWorkflowTests(unittest.TestCase):
    def setup_workflow(self, outcomes=None):
        workflow = make_workflow()
        workflow.project.description = "编写函数，把输入字符串倒序返回。"
        for node, result in zip(workflow.nodes, RESULTS):
            node.node_type = result["result_type"]
            node.config = {"student_code": "def reverse_string(text):\n    return text[::-1]\n"}
        repository = FakeExecutionRepository(workflow)
        provider = QueueProvider(outcomes if outcomes is not None else [json.dumps(item, ensure_ascii=False) for item in RESULTS])
        client = AIClient(provider, total_timeout_seconds=1, max_retries=0, retry_base_delay_seconds=0.1, max_retry_delay_seconds=1)
        registry = build_workflow_registry(client, SimpleNamespace(deepseek_model="fake", ai_agent_temperature=0.1))
        engine = WorkflowEngine(repository, registry, ContextManager(), WorkflowEngineLimits(max_nodes=12, max_rounds=12, max_node_tokens=1200, max_completion_tokens=4000, total_timeout_seconds=2, recovery_timeout_seconds=3, max_concurrency=1))
        return workflow, repository, provider, engine

    def run_engine(self, workflow, engine):
        return asyncio.run(engine.run(workflow.id, 1, expected_version=workflow.version, mode=WorkflowRunMode.INCOMPLETE))

    def test_teaching_results_roundtrip_without_changing_project_context(self):
        workflow, repository, provider, engine = self.setup_workflow()
        original = deepcopy(workflow.project.context_data)
        run = self.run_engine(workflow, engine)
        self.assertEqual(run.status, WorkflowRunStatus.COMPLETED)
        self.assertEqual(workflow.project.context_data, original)
        response = WorkflowRunResponse.model_validate(WorkflowService._to_run_data(run), from_attributes=True)
        self.assertEqual([node.result.result_type for node in response.nodes], [item["result_type"] for item in RESULTS])
        self.assertEqual(len(provider.requests), 3)
        for request in provider.requests:
            self.assertIn(workflow.project.description, request.messages[-1].content)
            self.assertNotIn("def reverse_string", request.messages[0].content)
        self.assertEqual(len(repository.runs), 1)

    def test_missing_code_or_problem_rejected_before_any_paid_call(self):
        for field, value in [("student_code", None), ("student_code", " \n"), ("problem", "   ")]:
            with self.subTest(field=field, value=value):
                workflow, repository, provider, engine = self.setup_workflow()
                workflow.nodes[1].config[field] = value
                with self.assertRaises(ConflictError):
                    self.run_engine(workflow, engine)
                self.assertEqual(provider.requests, [])
                self.assertEqual(repository.runs, [])

    def test_invalid_review_keeps_previous_results_and_can_resume(self):
        outputs = [json.dumps(item) for item in RESULTS]
        workflow, repository, provider, engine = self.setup_workflow(outputs[:2] + ['{"result_type":"answer_review","verdict":"full_marks"}', outputs[2]])
        failed = self.run_engine(workflow, engine)
        self.assertEqual(failed.status, WorkflowRunStatus.FAILED)
        self.assertEqual(sum(item.result is not None for item in failed.ai_requests), 2)
        resumed = self.run_engine(workflow, engine)
        self.assertEqual(resumed.status, WorkflowRunStatus.COMPLETED)
        self.assertEqual(len(resumed.ai_requests), 1)
        self.assertEqual(len(provider.requests), 4)

    def test_saving_changed_code_invalidates_only_changed_node(self):
        workflow, _, _, _ = self.setup_workflow()
        workflow.status = WorkflowStatus.COMPLETED
        for node in workflow.nodes:
            node.status = WorkflowNodeStatus.SUCCESS
        session = Mock()
        session.scalar.return_value = workflow.version
        repository = WorkflowRepository(session)
        records = [WorkflowNodeRecord(node.node_key, node.node_type, node.name, 100, 80, dict(node.config)) for node in workflow.nodes]
        records[-1].config["student_code"] = "def reverse_string(text):\n    return text[::1]"
        edges = [WorkflowEdgeRecord(workflow.nodes[i].node_key, workflow.nodes[i+1].node_key, None) for i in range(2)]
        with patch.object(repository, "_reload_workflow", return_value=workflow):
            repository.replace_graph(workflow, expected_version=workflow.version, nodes=records, edges=edges)
        self.assertEqual([node.status for node in workflow.nodes], [WorkflowNodeStatus.SUCCESS, WorkflowNodeStatus.SUCCESS, WorkflowNodeStatus.STALE])
        self.assertEqual(workflow.status, WorkflowStatus.STALE)
        session.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
