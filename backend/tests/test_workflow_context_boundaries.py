import asyncio
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.context.context_manager import ContextManager, ContextNode
from app.models.enums import WorkflowRunStatus, WorkflowNodeStatus, WorkflowStatus
from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge
from app.models.project import Project
from app.models.ai import AIResult
from app.repositories.workflow_execution import WorkflowExecutionRepository
from app.workflow.engine import WorkflowRunMode
from tests.test_workflow_engine import (
    FakeExecutionRepository, QueueProvider, architecture_json, make_engine,
    make_workflow, requirements_json, tech_stack_json,
)
from tests.test_workflow_run_edit_guard import isolated_database, make_real_engine, PausedProvider


class WorkflowContextMessageTests(unittest.TestCase):
    def run_with_policy(self, config):
        workflow = make_workflow()
        workflow.nodes[0].config = config
        provider = QueueProvider([
            requirements_json(), tech_stack_json(), architecture_json(),
        ])
        run = asyncio.run(make_engine(FakeExecutionRepository(workflow), provider).run(
            11, 1, expected_version=4, mode=WorkflowRunMode.ALL,
        ))
        return workflow, provider, run

    def values(self, request):
        content = request.messages[-1].content
        raw = content.split('<PROJECT_CONTEXT_JSON>\n', 1)[1].split(
            '\n</PROJECT_CONTEXT_JSON>', 1
        )[0]
        return json.loads(raw)['values']

    def test_default_empty_and_narrow_policy_reach_serialized_messages(self):
        for config in (None, {'context_reads': []}, {'context_reads': ['project_name']}):
            with self.subTest(config=config):
                workflow, provider, run = self.run_with_policy(config)
                expected = ContextManager().get_node_policy(ContextNode(
                    21, 'requirements_analysis', config,
                )).reads
                self.assertEqual(set(self.values(provider.requests[0])), expected)
                self.assertEqual(run.status, WorkflowRunStatus.COMPLETED)
                self.assertIsNotNone(workflow.project.context_data)

    def test_invalid_or_expanded_policy_fails_before_any_provider_call(self):
        for fields in (['database'], ['unknown'], None, 'requirements'):
            with self.subTest(fields=fields):
                _, provider, run = self.run_with_policy({'context_reads': fields})
                self.assertEqual(provider.requests, [])
                self.assertEqual(run.status, WorkflowRunStatus.FAILED)


