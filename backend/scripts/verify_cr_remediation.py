"""本轮 CR 专用 MySQL 补验：必须是已授权的空隔离库，不建库或清空已有数据。"""
import argparse
import asyncio
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
import json
from secrets import token_hex, token_urlsafe
from threading import Event
from unittest.mock import patch

import httpx
from sqlalchemy import event, func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_current_user
from app.context.context_manager import ContextManager
from app.context.context_schema import ContextSource, ContextSourceType
from app.context.project_context import ProjectContext
from app.core.config import SecuritySettings
from app.core.database import get_engine, get_session_factory
from app.core.exceptions import AuthenticationRequiredError, ConflictError, InputError
from app.core.security import SecurityService
from app.main import create_app
from app.models.ai import AIResult
from app.models.campus import CampusMembership, CampusRole, MembershipStatus
from app.models.enums import LearningPlanStatus, RecordType, TaskStatus, WorkflowNodeStatus, WorkflowStatus
from app.models.learning import DailyTask, LearningPlan, LearningRecord
from app.models.project import Project
from app.models.submission import Feedback, FeedbackDecision
from app.models.teaching import ClassMembership, ClassMembershipStatus, ClassMemberRole, TeachingAssignment
from app.models.user import User
from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge
from app.repositories.campus import CampusRepository
from app.repositories.learning import LearningRepository
from app.repositories.submission import SubmissionRepository
from app.repositories.teaching import TeachingRepository
from app.repositories.workflow_execution import WorkflowExecutionRepository, WorkflowExecutionVersionError
from app.services.auth import AuthService
from app.services.campus import CampusService
from app.services.learning import LearningService, PlanUpdateData, TaskCreateData, RecordUpdateData
from app.services.submission import SubmissionService
from app.services.teaching import TeachingService
from app.workflow.engine import WorkflowRunMode
from scripts.verify_cr1_workflow_concurrency import (
    Fixture, Worker, create_fixture, fail_run, require, snapshot, start_run,
    verify_edit_then_start, verify_start_then_edit, verify_simultaneous_starts,
    verify_context_then_complete, verify_completed_run_edit,
)
from scripts.verify_integration import configure_isolated_database, cleanup
from tests.test_workflow_engine import QueueProvider, architecture_json, tech_stack_json
from tests.test_workflow_run_edit_guard import make_real_engine


def identity(session, user_id):
    return AuthService._to_identity(session.get(User, user_id))


def node_request(session, fixture, run_id, context):
    node = session.get(WorkflowNode, fixture.node_id)
    version = session.get(Workflow, fixture.workflow_id).version
    return WorkflowExecutionRepository(session).start_node(run_id, node.id,
        expected_workflow_version=version, user_id=fixture.user_id, project_id=fixture.project_id,
        provider='fake', model='fake-model', node_type=node.node_type, node_key=node.node_key,
        input_hash='0' * 64, input_bytes=1, context_version=context.version).id


def commit_node(session, fixture, run_id, request_id, context, payload):
    kind = payload['result_type']
    updates = ({key: payload[key]['value'] for key in ('language', 'framework', 'frontend', 'backend', 'database')}
               if kind == 'tech_stack_analysis' else {'architecture': {'style': payload['style']}})
    merged = ContextManager().merge(context, updates,
        source=ContextSource(type=ContextSourceType.WORKFLOW_NODE, id=fixture.node_id, node_key='verify'))
    WorkflowExecutionRepository(session).complete_node(run_id, fixture.node_id, request_id,
        expected_workflow_version=1, expected_context_version=context.version,
        context=merged.context, changed_fields=merged.changed_fields, stale_node_ids=frozenset(),
        structured_result=payload, result_type=kind, text_summary=payload['summary'],
        content_hash='1' * 64, prompt_tokens=10, completion_tokens=10, latency_ms=1,
        finish_reason='stop', total_tokens=20)
    return merged.context


