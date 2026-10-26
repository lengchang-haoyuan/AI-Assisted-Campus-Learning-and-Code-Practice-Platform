"""S06 fixed ODS -> real Spark -> independent frozen checks; no database."""
import json
import time
from pathlib import Path
from analytics.spark_job import V2, make_session, load_input, run_job
from analytics.fixture_answers import calculate, assert_subset
from analytics.verify_s04 import compare
from analytics.snapshot_files import write_json

def write_frozen(path, value):
    if path.exists():
        assert json.loads(path.read_text()) == value
    else:
        write_json(path, value)

root = V2 / 'S06-产物'
root.mkdir(parents=True, exist_ok=True)
expected = json.loads((V2/'S03-验证证据/baseline-independent-answer.json').read_text())
expected['records'].update(raw_rows=5, valid_unique_rows=5, known_minutes=90,
                           known_duration_count=3, ordinary_count=3)
expected['daily'][1].update(records=4, known_minutes=60, known_duration_count=2)
write_frozen(V2/'S06-验证证据/main-independent-frozen-answer.json', expected)
boundary = json.loads((V2/'S03-验证证据/boundary-independent-answer.json').read_text())
write_frozen(V2/'S06-验证证据/boundary-independent-frozen-answer.json', boundary)
all_started = time.perf_counter()
spark = make_session()
spark.sparkContext.setLogLevel('ERROR')
startup = time.perf_counter()-all_started
results = {}
try:
    for job, snapshot, owner, frozen in [
        ('s06-e2e-main', 's06-e2e-owner3-20261021', 3, expected),
        ('s06-e2e-boundary', 's06-e2e-owner4-20261021', 4, boundary),
    ]:
        source = V2/'S06-ODS/snapshots'/snapshot
        started = time.perf_counter()
        final, answers, metadata = run_job(spark, source, root, job)
        spark_seconds = time.perf_counter()-started
        manifest, tables = load_input(source)
        reference_started = time.perf_counter()
        reference = calculate(tables, manifest)
        reference_seconds = time.perf_counter()-reference_started
        actual = answers[str(owner)]
        compare(actual, reference)
        compare(actual, frozen)
        write_json(V2/'S06-验证证据'/f'{job}-python-answer.json', reference)
        results[job] = {'job_id':job, 'snapshot_id':snapshot, 'owner_user_id':owner,
            'independent_answers_matched':True, 'frozen_answers_matched':True,
            'spark_seconds':spark_seconds, 'python_reference_seconds':reference_seconds,
            'output':str(final), 'rule_version':'quality-1.0', 'metric_version':'learning-process-1.0'}
        print(json.dumps(results[job]), flush=True)
finally:
    spark.stop()
write_json(V2/'S06-数据验收.json', {
    'stage':'S06', 'contract':'V2-S01-r2', 'scope':'data correctness only; not J1 explanation scoring',
    'all_frozen_data_assertions_passed':True, 'jobs':results,
    'spark_version':spark.version, 'startup_seconds':startup,
    'whole_job_seconds':time.perf_counter()-all_started, 'model_calls':0,
    'J1':'pending_by_user_decision'})
write_json(V2/'S06-发布清单.json', {
    'stage':'S06', 'contract':'V2-S01-r2',
    'authorization':'2026-10-21 explicit user approval: two validated offline jobs',
    'primary':{'job_id':'s06-e2e-main','relative_path':'S06-产物/jobs/s06-e2e-main'},
    'boundary':{'job_id':'s06-e2e-boundary','relative_path':'S06-产物/jobs/s06-e2e-boundary'}})
print('S06_DATA_CHECKS_PASSED', flush=True)
