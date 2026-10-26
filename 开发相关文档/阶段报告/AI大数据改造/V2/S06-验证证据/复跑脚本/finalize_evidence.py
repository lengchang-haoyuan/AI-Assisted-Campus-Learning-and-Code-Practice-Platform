import ast
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

root=Path.cwd()
v2=root/'开发相关文档/阶段报告/AI大数据改造/V2'
evidence=v2/'S06-验证证据'
def load(path):return json.loads((v2/path).read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
publication=load('S06-验证证据/publication-verification.json')
browser=load('S06-验证证据/browser/final/verification.json')
monitor=load('S06-验证证据/browser/final/server-observation.json')
nonexistent=load('S06-验证证据/nonexistent-batch.json')
case=load('S06-验证证据/frozen-cases-recheck.json')
proof=publication['API_events']
empty='45c55b05-ff63-4cc6-b6ca-734146054710'
def has_empty(owner,status):
    return any(e['path']=='offline-analytics/batches/'+empty and e['owner']==owner and e['status']==status for e in proof)
assert has_empty(3,200) and has_empty(4,404) and has_empty(None,401)
assert publication['completed_changed_content_rejected'] and publication['retry_same_batch']
assert nonexistent['actual']==404
assert monitor['GET_DML']==[] and monitor['GET_process_calls']==monitor['GET_publish_calls']==monitor['model_calls']==0
assert monitor['row_counts_unchanged'] and monitor['servers_stopped']
assert browser['status']=='passed' and len(browser['checks'])==25
frozen_checks={
    'D13.completed_batch_overwrite':{'expected':False,'actual':False,'evidence':'publication-verification.json#completed_changed_content_rejected'},
    'D13.identical_replay':{'expected':'no_op','actual':'no_op','evidence':'S06-发布结果.json#primary/replay_same_batch'},
    'D13.different_content_same_batch':{'expected':'409_conflict','actual':'409_conflict','evidence':'publication-verification.json; ConflictError domain status409 (no publish HTTP endpoint)'},
    'D13.failed_new_batch_preserves_previous':{'expected':True,'actual':True,'evidence':'publication-verification.json#API_events: failed/prepared404 then main200'},
    'D14.owner_1001_status':{'expected':200,'actual':200,'evidence':'publication-verification.json; fixture role mapped to real isolated owner3'},
    'D14.other_owner_status':{'expected':404,'actual':404,'evidence':'publication-verification.json; real isolated owner4'},
    'D14.nonexistent_status':{'expected':404,'actual':404,'evidence':'nonexistent-batch.json'},
    'D14.unauthenticated_status':{'expected':401,'actual':401,'evidence':'publication-verification.json#API_events'},
    'D14.ordinary_get_spark_calls':{'expected':0,'actual':0,'evidence':'browser/final/server-observation.json#GET_process_calls; GET publication/model guards'},
    'D14.ordinary_get_model_calls':{'expected':0,'actual':0,'evidence':'browser/final/server-observation.json#model_calls'},
}
assert all(x['actual']==x['expected'] for x in frozen_checks.values())
save(evidence/'S01-验收矩阵.json',{'contract':'V2-S01-r2','scope':'data and publication correctness, separate from J1',
    'data_score':90,'data_max':90,'data_evidence':'frozen-cases-recheck.json',
    'data_recheck_mode':'Current independent Python against previous immutable S04 real Spark artifacts; no new Spark for these15cases',
    'publication_score':10,'publication_max':10,'publication_frozen_checks':frozen_checks,
    'correctness_total':100,'correctness_max':100,'J1_score':None,'J1_threshold':6,'J1_max':8,
    'J1_status':'not_run_explicit_user_decision_model0','S06_full_acceptance':False})

timestamps=[]
for filename in ['prepare-sources.log','browser/final/real-browser-final.log']:
    values=[]
    for line in (evidence/filename).read_text(encoding='utf-8').splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        if 'timestamp' in event:values.append(event['timestamp'])
    timestamps.append(values)
start=datetime.fromisoformat(timestamps[0][0]);end=datetime.fromisoformat(timestamps[1][-1])
save(evidence/'trace-timings.json',{
    'source_first_POST_completed_at':start.isoformat(),'final_browser_last_request_at':end.isoformat(),
    'traced_wall_interval_seconds':(end-start).total_seconds(),
    'interval_not_performance':'Includes development, benchmark wait, failed orchestration, screenshots and review; not continuous pipeline or user latency',
    'source_resume_API_and_two_snapshots_seconds':load('S06-验证证据/source-timings.json')['source_api_and_snapshot_seconds'],
    'spark_main_seconds':load('S06-产物/jobs/s06-e2e-main/manifest.json')['elapsed_seconds'],
    'spark_boundary_seconds':load('S06-产物/jobs/s06-e2e-boundary/manifest.json')['elapsed_seconds'],
    'publication_main_process_seconds':load('S06-验证证据/publish-primary-cli.json')['seconds'],
    'publication_boundary_process_seconds':load('S06-验证证据/publish-boundary-cli.json')['seconds'],
    'authenticated_main_API_seconds':next(e['seconds'] for e in proof if e['path']=='offline-analytics/batches/'+publication['primary']),
    'benchmark_full_scope':'Same input -> normalization, relations, aggregates, result files and answer comparison; excludes DB/API/browser',
    'benchmark_evidence':'S06-实验/all-rounds.csv'})
(evidence/'ui-finish-review.md').write_text('''# S06 有限UI审查记录

Fresh reviewer首次全图审查 disposition=fix：唯一P2为趋势轴单位浅色，对比约1.32:1。
补 `yAxis.nameTextStyle.color=#5c7067` 后，reviewer依据最终桌面/390及记录数模式截图作verdict pass：**resolved**，对比约5.04:1。
该结论仅关闭原P2，不是重新做全表通过判断，不构成J1或完整S06验收。
下拉框accessible名称修复及首次反馈已发布均值/四区间补齐，一并在final25个真实浏览器断言核对。
detector对新页面/CSS仅运行一次，输出[]；提示的旧build/spec hero gate属于前置设计记录，没有因S06擅自修复漂移。
原round1失败/round2截图保留，最终批量确认位于browser/final。
''',encoding='utf-8')

modified=subprocess.check_output(['git','diff','--name-only'],text=True,encoding='utf-8').splitlines()
allowed={'DESIGN.md','.impeccable/design.json','analytics/prepare_publication.py','backend/app/services/analytics_artifacts.py',
 'frontend/src/layouts/AppLayout.vue','frontend/src/router/index.ts','frontend/src/views/AnalyticsView.vue','开发相关文档/开发日志/开发操作日志.md'}
decoded=[]
# Ask git for unquoted UTF-8 rather than interpreting octal quoted paths.
decoded=subprocess.check_output(['git','-c','core.quotePath=false','diff','--name-only'],text=True,encoding='utf-8').splitlines()
assert set(decoded)<=allowed,decoded
python_paths=[root/'analytics/prepare_publication.py',root/'analytics/benchmark_s06.py',root/'backend/app/services/analytics_artifacts.py']
python_paths+=list(evidence.rglob('*.py'))
for file in python_paths:ast.parse(file.read_text(encoding='utf-8'),filename=str(file))
jsonfiles=list(v2.glob('S06*.json'))+list((v2/'S06-ODS').rglob('*.json'))+list((v2/'S06-产物').rglob('*.json'))+list((v2/'S06-发布输入').rglob('*.json'))+list((v2/'S06-实验').rglob('*.json'))+list(evidence.rglob('*.json'))
for file in jsonfiles:json.loads(file.read_text(encoding='utf-8'))
link_count=0
for file in [v2/'S06-完成报告.md',v2/'S06-演示与证据索引.md',evidence/'frozen-cases-recheck.md']:
    for target in re.findall(r'\]\(([^)]+)\)',file.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):continue
        target=target.split('#')[0]
        resolved=(file.parent/target).resolve()
        assert resolved.exists() or resolved==(evidence/'final-qa.json').resolve(),(str(file),target)
        link_count+=1
for pattern in [r'Bearer\s+[A-Za-z0-9._-]{30,}',r'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}']:
    for file in evidence.rglob('*'):
        if file.is_file() and file.suffix in ('.json','.log','.md','.py','.cjs'):
            assert not re.search(pattern,file.read_text(encoding='utf-8',errors='replace')),file.name
diff=subprocess.run(['git','diff','--check'],capture_output=True,text=True,encoding='utf-8')
assert diff.returncode==0,diff.stdout
save(evidence/'final-qa.json',{'status':'passed','head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'protected_untracked_local_state':['.rivet/','tmp/'],'modified_tracked_files':decoded,
    'all_existing_changes_within_S06_boundary':True,'old_S03_S04_S05_artifacts_no_diff':True,
    'python_AST_files':len(python_paths),'JSON_files_parsed':len(jsonfiles),'local_markdown_links_checked':link_count,
    'credential_token_patterns_found':0,'git_diff_check_exit_code':diff.returncode,
    'no_dependency_or_config_changes':True,'frontend_build_exit_code':0,'targeted_backend_tests':30,
    'S06_full_acceptance':False,'pending':'Formal J1 by explicit user model0 decision',
    'not_run':['full296backendtests','real_model','million_scale','cluster','S07']})
print(json.dumps({'status':'passed','python_AST_files':len(python_paths),'JSON_files':len(jsonfiles),'links':link_count}))