def workflow_checks(factory, marker):
    fixture = create_fixture(factory, marker)
    with factory() as session:
        session.get(WorkflowNode, fixture.node_id).node_type = 'tech_stack_analysis'
        other = Workflow(project_id=fixture.project_id, name='Shared Context', status=WorkflowStatus.COMPLETED)
        independent_project = Project(owner_id=fixture.user_id, name='Other project', difficulty='intermediate')
        session.add_all([other, independent_project]); session.flush()
        foreign = Workflow(project_id=independent_project.id, name='Unaffected', status=WorkflowStatus.COMPLETED)
        session.add(foreign); session.flush()
        nodes = [WorkflowNode(workflow_id=other.id, node_key='architecture', node_type='architecture_design',
                             name='架构', status=WorkflowNodeStatus.SUCCESS),
                 WorkflowNode(workflow_id=other.id, node_key='child', node_type='architecture_design',
                             name='后继', config={'context_reads': []}, status=WorkflowNodeStatus.SUCCESS),
                 WorkflowNode(workflow_id=foreign.id, node_key='other', node_type='architecture_design',
                             name='其他项目', status=WorkflowNodeStatus.SUCCESS)]
        session.add_all(nodes); session.flush()
        session.add(WorkflowEdge(workflow_id=other.id, source_node_id=nodes[0].id, target_node_id=nodes[1].id))
        session.commit()
        second = Fixture(fixture.user_id, fixture.project_id, other.id, nodes[0].id)
        foreign_id, child_id = nodes[2].id, nodes[1].id
    with factory() as a, factory() as b:
        version, context = snapshot(a, fixture)
        a_run = start_run(a, fixture, version, context)
        a_request = node_request(a, fixture, a_run, context)
        b_run = start_run(b, second, 1, context)
        b_request = node_request(b, second, b_run, context)
        changed = commit_node(a, fixture, a_run, a_request, context, json.loads(tech_stack_json(language='Java')))
        with factory() as check:
            require(check.get(WorkflowNode, second.node_id).status == WorkflowNodeStatus.RUNNING, '其他运行节点状态被覆盖')
            require(check.get(WorkflowNode, child_id).status == WorkflowNodeStatus.STALE, '跨工作流后继未失效')
            require(check.get(WorkflowNode, foreign_id).status == WorkflowNodeStatus.SUCCESS, '其他项目被失效')
        try:
            commit_node(b, second, b_run, b_request, context, json.loads(architecture_json()))
            raise AssertionError('旧 Context 结果错误提交')
        except WorkflowExecutionVersionError:
            fail_run(b, b_run, node_id=second.node_id, request_id=b_request)
        WorkflowExecutionRepository(a).finish_run(a_run, expected_workflow_version=1,
                                                 expected_context_version=changed.version)
    with factory() as session:
        provider = QueueProvider([architecture_json(), architecture_json()])
        run = asyncio.run(make_real_engine(WorkflowExecutionRepository(session), provider).run(
            second.workflow_id, fixture.user_id, expected_version=1, mode=WorkflowRunMode.INCOMPLETE))
        require(run.status.value == 'completed' and len(provider.requests) == 2, '其他工作流未按失效节点重算')
    with factory() as session:
        version, context = snapshot(session, fixture)
        before = deepcopy(context.to_storage())
        old_status = session.get(WorkflowNode, second.node_id).status
        count = session.scalar(select(func.count(AIResult.id)))
        run_id = start_run(session, fixture, version, context)
        request_id = node_request(session, fixture, run_id, context)
        try:
            with patch.object(session, 'commit', side_effect=IntegrityError('controlled rejection', {}, Exception())):
                commit_node(session, fixture, run_id, request_id, context, json.loads(tech_stack_json(language='Python')))
        except Exception as exc:
            require(type(exc).__name__ == 'WorkflowExecutionPersistenceError', '回滚测试出现非预期异常')
        else:
            raise AssertionError('提交失败样本未触发拒绝')
        fail_run(session, run_id, node_id=fixture.node_id, request_id=request_id)
        require(session.get(Project, fixture.project_id).context_data == before, '回滚后 Context 部分保存')
        require(session.get(WorkflowNode, second.node_id).status == old_status, '回滚后失效状态部分保存')
        require(session.scalar(select(func.count(AIResult.id))) == count, '回滚后结果部分保存')
    print(json.dumps({'cr3_mysql': 'passed', 'cross_workflow': True, 'other_project_unchanged': True,
                      'old_result_rejected': True, 'incomplete_calls': 2, 'atomic_rollback': True}))
    return fixture