class ProjectContextInvalidationTests(unittest.IsolatedAsyncioTestCase):
    def prepare(self, engine):
        with Session(engine) as session:
            workflow = session.get(Workflow, 11)
            workflow.status = WorkflowStatus.COMPLETED
            for node in workflow.nodes:
                node.status = WorkflowNodeStatus.SUCCESS
            workflow.nodes[1].status = WorkflowNodeStatus.STALE
            other = Workflow(id=15, project_id=7, name="共享 Context", version=1,
                             status=WorkflowStatus.COMPLETED)
            session.add(other)
            session.add_all([
                WorkflowNode(id=51, workflow_id=15, node_key="architecture",
                             node_type="architecture_design", name="架构",
                             status=WorkflowNodeStatus.SUCCESS),
                WorkflowNode(id=52, workflow_id=15, node_key="child",
                             node_type="architecture_design", name="后继",
                             config={"context_reads": []}, status=WorkflowNodeStatus.SUCCESS),
                WorkflowNode(id=53, workflow_id=15, node_key="unrelated",
                             node_type="requirements_analysis", name="无关",
                             status=WorkflowNodeStatus.SUCCESS),
            ])
            session.flush()
            session.add(WorkflowEdge(workflow_id=15, source_node_id=51, target_node_id=52))
            session.commit()

    async def run_source(self, engine, language):
        with Session(engine, expire_on_commit=False) as session:
            provider = QueueProvider([tech_stack_json(language=language), architecture_json()])
            return await make_real_engine(WorkflowExecutionRepository(session), provider).run(
                11, 1, expected_version=4, mode=WorkflowRunMode.INCOMPLETE,
            )

    async def test_context_change_invalidates_other_workflow_and_reruns_only_dependencies(self):
        with isolated_database() as engine:
            self.prepare(engine)
            await self.run_source(engine, 'Java')
            with Session(engine, expire_on_commit=False) as session:
                statuses = dict(session.execute(select(WorkflowNode.id, WorkflowNode.status)
                                               .where(WorkflowNode.workflow_id == 15)).all())
                self.assertEqual(statuses, {51: WorkflowNodeStatus.STALE,
                                           52: WorkflowNodeStatus.STALE,
                                           53: WorkflowNodeStatus.SUCCESS})
                self.assertEqual(session.get(Workflow, 15).status, WorkflowStatus.STALE)
                provider = QueueProvider([architecture_json(), architecture_json()])
                run = await make_real_engine(WorkflowExecutionRepository(session), provider).run(
                    15, 1, expected_version=1, mode=WorkflowRunMode.INCOMPLETE,
                )
                self.assertEqual(len(provider.requests), 2)
                self.assertEqual(run.status, WorkflowRunStatus.COMPLETED)

    async def test_equal_context_values_leave_other_workflow_successful(self):
        with isolated_database() as engine:
            self.prepare(engine)
            await self.run_source(engine, 'Python')
            with Session(engine) as session:
                self.assertEqual(session.get(Workflow, 15).status, WorkflowStatus.COMPLETED)
                self.assertTrue(all(node.status == WorkflowNodeStatus.SUCCESS
                                    for node in session.get(Workflow, 15).nodes))

    async def test_other_running_workflow_rejects_old_context_and_can_retry(self):
        with isolated_database() as engine:
            self.prepare(engine)
            provider = PausedProvider()
            provider.outcomes = [architecture_json(), architecture_json(), requirements_json()]
            with Session(engine, expire_on_commit=False) as session:
                task = asyncio.create_task(make_real_engine(
                    WorkflowExecutionRepository(session), provider,
                ).run(15, 1, expected_version=1, mode=WorkflowRunMode.ALL))
                try:
                    await asyncio.wait_for(provider.entered.wait(), timeout=3)
                    await self.run_source(engine, 'Java')
                    with Session(engine) as other:
                        self.assertEqual(other.get(WorkflowNode, 51).status, WorkflowNodeStatus.RUNNING)
                    provider.release.set()
                    failed = await asyncio.wait_for(task, timeout=3)
                    self.assertEqual(failed.status, WorkflowRunStatus.FAILED)
                    self.assertEqual(failed.error_code, 'context_version_conflict')
                finally:
                    provider.release.set()
                    await asyncio.gather(task, return_exceptions=True)

    async def test_context_and_invalidation_roll_back_together_on_commit_failure(self):
        with isolated_database() as engine:
            self.prepare(engine)
            with Session(engine) as session:
                before = deepcopy(session.get(Project, 7).context_data)

            class FailingRepository(WorkflowExecutionRepository):
                def complete_node(inner, *args, **kwargs):
                    with patch.object(inner._session, 'commit', side_effect=IntegrityError(
                        'fake commit', {}, Exception('deterministic rejection'),
                    )):
                        return super().complete_node(*args, **kwargs)

            with Session(engine, expire_on_commit=False) as session:
                run = await make_real_engine(FailingRepository(session), QueueProvider([
                    tech_stack_json(language='Java'),
                ])).run(11, 1, expected_version=4, mode=WorkflowRunMode.INCOMPLETE)
                self.assertEqual(run.status, WorkflowRunStatus.FAILED)
            with Session(engine) as session:
                self.assertEqual(session.get(Project, 7).context_data, before)
                self.assertEqual(session.get(WorkflowNode, 51).status, WorkflowNodeStatus.SUCCESS)
                self.assertEqual(session.get(Workflow, 15).status, WorkflowStatus.COMPLETED)
                self.assertEqual(list(session.scalars(select(AIResult))), [])
