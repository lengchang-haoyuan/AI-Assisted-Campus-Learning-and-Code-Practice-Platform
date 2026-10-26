"""只读核对judge-r4说明、原始失败及次数缺口；不导入应用或读取凭证。"""

import ast
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent.parent
PREP = HERE.parent / '20261021-r1'
OLD = V2 / 'S06-J1运行/20261021-deepseek-flash-r2-judge-r3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    checks = []

    def check(condition, label):
        if not condition:
            raise ValueError(label)
        checks.append(label)

    text = (HERE / 'judge-r4-system.txt').read_text(encoding='utf-8')
    base = (OLD / 'judge-r3-system.txt').read_text(encoding='utf-8')
    check((HERE / 'judge-r4-system.txt').read_bytes().startswith((OLD / 'judge-r3-system.txt').read_bytes()), 'judge-r3原文字节前缀保留')
    addition = text[len(base):]
    requirements = ['被评对象是data.candidate_feedback', 'student_code与reference是核验材料', '先定位候选反馈', '不得把你自行发现', '不能因此自动填true', '缺少候选反馈', 'abstain', '置null', '支持还是反驳', '不得仅凭某个分数或另一布尔字段']
    for phrase in requirements:
        check(phrase in addition, f'新增说明覆盖:{phrase}')
    check(not re.search(r'G0[123]|expected_status|expected_evidence_valid|expected_actionability_score', addition), '新说明不泄露校准ID或预期字段')
    fixed = read(V2 / 'S01-AI固定模板与评价案例.json')
    expected = read(PREP / 'calibration-expected.json')
    check(expected['cases'] == fixed['raters']['calibration_cases'], '冻结预期仍与S01-r2一致')
    raw = read(OLD / 'raw/G02-parsed.json')
    validation = read(OLD / 'raw/G02-validation.json')
    check(raw['criterion_evidence'][0]['evidence_valid'] is True, '旧G02原始true未改')
    check(expected['cases'][1]['expected_evidence_valid'] is False, '冻结G02预期false未改')
    check(not validation['calibration_pass'] and not validation['expected_matches']['expected_evidence_valid'], '旧失败保持失败而非改评分器通过')
    gate = (OLD / 'validate_j1_response.py').read_text(encoding='utf-8')
    ast.parse(gate)
    check('type(actual) is type(expected)' in gate, '既有严格类型与冻结值比较保留')
    plan = read(HERE / 'execution-plan.json')
    # 重演授权前准备快照，仅核对当时已有两轮；不把随后judge-r4成功运行倒填到旧计划。
    ledgers = [read(V2 / 'S06-J1运行' / name / 'ledger.json') for name in ('20261021-deepseek-flash-r1', '20261021-deepseek-flash-r2-judge-r3')]
    consumed = sum(item['provider_attempts'] for item in ledgers)
    check(consumed == plan['actual_stage_attempts'] == 3, '准备时前两轮累计3次仍计入旧失败')
    check(plan['current_authorized_stage_attempt_cap'] - consumed == plan['remaining_authorized_attempts'] == 2, '现授权上限5/剩余2')
    check(sum(plan['new_round_required'][k] for k in ('calibration', 'analysis')) == plan['new_round_required']['total'] == 4, '新轮完整3校准加1正式')
    check(4 - plan['remaining_authorized_attempts'] == plan['additional_calibration_attempts_required'] == 2, '需要新增2次校准而非挪用角色')
    check(plan['proposed_stage_attempt_cap_not_yet_authorized'] == 7 and not plan['execution_authorized'], '累计7仅方案尚未授权')
    sizes = {}
    for name in ('G01', 'G02', 'G03', 'analysis'):
        inp = read(PREP / f'{name}-input.json')
        user = json.dumps(inp, ensure_ascii=False, separators=(',', ':'))
        sizes[name] = {'system_chars': len(text.strip()), 'user_chars': len(user), 'total_chars': len(text.strip()) + len(user)}
        check(len(text.strip()) <= 12000 and len(user) <= 12000 and len(text.strip()) + len(user) <= 24000, f'{name}既有消息字符上限')
    for relative in plan['input_refs'] + [plan['expected_ref'], plan['validator_ref']]:
        check((HERE / relative).resolve().is_file(), f'执行计划引用存在:{relative}')
    check(plan['model_calls_this_preparation'] == 0 and plan['cost_this_preparation'] == '0', '准备零模型零费用')
    ast.parse(Path(__file__).read_text(encoding='utf-8'))
    print(json.dumps({'status': 'passed', 'scope': 'offline_prompt_contract_checks_not_model_calibration', 'checks_count': len(checks), 'checks': checks, 'message_sizes': sizes, 'model_calls': 0, 'calibration_status': 'not_run', 'execution_authorized': False, 'additional_calibration_attempts_required': 2, 'S06_complete': False}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
