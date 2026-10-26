"""只读核对固定文件与 J1 准备材料；无网络、Provider、DB 或 Spark 入口。"""

import ast
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent.parent
checks = []


def check(condition, label):
    if not condition:
        raise ValueError(label)
    checks.append(label)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def pointer(value, path):
    for part in path.lstrip('/').split('/') if path else []:
        key = part.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def subset(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(subset(a, b) for a, b in zip(expected, actual))
    return type(expected) is type(actual) and expected == actual


def normalized_daily(rows):
    names = {'metric_date': 'date', 'task_total': 'tasks', 'cohort_count': 'cohort', 'revised_count': 'revised', 'confirmed_count': 'confirmed'}
    return [{names.get(k, k): v for k, v in row.items()} for row in rows]


def main():
    sources = read(HERE / 'source-numbers.json')
    analysis = read(HERE / 'analysis-input.json')
    rubric_source = (V2 / 'S01-评价评分表.md').read_text(encoding='utf-8')
    ai = read(V2 / 'S01-AI固定模板与评价案例.json')
    check(sources['contract_id'] == ai['contract_id'] == 'V2-S01-r2', '批准契约绑定r2')
    prompt = (HERE / 'judge-r2-system.txt').read_text(encoding='utf-8').strip()
    check(prompt == rubric_source.split('```text\n', 1)[1].split('\n```', 1)[0], 'judge-r2提示词逐字沿用')
    pub = read(V2 / 'S06-发布结果.json')
    index = read(V2 / 'S06-输入索引.json')
    for alias, pub_key in [('main', 'primary'), ('boundary', 'boundary')]:
        binding = sources['bindings'][alias]
        job = read(V2 / f"S06-产物/jobs/{binding['job_id']}/manifest.json")
        ods = read(V2 / f"S06-ODS/snapshots/{binding['snapshot_id']}/manifest.json")
        payload = read(V2 / f"S06-发布输入/{binding['job_id']}/payload.json")
        controlled = next(s for s in index['controlled_snapshots'] if s['snapshot_id'] == binding['snapshot_id'])
        for key in ('owner_user_id', 'snapshot_id', 'job_id', 'dataset_kind', 'source_cutoff', 'period_start', 'period_end', 'business_timezone', 'schema_version', 'metric_version', 'rule_version'):
            check(binding[key] == job[key] == payload[key], f'{alias}身份:{key}')
            if key in ods:
                check(binding[key] == ods[key], f'{alias}ODS:{key}')
        check(binding['source_cutoff'] == controlled['source_cutoff'], f'{alias}输入索引cutoff')
        check(binding['input_batch_id'] == ods['batch_id'] == job['input_batch_id'], f'{alias}输入batch独立绑定')
        check(binding['batch_id'] == pub[pub_key]['batch_id'] != binding['input_batch_id'], f'{alias}发布batch绑定且非输入batch')
        check(pub[pub_key]['state'] == 'completed', f'{alias}发布状态完成')
        for key in ('source_cutoff', 'schema_version', 'metric_version', 'rule_version', 'period_start', 'period_end', 'business_timezone'):
            check(binding[key] == pub[pub_key]['details'][key], f'{alias}发布详情:{key}')
        check(pub[pub_key]['details']['source']['snapshot_id'] == binding['snapshot_id'], f'{alias}发布来源快照')
        check(pub[pub_key]['details']['source']['job_id'] == binding['job_id'], f'{alias}发布来源job')
    check(sources['bindings']['main']['batch_id'] == 'b96ea63e-419e-4293-b724-d1ce59bd85ba', '指定主批')
    check(sources['bindings']['boundary']['batch_id'] == '3217db64-1302-4722-a483-c3b1ad7b980f', '指定边界批')
    evidence_count = 0
    for key, item in sources['evidence'].items():
        check(item['binding'] in sources['bindings'], f'{key}主体引用')
        for alias_key in item.get('alias_keys', []):
            check(alias_key in sources['evidence'], f'{key}别名:{alias_key}')
        for ref in item.get('refs', []):
            path = (V2 / ref['file']).resolve()
            check(path.is_relative_to(V2) and path.is_file(), f'{key}文件存在:{ref["file"]}')
            value = pointer(read(path), ref['pointer'])
            evidence_count += 1
            if 'fact_pointer' in item:
                expected = pointer(sources, item['fact_pointer'])
                if item['fact_pointer'].endswith('/daily'):
                    value = normalized_daily(value)
                check(subset(expected, value), f'{key}独立答案/ADS/载荷/发布详情:{ref["pointer"]}')
    facts = sources['facts']
    check([facts['main']['records'][k] for k in ('known_minutes', 'valid_unique_rows', 'known_duration_count', 'missing_duration_count')] == [90, 5, 3, 2], '主批90/5/3/2')
    check([facts['main']['tasks'][k] for k in ('completed', 'total', 'cancelled', 'overdue_unfinished')] == [2, 4, 1, 1], '主任务2/4取消1逾期1')
    check([facts['main']['topic'][k] for k in ('cohort_count', 'revised_count', 'confirmed_count', 'first_pass_confirmed_count', 'revised_confirmed_count', 'pending_latest_count', 'first_review_covered')] == [3, 1, 2, 1, 1, 1, 2], '主群组3/修订1/确认2/首次1/修订后1/待评1/反馈2')
    check([facts['boundary']['tasks'][k] for k in ('completed', 'total', 'overdue_unfinished')] == [199, 200, 1], '边界199/200逾期1')
    for alias in ('main', 'boundary'):
        for rates in [facts[alias]['tasks']['completion_rate']] + [facts[alias]['topic'][k] for k in ('revised_rate', 'confirmation_rate', 'revised_confirmation_rate')]:
            percent = None if rates['denominator'] == 0 else str((Decimal(rates['numerator']) * 100 / rates['denominator']).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP))
            check(rates['percent'] == percent, f'{alias}冻结比例:{rates["numerator"]}/{rates["denominator"]}')
    cutoff = datetime.fromisoformat(sources['bindings']['boundary']['source_cutoff'].replace('Z', '+00:00')).astimezone(timezone(timedelta(hours=8))).date()
    boundary_rows = [json.loads(line) for line in (V2 / 'S06-ODS/snapshots/s06-e2e-owner4-20261021/daily_tasks.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    overdue = sum(row['status'] in ('pending', 'in_progress') and datetime.fromisoformat(row['scheduled_date']).date() < cutoff for row in boundary_rows)
    check(overdue == facts['boundary']['tasks']['overdue_unfinished'] == 1, '边界既有ODS与本批cutoff公式')
    old = read(V2 / 'S06-验证证据/boundary-independent-frozen-answer.json')
    check(old['tasks']['overdue_unfinished'] == 0, '旧失败预期0仍保留')
    cleanup = read(V2 / 'S06-验证证据/cleanup-final-state.json')
    check(cleanup['deleted_only_record_id'] == 8 and [e['status'] for e in cleanup['API_events']] == [204, 404] and cleanup['snapshot_remains_immutable_90_minutes'], '仅引用旧清理ID8/90分钟保留')
    artifact = (HERE / '解释稿-v1.md').read_text(encoding='utf-8')
    explanation = artifact.split('<!-- analysis-text-start -->\n', 1)[1].split('<!-- analysis-text-end -->', 1)[0].strip()
    data = analysis['data']
    check(data['artifact_id'] == 'S06-analysis-b96ea63e-v1' and data['text_version'] == '1.0', '解释artifact及版本')
    check(data['explanation'] == explanation, '待评文本与固定解释稿逐字一致')
    check(data['bindings'] == sources['bindings'] and data['source_numbers'] == facts, '正式输入同批数字与身份')
    cited = set(re.findall(r'\[([MB]-[a-z]+|cleanup)\]', explanation))
    check(cited <= data['source_refs'].keys(), '解释稿全部引用键存在')
    for key, value in data['source_refs'].items():
        check(value == sources['evidence'][key], f'正式引用:{key}')
        for alias_key in value.get('alias_keys', []):
            check(alias_key in data['source_refs'], f'正式引用别名可解析:{alias_key}')
    for chart in data['chart_numbers']:
        for path in chart['facts']:
            check(pointer(facts, path) is not None, f'四图数字路径:{path}')
    expected_dims = ['problem_cohort', 'numeric_evidence', 'patterns_counterexamples', 'conclusion_boundary']
    check([d['dimension_id'] for d in data['topic_rubric']] == expected_dims, '四维结构无重复无缺失')
    for dim in data['topic_rubric']:
        check(list(dim['scores']) == ['0', '1', '2'], f'{dim["dimension_id"]}分值范围0至2')
        check(f'| {dim["name"]} | ' + ' | '.join(dim['scores'].values()) + ' |' in rubric_source, f'{dim["dimension_id"]}评分表逐字一致')
    expected = read(HERE / 'calibration-expected.json')
    check(expected['cases'] == ai['raters']['calibration_cases'] and not expected['send_to_judge'], '校准预期逐字保留且不发送')
    q05 = next(case for case in ai['cases'] if case['case_id'] == 'Q05')
    message_sizes = {}
    for name in ['G01', 'G02', 'G03', 'analysis']:
        entry = read(HERE / f'{name}-input.json')
        if name != 'analysis':
            d = entry['data']
            frozen = next(c for c in expected['cases'] if c['calibration_id'] == name)
            check(entry['mode'] == 'feedback' and d['case_id'] == name and d['source_case_id'] == 'Q05', f'{name}身份绑定')
            check(d['student_code'] == q05['student_code'] and d['candidate_feedback'] == frozen['candidate_feedback'], f'{name}代码反馈沿用冻结材料')
            check(d['reference'] == {k: q05[k] for k in ('reference_label', 'reference_criteria', 'reference_issues', 'reference_action')}, f'{name}参考标签不变')
            check(d['criterion_ids'] == ['C01'] and set(d['rubric']) == {'0', '1', '2', '3'}, f'{name}criterion与0至3结构')
            check(not any(k.startswith('expected_') for k in d), f'{name}不发送校准预期')
        user = json.dumps(entry, ensure_ascii=False, separators=(',', ':'))
        message_sizes[name] = {'system_chars': len(prompt), 'user_chars': len(user), 'total_chars': len(prompt) + len(user)}
        check(len(user) <= 12000 and len(prompt) + len(user) <= 24000, f'{name}现有AIMessage字符上限')
    contract = read(HERE / 'response-contract.json')
    props = contract['analysis']['properties']
    check(props['artifact_id']['const'] == data['artifact_id'], '响应artifact绑定')
    dims = props['dimensions']
    check(dims['minItems'] == dims['maxItems'] == 4 and dims['items']['properties']['dimension_id']['enum'] == expected_dims, '响应四维集合结构')
    score = dims['items']['properties']['score']
    check(score['type'] == ['integer', 'null'] and score['minimum'] == 0 and score['maximum'] == 2, '响应维度0至2与未评分null')
    fbscore = contract['feedback']['properties']['actionability_score']
    check(fbscore['minimum'] == 0 and fbscore['maximum'] == 3, '响应校准0至3范围')
    check(props['status']['enum'] == ['scored', 'abstain', 'invalid'], '三种裁判状态保留')
    ledger = read(HERE / 'budget-ledger.json')
    authorization = ledger['authorization']
    check(authorization['provider_id'] is None and authorization['model_id'] is None and authorization['input_permission'] is None, '精确模型及输入许可未擅自选择')
    check(authorization['total_attempts'] == 0 and authorization['total_currency_cap'] == '0', '实际授权调用0费用0')
    check(ledger['proposed_this_stage']['total_provider_attempts'] == 4 and ledger['proposed_this_stage']['total_output_token_cap'] == 4800, '本阶段计划3加1及4800输出上限')
    check(sum(v for k, v in ledger['cross_stage_plan_not_permission'].items() if k != 'total') == ledger['cross_stage_plan_not_permission']['total'] == 36, '跨阶段36计划且校准只计一次')
    check(ledger['actual']['provider_attempts'] == 0 and ledger['actual']['attempts'] == [] and ledger['actual']['spent'] == '0', '账本无实际尝试无费用')
    check(ledger['proposed_configuration_not_authorized']['max_retries'] == 0 and not ledger['calibration']['reusable_now'], '评价重试0且当前无可复用校准')
    result = read(HERE / 'not-run.json')
    check(result['analysis_total'] is None and result['calibration_passed'] is None and result['raw_responses'] == [] and not result['S06_complete'], '未运行不补分数或通过')
    # 仅检查本轮准备脚本语法与导入，未导入应用或执行任何材料内代码。
    tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    check(set(imports) <= {'ast', 'json', 're', 'sys', 'datetime', 'decimal', 'pathlib'}, '准备检查脚本仅标准库白名单')
    combined = '\n'.join(p.read_text(encoding='utf-8-sig') for p in HERE.iterdir() if p.suffix in ('.json', '.md', '.txt', '.py'))
    check(not re.search(r'(?i)(?:sk-[A-Za-z0-9]{16,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|Bearer\s+[A-Za-z0-9._-]{20,})', combined), '本轮材料常见令牌模式检查')
    output = {'status': 'passed', 'scope': 'local_preparation_only_not_J1', 'checks_count': len(checks), 'checks': checks, 'resolved_file_pointers': evidence_count, 'message_sizes': message_sizes, 'model_calls': 0, 'J1_calibration': 'not_run', 'J1_analysis': 'not_run', 'S06_complete': False}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, IndexError, TypeError, OSError) as exc:
        print(json.dumps({'status': 'failed', 'reason': str(exc), 'checks_completed': len(checks), 'model_calls': 0}, ensure_ascii=False))
        sys.exit(1)
