import json
from pathlib import Path
from analytics.spark_job import make_session
from analytics.snapshot_files import write_json
root=Path('/home/administrator/scholarhub-analytics/s04-20261020');spark=make_session();spark.sparkContext.setLogLevel('ERROR')
result={};schemas={}
try:
 for job,record_n,task_n,cohort_n,minutes,missing in [('v2-controlled',4,4,3,75,2),('v1-scale',10000,2500,100,421978,2000)]:
  result[job]={}
  for name,key,n in [('record_facts','id',record_n),('task_facts','id',task_n),('cohort_facts','submission_id',cohort_n)]:
   df=spark.read.parquet(str(root/'jobs'/job/'dwd'/name));df.createOrReplaceTempView('fact')
   row=spark.sql(f'SELECT count(*) n,count(DISTINCT {key}) distinct_keys,count(DISTINCT snapshot_id) snapshots,count(DISTINCT job_id) jobs FROM fact').first()
   assert row.n==row.distinct_keys==n and row.snapshots==row.jobs==1,(job,name,row)
   result[job][name]=row.asDict()
   schemas[name]=df.schema.jsonValue()
   if name=='record_facts':
    values=spark.sql('SELECT sum(duration_minutes) minutes,sum(CASE WHEN duration_minutes IS NULL THEN 1 ELSE 0 END) missing FROM fact').first()
    assert (values.minutes,values.missing)==(minutes,missing)
    result[job]['records_values']=values.asDict()
  for name in ['ads_records','ads_tasks','ads_topic','ads_daily']:
   df=spark.read.parquet(str(root/'jobs'/job/'ads'/name));schemas[name]=df.schema.jsonValue()
  schemas['ai_requests_aux']=spark.read.parquet(str(root/'jobs'/job/'dwd/ai_requests_aux')).schema.jsonValue()
 write_json(root/'parquet-readback.json',result);write_json(root/'DWD-ADS-schemas.json',schemas)
 print(json.dumps({'parquet_readback':'passed','facts':result}))
finally:spark.stop()