def plan_checks(factory, fixture):
    with factory() as session:
        plan = LearningPlan(user_id=fixture.user_id, title='199/200 边界', status=LearningPlanStatus.ACTIVE, progress=100)
        session.add(plan); session.flush()
        tasks = [DailyTask(user_id=fixture.user_id, plan_id=plan.id, title=f'任务{i}', scheduled_date=date.today(),
                           status=TaskStatus.COMPLETED if i < 199 else TaskStatus.PENDING) for i in range(200)]
        session.add_all(tasks); session.commit()
        plan_id, last_task = plan.id, tasks[-1].id
        try:
            LearningService(LearningRepository(session)).update_plan(plan_id, fixture.user_id,
                PlanUpdateData({'status': LearningPlanStatus.COMPLETED}))
        except ConflictError:
            session.rollback()
        else:
            raise AssertionError('199/200 被错误接受')
        session.get(DailyTask, last_task).status = TaskStatus.COMPLETED
        session.commit()
    at_plan_lock = Event()
    with factory() as holder:
        LearningRepository(holder).get_plan(plan_id, for_update=True)
        def create_task(session):
            connection = session.connection()
            def mark(_connection, _cursor, sql, _params, _context, _many):
                if 'from learning_plans' in sql.lower() and 'for update' in sql.lower():
                    at_plan_lock.set()
            event.listen(connection, 'before_cursor_execute', mark)
            data = TaskCreateData(title='不能追加', description=None, priority='medium', scheduled_date=date.today(),
                                  start_time=None, end_time=None, estimated_minutes=1, plan_id=plan_id, project_id=None)
            return LearningService(LearningRepository(session)).create_task(fixture.user_id, data)
        worker = Worker(factory, create_task)
        try:
            require(at_plan_lock.wait(5) and not worker.done.wait(0.2), '任务变更未等待计划行锁')
            LearningService(LearningRepository(holder)).update_plan(plan_id, fixture.user_id,
                PlanUpdateData({'status': LearningPlanStatus.COMPLETED}))
        finally:
            holder.rollback(); worker.join()
        require(isinstance(worker.error, ConflictError), '计划提交完成后仍追加了任务')
    with factory() as session:
        require(session.scalar(select(func.count(DailyTask.id)).where(DailyTask.plan_id == plan_id)) == 200,
                '拒绝后任务集合已变化')
    print(json.dumps({'cr6a_mysql': 'passed', 'rounding_rejected': True, 'plan_task_race': True}))


