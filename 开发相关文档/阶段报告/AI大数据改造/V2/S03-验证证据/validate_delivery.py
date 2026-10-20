import json,sys,os,ctypes,subprocess,zipfile,copy
from pathlib import Path
from ctypes import wintypes
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from analytics.prepare_samples import generate_scale,FIXTURE
from analytics.snapshot_files import read_snapshot,write_json
from analytics.fixture_answers import calculate,assert_subset
TEMP=Path(os.environ['TEMP'])/'ScholarHub-S03-20261020'
OUT=ROOT/'开发相关文档/阶段报告/AI大数据改造/V2/S03-验证证据'
SAMPLES=OUT.parent/'S03-样本'
f=json.loads(FIXTURE.read_text(encoding='utf8'))
repeat=TEMP/'reproducibility'
if not repeat.exists():
 repeat.mkdir();generate_scale(f,repeat)
name='synthetic-10000-seed-20261020-v1'
original=SAMPLES/'snapshots'/name
regenerated=repeat/'snapshots'/name
same=all(p.read_bytes()==(regenerated/p.name).read_bytes() for p in original.glob('*.jsonl'))
assert same
m,t=read_snapshot(original)
for table,fields in f['schema'].items():
 for row in t[table]:assert set(row)=={field['field'] for field in fields}
# 对所有主体核算独立答案，保存各主体三类指标，规模对照不依赖Spark输出。
answers={}
for owner in range(1000000,1000100):answers[str(owner)]=calculate(t,dict(m,owner_user_id=owner))
expected=json.loads((SAMPLES/f'{name}-expected.json').read_text(encoding='utf8'))
observed={'records':sum(a['records']['valid_unique_rows'] for a in answers.values()),'known_minutes':sum(a['records']['known_minutes'] for a in answers.values()),'missing_duration_count':sum(a['records']['missing_duration_count'] for a in answers.values()),'known_zero_count':sum(a['records']['known_zero_count'] for a in answers.values()),'tasks':sum(a['tasks']['total'] for a in answers.values()),'cohort_count':sum(a['topic']['cohort_count'] for a in answers.values()),'confirmed_count':sum(a['topic']['confirmed_count'] for a in answers.values()),'revised_count':sum(a['topic']['revised_count'] for a in answers.values())}
for k,v in observed.items():assert expected[k]==v,(k,v,expected[k])
# raw_rows/duplicates是多主体文件物理计数，不可加总为主体指标。
for a in answers.values():
 a['records'].pop('raw_rows');a['records'].pop('exact_duplicates')
answer_path=SAMPLES/f'{name}-subject-answers.json'
if not answer_path.exists():write_json(answer_path,answers)
else:assert json.loads(answer_path.read_text(encoding='utf8'))==answers
class MemoryCounters(ctypes.Structure):
 _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
mem=MemoryCounters();mem.cb=ctypes.sizeof(mem)
ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(MemoryCounters),wintypes.DWORD]
ok=ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(mem),mem.cb)
assert ok
write_json(OUT/'scale-validation.json',{'same_seed_source_files_byte_identical':same,'jsonl_files':len(list(original.glob('*.jsonl'))),'field_whitelist_checked':True,'independent_100_subject_answer_matches_generator_counts':observed,'peak_working_set_bytes':mem.PeakWorkingSetSize,'memory_method':'Windows GetProcessMemoryInfo PeakWorkingSetSize; includes replay and independent 100-subject calculations; not Spark RSS','python':sys.version,'unrun_scales':[100000,1000000],'spark_runs':0})
with zipfile.ZipFile(TEMP/'protected-source.zip') as z:
 changed=[n for n in z.namelist() if (ROOT/n).read_bytes()!=z.read(n)]
 assert not changed
write_json(OUT/'protection-check.json',{'baseline_source_files':350,'baseline_bytes_unchanged':True,'new_sources':['backend/scripts/export_ods_snapshot.py','backend/tests/test_ods_snapshot.py','analytics/__init__.py','analytics/snapshot_files.py','analytics/fixture_answers.py','analytics/prepare_samples.py'],'old_diff_unchanged':(TEMP/'source-diff-before.patch').read_bytes()==subprocess.check_output(['git','diff','--','frontend','backend']),'business_application_changed':False})
print(json.dumps({'replay_identical':same,'observed':observed,'peak_working_set_bytes':mem.PeakWorkingSetSize},ensure_ascii=False))

