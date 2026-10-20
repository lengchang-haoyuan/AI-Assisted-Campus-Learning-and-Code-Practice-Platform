"""本轮明确授权的隔离 API/MySQL 验证；保留成功来源，不触碰业务库。"""
import asyncio
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
from secrets import token_hex, token_urlsafe
import sys
from time import sleep
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from app.ai.client import AIClient
from app.ai.provider import AIProvider, AIProviderResult, AIUsage
from app.core.config import get_settings, get_security_settings
from app.core.database import get_engine, get_session_factory
from app.core.security import SecurityService
from app.main import create_app
from app.models.base import Base
from app.models.ai import AIRequest
from app.models.learning import DailyTask, LearningRecord
from app.models.project import Project
from app.models.submission import Feedback, Submission, SubmissionVersion
from app.models.teaching import ClassMembership
from app.models.campus import CampusMembership
from app.repositories.campus import CampusRepository
from app.repositories.submission import SubmissionRepository
from app.services.campus import CampusService
from scripts.verify_integration import configure_isolated_database, database_counts
from tests.test_agents import analysis_json

OUT = Path(r'C:\Users\Administrator\AppData\Local\Temp\ScholarHub-S02-20261020')
DATABASE = 'scholarhub_l4_s02_20261020'
MARKER = 's02_' + token_hex(4)
AUTH = {'user_reply': '批准新建隔离库并保留来源样例（推荐）', 'target_host': '127.0.0.1', 'target_port': 3306, 'database': DATABASE, 'max_fictional_accounts': 4, 'max_submission_heads': 3, 'max_tasks': 204, 'provider': 'fake_only', 'retention': '保留成功来源供S03；只按本轮标记处理临时／失败对象；不清空旧库、不删库、不改业务服务配置', 'recorded_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')}
(OUT / 'authorization.json').write_text(json.dumps(AUTH, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
original_url = make_url(get_settings().database_url)
assert original_url.database != DATABASE and original_url.host in {'127.0.0.1', 'localhost', '::1'}
assert (original_url.port or 3306) == 3306
events = []
checks = []
objects = {'run_marker': MARKER, 'database': DATABASE, 'accounts': {}, 'assignments': [], 'submissions': [], 'task_ids': []}
secret_keys = {'password', 'password_hash', 'token', 'access_token', 'refresh_token', 'slider_token', 'challenge_id', 'authorization'}

def safe(value):
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items() if k.lower() not in secret_keys}
    if isinstance(value, list):
        return [safe(v) for v in value]
    return value

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=lambda x: x.isoformat() if hasattr(x, 'isoformat') else str(x)) + '\n', encoding='utf-8')

