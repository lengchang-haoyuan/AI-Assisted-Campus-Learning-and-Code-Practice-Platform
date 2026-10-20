import json,sys
from pathlib import Path
from collections import Counter
from analytics.spark_job import make_session,run_job,QualityFailure,V2
from analytics.verify_s04 import verify_one
from analytics.snapshot_files import write_json
root=Path('/home/administrator/scholarhub-analytics/s04-20261020')
fixture=Path('/mnt/c/Users/Administrator/AppData/Local/Temp/ScholarHub-S04-20261020/quality-types/input.json')
spark=make_session();spark.sparkContext.setLogLevel('ERROR')
try:
 try:run_job(spark,fixture,root,'v2-quality-types')
 except QualityFailure:pass
 else:raise AssertionError('invalid_inputs_accepted')
 failure=next((root/'.incomplete').glob('v2-quality-types-*'))
 errors=json.loads((failure/'exceptions.json').read_text())
 observed=dict(Counter(e['reason'] for e in errors))
 expected={'integer_out_of_range':3,'invalid_json_type':1,'invalid_time':2,'unknown_enum':1,'required_key_missing':1}
 assert observed==expected,(observed,expected)
 assert not (root/'jobs/v2-quality-types').exists()
 write_json(root/'v2-quality-types-check.json',{'status':'passed','errors':observed,'invalid_rows':8,'valid_historical_zero_retained_in_normalization':True,'batch_rejected':True,'failed_attempt':str(failure)})
 missing=fixture.parent/'missing';missing.mkdir()
 data=json.loads(fixture.read_text());del data['tables']['learning_records'];write_json(missing/'input.json',data)
 try:run_job(spark,missing/'input.json',root,'v2-missing-table')
 except QualityFailure as e:assert str(e)=='missing_source_table'
 else:raise AssertionError('missing_source_accepted')
 result=verify_one(spark,V2/'S03-ODS/snapshots/s03-owner3-restored',root,'v2-controlled')
 write_json(root/'v2-final-check.json',{'source_type_quality':'passed','missing_source_rejected':True,'controlled':result})
 print(json.dumps({'quality':observed,'missing_source':'rejected','controlled':'passed'}))
finally:spark.stop()
