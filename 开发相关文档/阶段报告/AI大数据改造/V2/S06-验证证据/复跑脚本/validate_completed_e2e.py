"""Recheck existing immutable real Spark outputs against current-cutoff expectations."""
import json
from pathlib import Path
from analytics.spark_job import V2, load_input
from analytics.fixture_answers import calculate
from analytics.verify_s04 import compare
from analytics.snapshot_files import write_json

results = {}
for job, snapshot, owner, filename in [
    ('s06-e2e-main','s06-e2e-owner3-20261021',3,'main-independent-frozen-answer.json'),
    ('s06-e2e-boundary','s06-e2e-owner4-20261021',4,'boundary-independent-frozen-answer.json'),
]:
    manifest, tables = load_input(V2/'S06-ODS/snapshots'/snapshot)
    expected = json.loads((V2/'S06-验证证据'/filename).read_text())
    if owner == 4:
        # S01: overdue uses source_cutoff's business date, not the end of window.
        # Current cutoff Shanghai Oct21; the one pending Oct20 task is overdue.
        pending = [t for t in tables['daily_tasks'] if t['status'] in ('pending','in_progress')]
        assert len(pending) == 1 and pending[0]['scheduled_date'] == '2026-10-20'
        assert manifest['source_cutoff'].startswith('2026-10-21')
        expected['tasks']['overdue_unfinished'] = 1
        expected['daily'][0]['overdue_unfinished'] = 1
        write_json(V2/'S06-验证证据/boundary-independent-frozen-answer-r2.json', expected)
    jobdir = V2/'S06-产物/jobs'/job
    actual = json.loads((jobdir/'ads/answers.json').read_text())[str(owner)]
    reference = calculate(tables, manifest)
    compare(actual, reference)
    compare(actual, expected)
    quality = json.loads((jobdir/'quality.json').read_text())
    jm = json.loads((jobdir/'manifest.json').read_text())
    assert jm['state'] == 'computed' and quality['fatal_errors'] == 0 and quality['reconciled']
    refpath = V2/'S06-验证证据'/f'{job}-python-answer.json'
    if refpath.exists():
        compare(json.loads(refpath.read_text()), reference)
    else:
        write_json(refpath, reference)
    results[job]={'job_id':job,'snapshot_id':snapshot,'owner_user_id':owner,
        'independent_answers_matched':True,'frozen_answers_matched':True,
        'rule_version':jm['rule_version'],'metric_version':jm['metric_version'],
        'spark_elapsed_seconds':jm.get('elapsed_seconds'), 'daily_rows':len(actual['daily'])}
write_json(V2/'S06-数据验收.json',{'stage':'S06','contract':'V2-S01-r2',
    'scope':'Data correctness only; J1 remains pending',
    'all_frozen_data_assertions_passed':True,'jobs':results,
    'boundary_expectation_correction':'S03 cutoff Oct20 -> S06 cutoff Oct21; pending Oct20 now overdue1, source/rules unchanged; original failed check retained',
    'J1':'pending_by_user_decision','model_calls':0})
write_json(V2/'S06-发布清单.json',{'stage':'S06','contract':'V2-S01-r2',
    'authorization':'2026-10-21 explicit user approval: two validated offline jobs',
    'primary':{'job_id':'s06-e2e-main','relative_path':'S06-产物/jobs/s06-e2e-main'},
    'boundary':{'job_id':'s06-e2e-boundary','relative_path':'S06-产物/jobs/s06-e2e-boundary'}})
print(json.dumps({'status':'passed','jobs':results,'model_calls':0}))