def business_counts():
    engine = create_engine(original_url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
            connection.commit()
            assert connection.scalar(text('SELECT @@session.transaction_read_only')) == 1
            counts = {name: int(connection.scalar(select(func.count()).select_from(table))) for name, table in Base.metadata.tables.items()}
            connection.rollback()
            return counts
    finally:
        engine.dispose()

def check(name, value, expected=True):
    assert value == expected, f'{name}: expected {expected!r}, got {value!r}'
    checks.append({'check': name, 'actual': value, 'expected': expected, 'status': 'passed'})

def signature():
    with get_session_factory()() as session:
        return {'counts': {model.__tablename__: session.scalar(select(func.count()).select_from(model)) for model in [Submission, SubmissionVersion, Feedback, LearningRecord]}, 'heads': [list(row) for row in session.execute(select(Submission.id, Submission.latest_version_number, Submission.revision).order_by(Submission.id))], 'versions': [[a, b, str(c), d] for a, b, c, d in session.execute(select(SubmissionVersion.submission_id, SubmissionVersion.version_number, SubmissionVersion.status, SubmissionVersion.revision).order_by(SubmissionVersion.submission_id, SubmissionVersion.version_number))]}

class Provider(AIProvider):
    calls = 0
    committed_running_seen = False

    @property
    def name(self):
        return 'fake'

    async def complete(self, request):
        self.calls += 1
        with get_session_factory()() as session:
            self.committed_running_seen = bool(session.scalar(select(func.count()).select_from(AIRequest).where(AIRequest.status == 'running')))
        return AIProviderResult(provider='fake', model='s02-fake-model', content=analysis_json(), finish_reason='stop', usage=AIUsage(prompt_tokens=100, completion_tokens=80, total_tokens=180))

def run():
    before = business_counts()
    save('business-counts-before.json', before)
    configure_isolated_database(DATABASE, initialize=True)
    check('isolated_initial_rows', sum(database_counts().values()), 0)
    check('isolated_table_count', len(Base.metadata.tables), 34)
    source = json.loads((Path.cwd().parent / '开发相关文档/阶段报告/AI大数据改造/V2/S01-分析固定样例与独立答案.json').read_text(encoding='utf-8'))
    check('source_schema_fields', sum(len(v) for v in source['schema'].values()), 71)
    for table, fields in source['schema'].items():
        for field in fields:
            col = Base.metadata.tables[table].c[field['field']]
            assert col.nullable == field['nullable']
    provider = Provider()
    fake = AIClient(provider, total_timeout_seconds=5, max_retries=0, retry_base_delay_seconds=0.1, max_retry_delay_seconds=1)
    with patch('app.api.deps.build_ai_client', return_value=fake):
        app = create_app()

        async def send(method, path, kwargs):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url='http://s02-isolated') as client:
                return await client.request(method, '/api/v1' + path, **kwargs)

        def call(method, path, expected=200, **kwargs):
            if method == 'POST' and path == '/auth/login':
                challenge = call('POST', '/auth/slider/challenge')
                sleep(0.6)
                verified = call('POST', '/auth/slider/verify', json={'challenge_id': challenge['challenge_id'], 'position': 100})
                kwargs['json'] = {**kwargs['json'], 'slider_token': verified['slider_token']}
            response = asyncio.run(send(method, path, kwargs))
            try:
                data = response.json() if response.content else None
            except ValueError:
                data = {'non_json_response': True}
            events.append({'sequence': len(events) + 1, 'time': datetime.now(UTC).isoformat(), 'method': method, 'path': path, 'request_body': safe(kwargs.get('json')), 'status_code': response.status_code, 'response': safe(data)})
            accepted = expected if isinstance(expected, tuple) else (expected,)
            assert response.status_code in accepted, f'{method} {path}: expected {accepted}, got {response.status_code}'
            return data

        credentials = {}
        headers = {}
        for role in ['admin', 'teacher', 'student', 'boundary_student']:
            username = f'{MARKER}_{role}'
            password = token_urlsafe(32)
            user = call('POST', '/auth/register', 201, json={'username': username, 'email': username + '@example.invalid', 'password': password})
            objects['accounts'][role] = {'id': user['id'], 'fictional_username': username}
            credentials[role] = {'identifier': username, 'password': password}
        admin_id = objects['accounts']['admin']['id']
        with get_session_factory()() as session:
            CampusService(CampusRepository(session), SecurityService(get_security_settings())).initialize_first_admin(user_id=admin_id, reason='S02授权隔离库虚构管理员初始化')
        for role in ['admin', 'teacher', 'student', 'boundary_student']:
            token = call('POST', '/auth/login', json=credentials[role])
            headers[role] = {'Authorization': 'Bearer ' + token['access_token']}
            if role != 'admin':
                invitation = call('POST', '/campus/invitations', 201, headers=headers['admin'], json={'target_user_id': objects['accounts'][role]['id'], 'role': 'teacher' if role == 'teacher' else 'student', 'reason': 'S02本轮虚构角色'})
                call('POST', '/campus/invitations/redeem', headers=headers[role], json={'token': invitation['token']})
                token = call('POST', '/auth/login', json=credentials[role])
                headers[role] = {'Authorization': 'Bearer ' + token['access_token']}
        student = headers['student']; teacher = headers['teacher']; boundary = headers['boundary_student']
        uid = objects['accounts']['student']['id']
        project = call('POST', '/projects', 201, headers=student, json={'name': f'{MARKER}已有来源核验', 'language': 'Python', 'status': 'in_progress'})
        objects['project_id'] = project['id']
        call('GET', f"/projects/{project['id']}", 403, headers=boundary)
        tz = timezone(timedelta(hours=8)); today = datetime.now(tz).date(); yesterday = today - timedelta(days=1)

        def plan(label, actor, **kwargs):
            return call('POST', '/learning/plans', 201, headers=actor, json={'title': f'{MARKER}_{label}', 'status': 'active', **kwargs})

        empty = plan('empty', student)
        call('PUT', f"/learning/plans/{empty['id']}", 409, headers=student, json={'status': 'completed'})
        check('empty_plan_preserved_active', call('GET', f"/learning/plans/{empty['id']}", headers=student)['status'], 'active')
        main = plan('primary', student, project_id=project['id'], start_date=yesterday.isoformat(), end_date=today.isoformat())
        objects['main_plan_id'] = main['id']; objects['empty_plan_id'] = empty['id']
        tasks = []
        for index in range(4):
            task = call('POST', '/learning/tasks', 201, headers=student, json={'title': f'{MARKER}_main_{index}', 'scheduled_date': (yesterday if index == 3 else today).isoformat(), 'plan_id': main['id']})
            tasks.append(task); objects['task_ids'].append(task['id'])
        for task in tasks[:2]:
            done = call('POST', f"/learning/tasks/{task['id']}/complete", headers=student)
            replay = call('POST', f"/learning/tasks/{task['id']}/complete", headers=student)
            check(f"task_{task['id']}_completion_idempotent", replay['completed_at'], done['completed_at'])
        call('PUT', f"/learning/tasks/{tasks[2]['id']}", headers=student, json={'status': 'cancelled'})
        call('PUT', f"/learning/tasks/{tasks[0]['id']}", 403, headers=boundary, json={'title': '越权不应写入'})
        record_body = {'title': f'{MARKER}_ordinary', 'record_type': 'project', 'duration_minutes': 25, 'project_id': project['id'], 'occurred_at': datetime.combine(yesterday, datetime.min.time(), tzinfo=tz).replace(hour=23, minute=30).astimezone(UTC).isoformat()}
        record = call('POST', '/learning/records', 201, headers=student, json=record_body)
        call('PUT', f"/learning/records/{record['id']}", headers=student, json={'duration_minutes': 30})
        second = call('POST', '/learning/records', 201, headers=student, json={**record_body, 'title': f'{MARKER}_ordinary_2', 'duration_minutes': 45, 'occurred_at': datetime.combine(today, datetime.min.time(), tzinfo=tz).replace(hour=0, minute=30).astimezone(UTC).isoformat()})
        objects['manual_record_ids'] = [record['id'], second['id']]
        for changes in [{'duration_minutes': 0}, {'duration_minutes': None}, {'occurred_at': today.isoformat() + 'T00:00:00'}, {'record_metadata': {'source': 'teaching_feedback', 'submission_id': 1}}]:
            call('POST', '/learning/records', 422, headers=student, json={**record_body, **changes})
        call('PUT', f"/learning/records/{record['id']}", 403, headers=boundary, json={'duration_minutes': 60})

        edge = plan('199_of_200', boundary)
        objects['boundary_plan_id'] = edge['id']
        for i in range(200):
            task = call('POST', '/learning/tasks', 201, headers=boundary, json={'title': f'{MARKER}_boundary_{i}', 'scheduled_date': today.isoformat(), 'plan_id': edge['id']})
            objects['task_ids'].append(task['id'])
            if i < 199:
                call('POST', f"/learning/tasks/{task['id']}/complete", headers=boundary)
            else:
                boundary_pending = task['id']
        display = call('GET', f"/learning/plans/{edge['id']}", headers=boundary)
        check('boundary_legacy_display_progress', display['progress'], 100)
        call('PUT', f"/learning/plans/{edge['id']}", 409, headers=boundary, json={'status': 'completed'})
        call('PUT', f"/learning/plans/{edge['id']}", headers=boundary, json={'status': 'cancelled'})
        call('POST', f'/learning/tasks/{boundary_pending}/complete', 409, headers=boundary)
        call('POST', '/learning/tasks', 409, headers=boundary, json={'title': f'{MARKER}_forbidden_extra', 'scheduled_date': today.isoformat(), 'plan_id': edge['id']})
        call('DELETE', f'/learning/tasks/{boundary_pending}', 409, headers=boundary)

        classroom = call('POST', '/campus/classes', 201, headers=teacher, json={'name': f'{MARKER}_class', 'course_title': 'S02既有业务核验', 'term_label': '2026'})
        objects['class_id'] = classroom['id']
        membership = call('GET', '/campus/me', headers=student)['membership']
        call('POST', f"/campus/classes/{classroom['id']}/members", 201, headers=teacher, json={'campus_membership_id': membership['id'], 'member_role': 'student'})
        for i in range(3):
            assignment = call('POST', f"/campus/classes/{classroom['id']}/assignments", 201, headers=teacher, json={'title': f'{MARKER}_assignment_{i}', 'instructions': '静态材料与教师确认核验，不执行学生代码。', 'learning_objectives': ['正确记录修订'], 'acceptance_criteria': ['关联版本与真实反馈'], 'due_at': (datetime.now(UTC) + timedelta(days=7)).isoformat()})
            objects['assignments'].append(assignment['id'])
            call('POST', f"/campus/assignments/{assignment['id']}/publish", headers=teacher, json={'expected_revision': assignment['revision']})
        aid = objects['assignments'][0]
        body = {'request_key': f'{MARKER}_v1', 'expected_latest_version': 0, 'summary': 'S02 V1待补边界说明', 'source_project_id': project['id']}
        v1 = call('POST', f'/campus/assignments/{aid}/submissions', 201, headers=student, json=body)
        objects['submissions'].append(v1['id']); sid = v1['id']
        sig = signature()
        replay = call('POST', f'/campus/assignments/{aid}/submissions', headers=student, json=body)
        check('v1_replay_same_id', replay['id'], sid); check('v1_replay_no_rows_or_revisions', signature(), sig)
        call('POST', f'/campus/assignments/{aid}/submissions', 409, headers=student, json={**body, 'summary': '冲突载荷'})
        check('v1_request_key_conflict_no_partial_write', signature(), sig)
        returned_body = {'expected_revision': v1['revision'], 'decision': 'return', 'comment': '请补充边界说明。'}
        returned = call('POST', f'/campus/submissions/{sid}/versions/1/feedback', 201, headers=teacher, json=returned_body)
        sig = signature()
        replay = call('POST', f'/campus/submissions/{sid}/versions/1/feedback', headers=teacher, json=returned_body)
        check('return_replay_same_feedback', replay['id'], returned['id']); check('return_replay_no_rows_or_revisions', signature(), sig)
        call('POST', f'/campus/submissions/{sid}/versions/1/feedback', 409, headers=teacher, json={**returned_body, 'comment': '冲突评语'})
        check('return_payload_conflict_no_partial_write', signature(), sig)
        v2_body = {**body, 'request_key': f'{MARKER}_v2', 'expected_latest_version': 1, 'summary': 'S02 V2补齐边界说明'}
        call('POST', f'/campus/assignments/{aid}/submissions', 409, headers=student, json={**v2_body, 'expected_latest_version': 0})
        check('old_latest_version_no_partial_write', signature(), sig)
        v2 = call('POST', f'/campus/assignments/{aid}/submissions', 201, headers=student, json=v2_body)
        sig = signature()
        call('POST', f'/campus/assignments/{aid}/submissions', headers=student, json=v2_body)
        check('v2_replay_no_rows_or_revisions', signature(), sig)
        accept_body = {'expected_revision': v2['revision'], 'decision': 'accept', 'comment': 'S02版本材料符合固定教学要求。'}
        call('POST', f'/campus/submissions/{sid}/versions/2/feedback', 409, headers=teacher, json={**accept_body, 'expected_revision': 1})
        check('old_feedback_revision_no_partial_write', signature(), sig)
        accepted = call('POST', f'/campus/submissions/{sid}/versions/2/feedback', 201, headers=teacher, json=accept_body)
        sig = signature()
        replay = call('POST', f'/campus/submissions/{sid}/versions/2/feedback', headers=teacher, json=accept_body)
        check('accept_replay_same_feedback', replay['id'], accepted['id']); check('accept_replay_no_record_duplication', signature(), sig)
        call('POST', f'/campus/submissions/{sid}/versions/2/feedback', 409, headers=teacher, json={**accept_body, 'comment': '不可覆盖已存反馈'})
        check('accept_conflict_no_partial_write', signature(), sig)
        history = call('GET', f'/campus/submissions/{sid}/versions', headers=student)['items']
        check('version_history', [[v['version_number'], v['status']] for v in history], [[2, 'accepted'], [1, 'returned']])
        head = call('GET', f'/campus/submissions/{sid}', headers=student)
        check('revised_submission_revision', head['revision'], 4)
        for index in [1, 2]:
            assignment_id = objects['assignments'][index]
            submitted = call('POST', f'/campus/assignments/{assignment_id}/submissions', 201, headers=student, json={**body, 'request_key': f'{MARKER}_extra_{index}', 'summary': 'S02首次提交固定材料'})
            objects['submissions'].append(submitted['id'])
            if index == 1:
                call('POST', f"/campus/submissions/{submitted['id']}/versions/1/feedback", 201, headers=teacher, json={**accept_body, 'expected_revision': submitted['revision']})
            else:
                pending = submitted
        call('GET', f'/campus/submissions/{sid}', 404, headers=boundary)
        call('POST', f'/campus/assignments/{aid}/submissions', 404, headers=boundary, json={**body, 'request_key': f'{MARKER}_outsider'})

        # Inject only a controlled failure at the real repository write boundary.
        sig = signature(); original_add = SubmissionRepository.add; flushed = []
        def fail_after_record(self, value):
            if isinstance(value, Feedback):
                raise RuntimeError('S02 controlled feedback failure after record flush')
            original_add(self, value)
            if isinstance(value, LearningRecord):
                flushed.append(value.id)
        with patch.object(SubmissionRepository, 'add', fail_after_record):
            call('POST', f"/campus/submissions/{pending['id']}/versions/1/feedback", 500, headers=teacher, json={**accept_body, 'expected_revision': pending['revision']})
        check('rollback_probe_record_was_flushed', len(flushed), 1)
        check('rollback_after_record_flush_is_atomic', signature(), sig)
        objects['rolled_back_record_ids'] = flushed

        call('POST', f"/projects/{project['id']}/context", 201, headers=student)
        result = call('POST', '/agents/project-analysis', 201, headers=student, json={'project_id': project['id'], 'input': {}})
        check('fake_agent_succeeded', result['status'], 'completed')
        check('fake_provider_only_one_call', provider.calls, 1)
        check('request_committed_before_fake_provider', provider.committed_running_seen)
        objects['ai_request_id'] = result['request_id']
        call('GET', f"/agents/results/{result['request_id']}", 404, headers=boundary)

        with get_session_factory()() as session:
            records = list(session.scalars(select(LearningRecord).where(LearningRecord.user_id == uid).order_by(LearningRecord.id)))
            fbs = list(session.scalars(select(Feedback).where(Feedback.decision == 'accept').order_by(Feedback.id)))
            trusted = []
            for fb in fbs:
                lr = session.get(LearningRecord, fb.learning_record_id)
                sub = session.get(Submission, fb.submission_id)
                version = session.scalar(select(SubmissionVersion).where(SubmissionVersion.submission_id == sub.id, SubmissionVersion.version_number == fb.version_number))
                sm = session.get(ClassMembership, sub.student_membership_id); cm = session.get(CampusMembership, sm.campus_membership_id)
                tm = session.get(ClassMembership, fb.teacher_membership_id)
                check(f'feedback_{fb.id}_same_student', lr.user_id, cm.user_id)
                check(f'feedback_{fb.id}_teacher_same_class', [tm.class_id, str(tm.member_role)], [sub.class_id, 'teacher'])
                check(f'feedback_{fb.id}_matching_version', str(version.status), 'accepted')
                check(f'feedback_{fb.id}_unknown_duration_preserved', lr.duration_minutes, None)
                check(f'feedback_{fb.id}_no_personal_task_join', lr.task_id, None)
                trusted.append({'feedback_id': fb.id, 'submission_id': sub.id, 'version_number': fb.version_number, 'learning_record_id': lr.id, 'user_id': lr.user_id, 'teacher_membership_id': fb.teacher_membership_id, 'class_id': sub.class_id})
            task_rows = list(session.scalars(select(DailyTask).where(DailyTask.user_id == uid)))
            other_tasks = list(session.scalars(select(DailyTask).where(DailyTask.plan_id == edge['id'])))
            known = [r.duration_minutes for r in records if r.duration_minutes is not None]
            active_days = sorted({r.occurred_at.astimezone(tz).date().isoformat() for r in records})
            completed = sum(str(t.status) == 'completed' for t in task_rows)
            canceled = sum(str(t.status) == 'cancelled' for t in task_rows)
            overdue = sum(t.scheduled_date < today and str(t.status) in ['pending', 'in_progress'] for t in task_rows)
            check('primary_record_count', len(records), 4); check('primary_known_minutes', sum(known), 75)
            check('primary_missing_duration', len(records) - len(known), 2); check('primary_active_days', len(active_days), 2)
            check('primary_task_fraction_and_cancelled', [completed, len(task_rows), canceled, overdue], [2, 4, 1, 1])
            check('boundary_completed_total', [sum(str(t.status) == 'completed' for t in other_tasks), len(other_tasks)], [199, 200])
            check('boundary_exact_percent', str((Decimal(199) * 100 / Decimal(200)).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)), '99.500000')
            check('task_date_not_shifted', session.get(DailyTask, tasks[3]['id']).scheduled_date.isoformat(), yesterday.isoformat())
            check('utc_times_are_aware', all(r.occurred_at.utcoffset() == timedelta(0) for r in records))
            counts = signature()['counts']
            check('three_cohorts_four_versions_three_feedback', [counts['submissions'], counts['submission_versions'], counts['feedback']], [3, 4, 3])
            waits = []
            for submission_id in objects['submissions']:
                feedback = session.scalar(select(Feedback).where(Feedback.submission_id == submission_id).order_by(Feedback.created_at).limit(1))
                if feedback is not None:
                    version = session.scalar(select(SubmissionVersion).where(SubmissionVersion.submission_id == submission_id, SubmissionVersion.version_number == feedback.version_number))
                    seconds = Decimal(str((feedback.created_at - version.submitted_at).total_seconds()))
                    assert seconds >= 0
                    waits.append({'submission_id': submission_id, 'submitted_at': version.submitted_at, 'feedback_at': feedback.created_at, 'seconds': str(seconds), 'minutes': str(seconds / 60)})
            derived_ids = [r['learning_record_id'] for r in trusted]
        for record_id in derived_ids:
            call('PUT', f'/learning/records/{record_id}', 409, headers=student, json={'duration_minutes': 60})
        summary = {'dataset_kind': 'controlled', 'owner_user_id': uid, 'source_cutoff': datetime.now(UTC).isoformat(), 'period_start': yesterday.isoformat(), 'period_end': today.isoformat(), 'known_minutes': 75, 'record_count': 4, 'known_duration_count': 2, 'missing_duration_count': 2, 'known_zero_count': 0, 'active_days': active_days, 'trusted_teaching_records': trusted, 'primary_tasks': {'completed': 2, 'total': 4, 'cancelled': 1, 'overdue_unfinished': 1, 'percent': '50.000000'}, 'cohort': {'total': 3, 'revised': 1, 'confirmed': 2, 'first_pass': 1, 'revised_confirmed': 1, 'pending': 1, 'revised_percent': '33.333333', 'confirmation_percent': '66.666667', 'first_feedback_coverage': '2/3', 'first_feedback_waits': waits}, 'boundary_other_owner': {'user_id': objects['accounts']['boundary_student']['id'], 'completed': 199, 'total': 200, 'percent': '99.500000', 'display_progress': 100, 'completion_rejected': True, 'terminal_plan_status': 'cancelled'}, 'empty_tasks': {'sample_count': 0, 'percent': None, 'plan_completion_rejected': True}, 'fake_ai_requests': 1, 'real_model_calls': 0, 'retained_for_S03': True, 'interpretation': '真实API产生的受控业务样例，不是自然长期用户数据；仓库URL/ref和提交说明不等于代码快照；没有执行学生代码'}
        save('independent-expected-and-observed.json', summary)
        save('objects.json', objects)
        save('isolated-final-counts.json', database_counts())
    after = business_counts(); save('business-counts-after.json', after)
    check('business_aggregate_counts_unchanged', after, before)
    check('authorized_task_limit', len(objects['task_ids']), 204)
    save('checks.json', checks)
    save('api-evidence.json', events)
    save('retention-and-cleanup.json', {'status': 'retained_by_explicit_user_authorization', 'database': DATABASE, 'run_marker': MARKER, 'no_database_dropped': True, 'no_existing_database_cleared': True, 'failed_operations_left_no_rows': True, 'rollback_probe_record_ids_absent': objects['rolled_back_record_ids'], 'successful_sources_retained_for_S03': True, 'process_only_overrides': ['DATABASE_URL', 'JWT_SECRET', 'build_ai_client'], 'environment_file_changed': False})
    result = {'status': 'passed', 'database': DATABASE, 'run_marker': MARKER, 'api_requests': len(events), 'checks': len(checks), 'fake_provider_calls': provider.calls, 'real_model_calls': 0, 'source_code_changes': 0, 'retained_for_S03': True}
    save('api-verification-result.json', result)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        import traceback
        location = traceback.extract_tb(exc.__traceback__)[-1]
        save('api-evidence-partial.json', events)
        save('objects-partial.json', objects)
        save('checks-partial.json', checks)
        error = {'status': 'failed', 'error_type': type(exc).__name__, 'location': f'{Path(location.filename).name}:{location.lineno}', 'detail': str(exc) if isinstance(exc, AssertionError) else '未输出连接或SQL参数；保留本轮隔离数据，不扩大清理范围'}
        save('api-verification-failure.json', error)
        print(json.dumps(error, ensure_ascii=False))
        sys.exit(1)
