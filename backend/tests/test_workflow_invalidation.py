from copy import deepcopy
import unittest

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AIResult
from app.models.enums import WorkflowNodeStatus, WorkflowStatus
from app.models.workflow import Workflow, WorkflowNode
from app.repositories.workflow import WorkflowRepository
from app.repositories.workflow_execution import WorkflowExecutionRepository
from app.services.workflow import (
    WorkflowEdgeCreateData, WorkflowEdgeUpdateData, WorkflowNodeUpdateData,
    WorkflowService,
)
from app.workflow.engine import WorkflowRunMode
from tests.test_workflow_engine import (
    NOW, QueueProvider, architecture_json, requirements_json, tech_stack_json,
)
from tests.test_workflow_run_edit_guard import (
    graph_snapshot, isolated_database, make_real_engine, unchanged_graph_data,
)


class WorkflowInvalidationTests(unittest.IsolatedAsyncioTestCase):
    async def prime(self, engine):
        with Session(engine, expire_on_commit=False) as session:
            provider = QueueProvider([
                requirements_json(), tech_stack_json(), architecture_json(),
            ])
            await make_real_engine(WorkflowExecutionRepository(session), provider).run(
                11, 1, expected_version=4, mode=WorkflowRunMode.ALL,
            )
            session.add(WorkflowNode(
                id=24, workflow_id=11, node_key="independent", node_type="architecture_design",
                name="无关分支", status=WorkflowNodeStatus.SUCCESS, context_version=1,
                output_data={"history": "independent"}, created_at=NOW, updated_at=NOW,
            ))
            session.commit()

    def statuses(self, engine):
        with Session(engine) as session:
            return dict(session.execute(select(WorkflowNode.id, WorkflowNode.status)).all())

    async def test_instruction_change_invalidates_only_node_and_successors_and_reruns(self):
        with isolated_database() as engine:
            await self.prime(engine)
            with Session(engine) as session:
                old_outputs = {node.id: deepcopy(node.output_data)
                               for node in session.scalars(select(WorkflowNode))}
                service = WorkflowService(WorkflowRepository(session))
                service.update_node(11, 22, 1, WorkflowNodeUpdateData({
                    "config": {"instruction": "重新分析技术栈"},
                }))
                self.assertEqual(session.get(Workflow, 11).status, WorkflowStatus.STALE)
                self.assertEqual(len(list(session.scalars(select(AIResult)))), 3)
                self.assertEqual({node.id: node.output_data
                                  for node in session.scalars(select(WorkflowNode))}, old_outputs)
            self.assertEqual(self.statuses(engine), {
                21: WorkflowNodeStatus.SUCCESS, 22: WorkflowNodeStatus.STALE,
                23: WorkflowNodeStatus.STALE, 24: WorkflowNodeStatus.SUCCESS,
            })
            with Session(engine, expire_on_commit=False) as session:
                provider = QueueProvider([tech_stack_json(), architecture_json()])
                run = await make_real_engine(WorkflowExecutionRepository(session), provider).run(
                    11, 1, expected_version=5, mode=WorkflowRunMode.INCOMPLETE,
                )
                self.assertEqual([r.request_metadata["node_id"] for r in run.ai_requests], [22, 23])
                self.assertEqual(len(provider.requests), 2)

    async def test_display_same_value_and_unused_config_do_not_invalidate(self):
        for changes in [
            {"name": "新名称", "position_x": 10, "position_y": 15},
            {"config": {"instruction": "选择兼容技术栈。"}},
            {"config": {"instruction": "选择兼容技术栈。", "display_note": "备注"}},
        ]:
            with self.subTest(changes=changes), isolated_database() as engine:
                await self.prime(engine)
                with Session(engine) as session:
                    WorkflowService(WorkflowRepository(session)).update_node(
                        11, 22, 1, WorkflowNodeUpdateData(changes),
                    )
                self.assertTrue(all(s == WorkflowNodeStatus.SUCCESS
                                    for s in self.statuses(engine).values()))

    async def test_execution_fields_and_node_type_invalidate(self):
        for changes in [
            {"node_type": "requirements_analysis"},
            {"config": {"expected_output": "列出依据"}},
            {"config": {"context_reads": []}},
            {"config": {"context_writes": []}},
        ]:
            with self.subTest(changes=changes), isolated_database() as engine:
                await self.prime(engine)
                with Session(engine) as session:
                    WorkflowService(WorkflowRepository(session)).update_node(
                        11, 22, 1, WorkflowNodeUpdateData(changes),
                    )
                self.assertEqual(self.statuses(engine)[23], WorkflowNodeStatus.STALE)
                self.assertEqual(self.statuses(engine)[24], WorkflowNodeStatus.SUCCESS)

    async def test_edge_create_update_delete_invalidate_old_and_new_targets(self):
        operations = [
            lambda service: service.create_edge(11, 1, WorkflowEdgeCreateData(21, 24, None)),
            lambda service: service.update_edge(
                11, 31, 1, WorkflowEdgeUpdateData({"target_node_id": 24}),
            ),
            lambda service: service.delete_edge(11, 31, 1),
        ]
        for index, operation in enumerate(operations):
            with self.subTest(operation=index), isolated_database() as engine:
                await self.prime(engine)
                with Session(engine) as session:
                    operation(WorkflowService(WorkflowRepository(session)))
                state = self.statuses(engine)
                self.assertEqual(state[21], WorkflowNodeStatus.SUCCESS)
                self.assertEqual(state[24], WorkflowNodeStatus.STALE if index < 2
                                 else WorkflowNodeStatus.SUCCESS)
                if index > 0:
                    self.assertEqual(state[22], WorkflowNodeStatus.STALE)
                    self.assertEqual(state[23], WorkflowNodeStatus.STALE)

    async def test_graph_save_and_single_resource_share_downstream_rules(self):
        with isolated_database() as engine:
            await self.prime(engine)
            data = unchanged_graph_data(graph_snapshot(engine))
            data.nodes[1].config["instruction"] = "整图修改技术栈"
            with Session(engine) as session:
                WorkflowService(WorkflowRepository(session)).replace_graph(11, 1, data)
            self.assertEqual(self.statuses(engine), {
                21: WorkflowNodeStatus.SUCCESS, 22: WorkflowNodeStatus.STALE,
                23: WorkflowNodeStatus.STALE, 24: WorkflowNodeStatus.SUCCESS,
            })
