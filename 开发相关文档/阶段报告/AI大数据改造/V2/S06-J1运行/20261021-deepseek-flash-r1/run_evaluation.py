"""本次授权的单轮离线J1评价；默认仅检查，加--execute才调用，已有账本禁止重跑。"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from time import perf_counter

HERE = Path(__file__).resolve().parent
V2 = HERE.parent.parent
ROOT = HERE.parents[5]
PREP = V2 / 'S06-J1准备/20261021-r1'
sys.path.insert(0, str(ROOT / 'backend'))

import httpx

from app.ai.client import AIClient
from app.ai.deepseek import DeepSeekProvider
from app.ai.provider import AIClientError, AICompletionRequest, AIMessage, AIMessageRole, AIResponseFormat
from app.core.config import AISettings
from validate_j1_response import validate_response


def now():
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).isoformat()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def preflight():
    authorization = read(HERE / 'authorization.json')
    params = read(HERE / 'parameters.json')
    assert authorization['total_provider_attempt_limit'] == 4
    assert authorization['calibration_attempt_limit'] == 3 and authorization['analysis_attempt_limit'] == 1
    assert authorization['currency_cap_policy'].startswith('用户明确本轮费用不设上限')
    assert params['provider'] == 'deepseek' and params['model'] == 'deepseek-flash'
    assert params['max_retries'] == 0 and params['transport_retries'] == 0
    assert params['reasoning_enabled'] is False and params['max_tokens'] == 1200
    rubric = (V2 / 'S01-评价评分表.md').read_text(encoding='utf-8')
    system = (PREP / 'judge-r2-system.txt').read_text(encoding='utf-8').strip()
    assert system == rubric.split('```text\n', 1)[1].split('\n```', 1)[0]
    settings = AISettings()
    assert settings.ai_provider == 'deepseek' and settings.deepseek_base_url == 'https://api.deepseek.com'
    assert settings.deepseek_api_key is not None, '项目现有DeepSeek密钥未配置'
    requests = {}
    for name in ('G01', 'G02', 'G03', 'analysis'):
        input_obj = read(PREP / f'{name}-input.json')
        user = json.dumps(input_obj, ensure_ascii=False, separators=(',', ':'))
        requests[name] = (input_obj, AICompletionRequest(
            messages=(AIMessage(role=AIMessageRole.SYSTEM, content=system), AIMessage(role=AIMessageRole.USER, content=user)),
            model=params['model'], temperature=params['temperature'], max_tokens=params['max_tokens'],
            response_format=AIResponseFormat.JSON_OBJECT, reasoning_enabled=False,
        ))
    return settings, params, requests


def compute_cost(raw, started_at):
    usage = raw.get('usage', {})
    prompt, output = usage.get('prompt_tokens'), usage.get('completion_tokens')
    hit = usage.get('prompt_cache_hit_tokens')
    miss = usage.get('prompt_cache_miss_tokens')
    if hit is None:
        hit = usage.get('prompt_tokens_details', {}).get('cached_tokens')
    if miss is None and type(prompt) is int and type(hit) is int:
        miss = prompt - hit
    start = datetime.fromisoformat(started_at)
    # 本次授权在夜间执行，跨到高峰或异常使用量时停止，不能套错单价。
    if 9 <= start.hour < 12 or 14 <= start.hour < 18:
        return {'currency': 'CNY', 'amount': None, 'reason': '本轮夜间单价记录不适用于当前时段'}
    if not all(type(n) is int and n >= 0 for n in (prompt, output, hit, miss)) or hit + miss != prompt:
        return {'currency': 'CNY', 'amount': None, 'reason': '原始usage缓存拆分或输出tokens不足以核算'}
    prices = read(HERE / 'pricing-basis.json')['off_peak']
    amount = (Decimal(hit) * Decimal(prices['input_cache_hit']) + Decimal(miss) * Decimal(prices['input_cache_miss']) + Decimal(output) * Decimal(prices['output'])) / Decimal(1000000)
    return {'currency': 'CNY', 'amount': str(amount), 'kind': 'actual_usage_times_official_price_not_account_reconciled', 'price_period': 'off_peak', 'cache_hit_tokens': hit, 'cache_miss_tokens': miss, 'completion_tokens': output, 'basis_ref': 'pricing-basis.json'}


async def execute(settings, params, requests):
    ledger_path = HERE / 'ledger.json'
    if ledger_path.exists():
        raise RuntimeError('已有本轮账本；禁止重跑或自动恢复收费请求，请先审阅实际尝试')
    ledger = {'evaluation_id': 'S06-J1-20261021-deepseek-flash-r1', 'started_at': now(), 'status': 'running', 'provider': 'deepseek', 'model_id': params['model'], 'authorized_attempts': 4, 'currency': 'CNY', 'currency_cap': None, 'currency_cap_policy': 'explicitly_unbounded_by_user', 'attempts': [], 'provider_attempts': 0, 'remaining_authorized_attempts': 4, 'calibration_passed': False, 'calibration_reusable': False, 'analysis_total': None, 'analysis_passed': False, 'cost_from_actual_usage': '0', 'account_reconciled': False}
    write(ledger_path, ledger)
    (HERE / 'raw').mkdir(exist_ok=False)
    active = {}
    captured = {}
    secret = settings.deepseek_api_key.get_secret_value()

    async def capture_request(request):
        active['http_request_events'] += 1
        # 只保存无headers的请求正文；现有Provider负责注入认证，密钥不进入材料。
        body = request.content.decode('utf-8')
        assert secret not in body
        write(HERE / 'raw' / f"{active['input_id']}-request.json", json.loads(body))

    async def capture_response(response):
        body = await response.aread()
        text = body.decode('utf-8', errors='replace')
        redacted = secret in text
        text = text.replace(secret, '[REDACTED]')
        raw_path = HERE / 'raw' / f"{active['input_id']}-response.json"
        raw_path.write_text(text, encoding='utf-8')
        active.update(http_status=response.status_code, raw_response_ref=raw_path.relative_to(HERE).as_posix(), response_redacted=redacted)
        try:
            captured[active['input_id']] = json.loads(text)
        except ValueError:
            captured[active['input_id']] = {}

    calibration = read(PREP / 'calibration-expected.json')['cases']
    limits = httpx.Limits(max_connections=1, max_keepalive_connections=1)
    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=0), limits=limits, follow_redirects=False, event_hooks={'request': [capture_request], 'response': [capture_response]}) as http:
        provider = DeepSeekProvider(http, api_key=settings.deepseek_api_key, base_url=params['base_url'], connect_timeout_seconds=5, request_timeout_seconds=60)
        client = AIClient(provider, total_timeout_seconds=60, max_retries=0, retry_base_delay_seconds=0, max_retry_delay_seconds=0)
        for name in ('G01', 'G02', 'G03', 'analysis'):
            if name == 'analysis' and not ledger['calibration_passed']:
                break
            if ledger['provider_attempts'] >= 4:
                raise RuntimeError('本轮次数耗尽')
            input_obj, request = requests[name]
            write(HERE / 'raw' / f'{name}-input.json', input_obj)
            active = {'attempt_no': ledger['provider_attempts'] + 1, 'input_id': name, 'role': 'judge_calibration' if name != 'analysis' else 'judge_analysis', 'started_at': now(), 'status': 'started', 'http_request_events': 0, 'input_ref': f'raw/{name}-input.json', 'parameters_ref': 'parameters.json', 'model_requested': params['model']}
            ledger['attempts'].append(active)
            ledger['provider_attempts'] += 1
            ledger['remaining_authorized_attempts'] = 4 - ledger['provider_attempts']
            write(ledger_path, ledger)  # Provider开始前记次；异常也保留，不回退次数。
            started = perf_counter()
            gate = None
            try:
                result = await client.complete(request)
                active.update(status='response_received', latency_ms=result.latency_ms, model_returned=result.model, finish_reason=result.finish_reason, usage=result.usage.model_dump(mode='json'))
                result_dump = result.model_dump(mode='json')
                safe_dump = json.loads(json.dumps(result_dump, ensure_ascii=False).replace(secret, '[REDACTED]'))
                write(HERE / 'raw' / f'{name}-provider-result.json', safe_dump)
                parsed = json.loads(result.content)
                write(HERE / 'raw' / f'{name}-parsed.json', parsed)
                expected = next((case for case in calibration if case['calibration_id'] == name), None)
                gate = validate_response(input_obj, parsed, expected)
                if result.finish_reason != 'stop':
                    gate['errors'].append('finish_reason不是stop，保留无效结果')
                    gate['calibration_pass'] = False
                    gate['analysis_pass'] = False
                    gate['status'] = 'invalid'
                write(HERE / 'raw' / f'{name}-validation.json', gate)
                active['validation_ref'] = f'raw/{name}-validation.json'
                active['status'] = gate['status']
            except AIClientError as exc:
                active.update(status='provider_failed', failure_category=exc.category.value)
            except (ValueError, TypeError, KeyError) as exc:
                active.update(status='invalid', failure_type=type(exc).__name__)
            active['latency_ms'] = max(0, round((perf_counter() - started) * 1000))
            active['finished_at'] = now()
            active['cost'] = compute_cost(captured.get(name, {}), active['started_at'])
            if active['cost']['amount'] is not None:
                ledger['cost_from_actual_usage'] = str(Decimal(ledger['cost_from_actual_usage']) + Decimal(active['cost']['amount']))
            else:
                ledger['cost_unknown'] = True
            if name == 'analysis' and gate is not None:
                ledger['analysis_total'] = gate['analysis_total']
                ledger['analysis_passed'] = gate['analysis_pass']
            if gate is None or not gate.get('calibration_pass' if name != 'analysis' else 'analysis_pass') or active['cost']['amount'] is None or active['http_request_events'] != 1:
                ledger['status'] = 'stopped_calibration_failed' if name != 'analysis' else 'analysis_not_passed'
                ledger['stop_input_id'] = name
                write(ledger_path, ledger)
                print(json.dumps({'input_id': name, 'status': active['status'], 'calibration_pass': gate.get('calibration_pass') if gate else False, 'analysis_total': gate.get('analysis_total') if gate else None, 'stop': True}, ensure_ascii=False), flush=True)
                break
            if name == 'G03':
                ledger['calibration_passed'] = True
                ledger['calibration_reusable'] = True
                ledger['calibration_reuse_condition'] = '同provider/精确模型版本/提示词/参数/校准输入不变，S08可复用；模型后端版本变更需重新校准'
            if name == 'analysis':
                ledger.update(analysis_total=gate['analysis_total'], analysis_passed=gate['analysis_pass'], status='completed' if gate['analysis_pass'] else 'analysis_not_passed')
            write(ledger_path, ledger)
            print(json.dumps({'input_id': name, 'status': active['status'], 'calibration_pass': gate['calibration_pass'], 'analysis_total': gate['analysis_total'], 'stop': False}, ensure_ascii=False), flush=True)
    ledger['finished_at'] = now()
    ledger['no_automatic_retry'] = True
    ledger['analysis_attempts'] = sum(a['role'] == 'judge_analysis' for a in ledger['attempts'])
    ledger['calibration_attempts'] = sum(a['role'] == 'judge_calibration' for a in ledger['attempts'])
    ledger['total_prompt_tokens'] = sum(a.get('usage', {}).get('prompt_tokens') or 0 for a in ledger['attempts'])
    ledger['total_completion_tokens'] = sum(a.get('usage', {}).get('completion_tokens') or 0 for a in ledger['attempts'])
    ledger['S06_complete'] = ledger['calibration_passed'] and ledger['analysis_passed'] and not ledger.get('cost_unknown', False)
    write(ledger_path, ledger)
    print(json.dumps({k: ledger[k] for k in ('status', 'provider_attempts', 'remaining_authorized_attempts', 'calibration_passed', 'analysis_total', 'cost_from_actual_usage', 'S06_complete')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        settings, params, requests = preflight()
        if args.execute:
            asyncio.run(execute(settings, params, requests))
        else:
            print(json.dumps({'status': 'preflight_passed', 'model': params['model'], 'inputs': list(requests), 'key_present': True, 'key_value_printed': False, 'provider_attempts': 0}, ensure_ascii=False))
    except Exception as exc:
        # 配置异常不打印可能含环境输入的异常正文；实际Provider尝试已在账本先记。
        print(json.dumps({'status': 'runner_stopped', 'error_type': type(exc).__name__}, ensure_ascii=False))
        sys.exit(1)