def teaching_checks(factory, fixture, suffix, user_ids):
    security = SecurityService(SecuritySettings(jwt_secret=token_urlsafe(48)))
    with factory() as session:
        admin = User(username=f'l4_verify_{suffix}_admin', email=f'{suffix}-admin@example.invalid', password_hash='fictional-unused')
        teacher = User(username=f'l4_verify_{suffix}_teacher', email=f'{suffix}-teacher@example.invalid', password_hash='fictional-unused')
        session.add_all([admin, teacher]); session.commit()
        admin_id, teacher_id = admin.id, teacher.id
        user_ids.extend([admin_id, teacher_id])
        campus = CampusService(CampusRepository(session), security)
        campus.initialize_first_admin(user_id=admin_id, reason='CR isolated verification')
        for user_id, role in [(teacher_id, CampusRole.TEACHER), (fixture.user_id, CampusRole.STUDENT)]:
            _, token = campus.issue_invitation(identity(session, admin_id), target_user_id=user_id,
                target_email=None, role=role, expires_in_hours=1, reason='CR verified fixture')
            campus.redeem_invitation(identity(session, user_id), token=token)
        teaching = TeachingService(TeachingRepository(session))
        teacher_identity = identity(session, teacher_id)
        student_identity = identity(session, fixture.user_id)
        classroom = teaching.create_class(teacher_identity, name='CR隔离班级', course_title='项目实践', term_label='2026秋')
        member = teaching.add_member(teacher_identity, class_id=classroom.id,
            campus_membership_id=session.scalar(select(CampusMembership.id).where(CampusMembership.user_id == fixture.user_id)),
            member_role=ClassMemberRole.STUDENT)
        assignment = teaching.create_assignment(teacher_identity, class_id=classroom.id, title='CR空值验证',
            instructions='完成任务并提交验证证据。', learning_objectives=['理解验证'], acceptance_criteria=['保存证据'],
            due_at=datetime.now(UTC) + timedelta(days=2), source_project_id=None)
        application = create_app()
        application.dependency_overrides[get_current_user] = lambda: teacher_identity
        async def invalid_nulls():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://test') as client:
                for key in ('title', 'instructions', 'learning_objectives', 'acceptance_criteria'):
                    response = await client.patch(f'/api/v1/campus/assignments/{assignment.id}',
                        json={'expected_revision': assignment.revision, key: None})
                    require(response.status_code == 422, 'null 请求未在提交前拒绝')
                for endpoint in (f'/campus/assignments/{assignment.id}', f'/campus/classes/{classroom.id}/assignments'):
                    require((await client.get('/api/v1' + endpoint)).status_code == 200, 'null 拒绝后详情或列表不可读')
        asyncio.run(invalid_nulls())
        session.expire_all()
        persisted = session.get(TeachingAssignment, assignment.id)
        require(persisted.revision == assignment.revision and persisted.learning_objectives == ['理解验证'], 'null 部分保存')
        teaching.publish_assignment(teacher_identity, assignment_id=assignment.id, expected_revision=assignment.revision)
        submissions = SubmissionService(SubmissionRepository(session))
        submitted, _ = submissions.submit(student_identity, assignment_id=assignment.id,
            request_key=f'cr_{suffix}', expected_latest_version=0, summary='虚构验证样本',
            repository_url=None, repository_ref=None, source_project_id=None)
        feedback, _ = submissions.feedback(teacher_identity, submission_id=submitted['id'], version_number=1,
            expected_revision=submitted['revision'], decision=FeedbackDecision.ACCEPT, comment='已核对虚构样本')
        record_id = session.get(Feedback, feedback['id']).learning_record_id
        learning = LearningService(LearningRepository(session))
        record = learning.get_record(record_id, fixture.user_id)
        require(record.duration_minutes is None and record.record_metadata['source'] == 'teaching_submission', '真实反馈来源丢失')
        try:
            learning.update_record(record_id, fixture.user_id, RecordUpdateData({'title': '不允许'}))
        except ConflictError:
            session.rollback()
        else:
            raise AssertionError('真实教学记录可被编辑')
        application.dependency_overrides[get_current_user] = lambda: student_identity
        async def forged_metadata():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://test') as client:
                response = await client.post('/api/v1/learning/records', json={
                    'title': '伪造来源', 'record_type': 'study', 'duration_minutes': 1,
                    'record_metadata': {'source': 'teaching_submission', 'submission_id': 999, 'version_number': 1}})
                require(response.status_code == 422, '伪造来源请求未拒绝')
        asyncio.run(forged_metadata())
        membership = session.scalar(select(CampusMembership).where(CampusMembership.user_id == fixture.user_id))
        original_id = membership.id
        campus.update_account(identity(session, admin_id), user_id=fixture.user_id, reason='重新核验测试',
            expected_revision=membership.revision, expected_auth_version=None, role=None,
            campus_status=MembershipStatus.REVOKED, account_enabled=None)
        teaching.update_member(teacher_identity, class_id=classroom.id, member_id=member.id,
            expected_revision=member.revision, status=ClassMembershipStatus.REMOVED)
        _, token = campus.issue_invitation(identity(session, admin_id), target_user_id=fixture.user_id,
            target_email=None, role=CampusRole.STUDENT, expires_in_hours=1, reason='重新核验通过')
        stale = identity(session, fixture.user_id)
    def redeem(session):
        return CampusService(CampusRepository(session), security).redeem_invitation(stale, token=token)
    gate = Event()
    def simultaneous(session):
        require(gate.wait(5), '兑换屏障未释放'); return redeem(session)
    workers = [Worker(factory, simultaneous), Worker(factory, simultaneous)]
    try:
        for worker in workers: require(worker.ready.wait(5), '兑换连接未就绪')
    finally:
        gate.set()
        for worker in workers: worker.join()
    require(sum(w.error is None for w in workers) == 1, '双兑换成功次数不为一')
    require(sum(isinstance(w.error, AuthenticationRequiredError) for w in workers) == 1, '旧会话未失效')
    with factory() as session:
        membership = session.scalar(select(CampusMembership).where(CampusMembership.user_id == fixture.user_id))
        require(membership.id == original_id and membership.status == MembershipStatus.ACTIVE, '未复用成员恢复身份')
        require(session.get(ClassMembership, member.id).status == ClassMembershipStatus.REMOVED, '自动恢复了班级成员')
        require(session.scalar(select(func.count(CampusMembership.id)).where(CampusMembership.user_id == fixture.user_id)) == 1,
                '恢复产生重复身份')
    print(json.dumps({'cr5_mysql': 'passed', 'cr6b_mysql': 'passed', 'cr7_mysql': 'passed',
                      'null_revision_unchanged': True, 'real_feedback_relation': True,
                      'double_redeem_successes': 1, 'membership_reused': True, 'removed_class_member_unchanged': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    require(args.database == 'scholarhub_l4_20261016_cr1', '只允许本轮已确认的专用库')
    configure_isolated_database(args.database, initialize=False)
    @event.listens_for(get_engine(), 'checkout')
    def bound_locks(connection, _record, _proxy):
        with connection.cursor() as cursor: cursor.execute('SET SESSION innodb_lock_wait_timeout=5')
    factory = get_session_factory()
    suffix = token_hex(5)
    user_ids = []
    try:
        repeat = create_fixture(factory, f'l4_verify_{suffix}_repeat')
        user_ids.append(repeat.user_id)
        for verify in (verify_edit_then_start, verify_start_then_edit, verify_simultaneous_starts,
                       verify_context_then_complete, verify_completed_run_edit):
            verify(factory, repeat)
        fixture = workflow_checks(factory, f'l4_verify_{suffix}_student')
        user_ids.append(fixture.user_id)
        plan_checks(factory, fixture)
        teaching_checks(factory, fixture, suffix, user_ids)
        print(json.dumps({'cr_mysql_supplement': 'passed'}))
    finally:
        cleanup(user_ids, f'p15_{suffix}', suffix)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'cr_mysql_supplement': 'failed', 'error_type': type(exc).__name__,
                          'reason': str(exc) if isinstance(exc, (AssertionError, ConflictError)) else '未输出连接或SQL参数'}))
        raise SystemExit(1) from None
