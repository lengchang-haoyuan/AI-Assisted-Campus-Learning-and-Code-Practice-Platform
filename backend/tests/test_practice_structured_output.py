"""仅MockTransport/Fake验证Schema协议；不读真实凭证、不请求模型。"""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import re
import unittest

import httpx
from pydantic import SecretStr, ValidationError

from app.agents.base import AgentOutputValidationError
from app.ai.client import AIClient
from app.ai.deepseek import DeepSeekProvider
from app.ai.provider import AIClientError, AICompletionRequest, AIFailureCategory, AIMessage, AIMessageRole, AIResponseFormat
from app.practice.review import PracticeReviewDraft
from tests.test_practice_agent import guidance_output, make_context
from tests.test_practice_review import make_review_agent, review_draft, review_input


def schema_request():
    agent, _ = make_review_agent(review_draft())
    return agent._build_completion_request(make_context(), agent.validate_input(review_input()))


def response_body():
    return {
        "model": "deepseek-flash", "status": "completed", "error": None,
        "incomplete_details": None,
        "output": [{"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": '{"synthetic":true}'},
        ]}],
        "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30,
                  "input_tokens_details": {"cached_tokens": 4}},
    }


class StructuredRequestTests(unittest.TestCase):
    def test_review_request_binds_same_schema_in_prompt_and_transport(self):
        request = schema_request()
        self.assertEqual(request.response_format, AIResponseFormat.JSON_SCHEMA)
        self.assertEqual(request.response_schema_name, "practice_review_v1")
        schema_text = json.dumps(request.response_schema, ensure_ascii=False, separators=(",", ":"))
        self.assertIn(schema_text, request.messages[0].content)
        self.assertFalse(request.reasoning_enabled)

    def test_each_verdict_branch_requires_fields_and_forbids_null_verdict(self):
        request = schema_request()
        variants = request.response_schema["properties"]["criteria"]["items"]["anyOf"]
        self.assertEqual(len(variants), 8)
        branches = {row["properties"]["verdict"]["enum"][0]: row for row in variants}
        self.assertEqual(set(branches), {"pass", "fail", "unknown"})
        for row in variants:
            self.assertEqual(set(row["required"]), set(row["properties"]))
            self.assertEqual(row["properties"]["verdict"]["type"], "string")
            self.assertFalse(row["additionalProperties"])
        for key in ("issue_type", "evidence_span", "reason", "suggested_self_test", "next_action"):
            self.assertEqual(branches["fail"]["properties"][key]["type"], "string")
        self.assertEqual(branches["unknown"]["properties"]["next_action"]["minLength"], 1)
        self.assertEqual(branches["pass"]["properties"]["issue_type"], {"type": "null"})

    def test_fail_branches_bind_all_criteria_to_template_issue_types(self):
        from app.practice.templates import get_template

        variants = schema_request().response_schema["properties"]["criteria"]["items"]["anyOf"]
        failures = {row["properties"]["criterion_id"]["enum"][0]: row
                    for row in variants if row["properties"]["verdict"]["enum"] == ["fail"]}
        expected = {item["criterion_id"]: set(item["issue_types"]) for item in get_template()["criteria"]}
        self.assertEqual(set(failures), set(expected))
        for criterion_id, issues in expected.items():
            with self.subTest(criterion_id=criterion_id):
                row = failures[criterion_id]["properties"]
                self.assertEqual(row["criterion_id"]["enum"], [criterion_id])
                self.assertEqual(set(row["issue_type"]["enum"]), issues)
        self.assertEqual(failures["C05"]["properties"]["issue_type"]["enum"], ["empty_result_contract"])
        self.assertIn("counting", failures["C03"]["properties"]["issue_type"]["enum"])

    def test_nonfail_quotes_are_null_and_fail_quotes_are_short_single_line(self):
        branches = schema_request().response_schema["properties"]["criteria"]["items"]["anyOf"]
        for branch in branches:
            verdict = branch["properties"]["verdict"]["enum"][0]
            span = branch["properties"]["evidence_span"]
            with self.subTest(verdict=verdict, criterion=branch["properties"]["criterion_id"]):
                if verdict != "fail":
                    self.assertEqual(span, {"type": "null"})
                else:
                    self.assertEqual(span["maxLength"], 300)
                    self.assertEqual(span["minLength"], 1)
                    self.assertIsNotNone(re.fullmatch(span["pattern"], 'return {"说明": "中文\\n"}'))
                    self.assertIsNotNone(re.fullmatch(span["pattern"], "return ..."))
                    self.assertIsNotNone(re.fullmatch(span["pattern"], "x" * 300))
                    self.assertGreater(len("x" * 301), span["maxLength"])
                    self.assertIsNone(re.fullmatch(span["pattern"], "first\n...\nlast"))
                    self.assertIsNone(re.fullmatch(span["pattern"], "first\r\nlast"))

    def test_original_Q03_spliced_pass_quotes_still_rejected_without_rewriting(self):
        root = Path(__file__).resolve().parents[2]
        old = root / "开发相关文档/阶段报告/AI大数据改造/V2/S08-评价运行/20261025-pro-flash-r6"
        payload = json.loads((old / "invalid-candidates/Q03-response.json").read_text(encoding="utf-8"))["response"]
        original = deepcopy(payload)
        data = json.loads((old / "inputs/Q03-under-test-input.json").read_text(encoding="utf-8"))
        PracticeReviewDraft.model_validate(payload)  # 原公共1.0字段仍兼容，拒绝点在代码归属引用。
        agent, provider = make_review_agent(payload)
        with self.assertRaisesRegex(AgentOutputValidationError, "引用不在"):
            asyncio.run(agent.run(make_context(), data))
        self.assertEqual(payload, original)
        self.assertEqual(len(provider.requests), 1)

    def test_legacy_nonfail_contiguous_quote_remains_compatible(self):
        for overall in ("pass", "insufficient"):
            with self.subTest(overall=overall):
                payload = review_draft(overall=overall)
                payload["criteria"][0]["evidence_span"] = "return {}"
                agent, provider = make_review_agent(payload)
                result = asyncio.run(agent.run(make_context(), review_input()))
                self.assertEqual(result.result.criteria[0].evidence_span, "return {}")
                self.assertEqual(result.result.overall, overall)
                self.assertEqual(len(provider.requests), 1)

    def test_real_ellipsis_and_unicode_in_contiguous_fail_quotes_are_not_removed(self):
        for quote in ("return ...", 'return {"说明": "中文\\n"}'):
            with self.subTest(quote=quote):
                payload = review_draft(overall="pass")
                payload.update(overall="needs_changes")
                payload["criteria"][4].update(verdict="fail", issue_type="empty_result_contract", evidence_span=quote,
                    suggested_self_test="核对空输入是否返回五个整数", next_action="修正空有效集返回")
                data = review_input(code="def summarize_records(csv_text):\n    " + quote + "\n")
                agent, provider = make_review_agent(payload)
                result = asyncio.run(agent.run(make_context(), data))
                self.assertEqual(result.result.criteria[4].evidence_span, quote)
                self.assertEqual(len(provider.requests), 1)

    def test_old_wrong_criterion_issue_pair_still_rejected_without_relabel(self):
        payload = review_draft(overall="needs_changes")
        for item in payload["criteria"]:
            item.update(verdict="pass", issue_type=None)
        payload["criteria"][4].update(verdict="fail", issue_type="counting", evidence_span="csv", reason="合成归类错误",
                                       suggested_self_test="核对有效行数", next_action="修正计数")
        original = deepcopy(payload)
        agent, provider = make_review_agent(payload)
        with self.assertRaises(AgentOutputValidationError):
            asyncio.run(agent.run(make_context(), review_input()))
        self.assertEqual(payload, original)
        self.assertEqual(len(provider.requests), 1)

    def test_guidance_keeps_chat_mode_and_old_request_dump(self):
        agent, _ = make_review_agent(guidance_output(), guidance=True)
        request = agent._build_completion_request(make_context(), agent.validate_input(review_input(action="hint")))
        self.assertEqual(request.response_format, AIResponseFormat.JSON_OBJECT)
        self.assertNotIn("response_schema", request.model_dump(mode="json"))
        self.assertNotIn("response_schema_name", request.model_dump(mode="json"))
        path, body = DeepSeekProvider._request_payload(request)
        self.assertEqual(path, "/chat/completions")
        self.assertEqual(body, {
            "model": request.model,
            "messages": [{"role": item.role.value, "content": item.content} for item in request.messages],
            "temperature": request.temperature, "stream": False,
            "max_tokens": request.max_tokens, "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        })

    def test_inconsistent_schema_mode_is_rejected_before_network(self):
        base = {"model": "deepseek-flash", "messages": (AIMessage(role=AIMessageRole.USER, content="synthetic"),)}
        for changes in (
            {"response_format": AIResponseFormat.JSON_SCHEMA},
            {"response_format": AIResponseFormat.JSON_OBJECT, "response_schema": {"type": "object"}},
            {"response_format": AIResponseFormat.JSON_SCHEMA, "response_schema": {"type": "array"}, "response_schema_name": "review"},
            {"response_format": AIResponseFormat.JSON_SCHEMA, "response_schema": {"type": "object"}, "response_schema_name": "bad/name"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                AICompletionRequest(**base, **changes)

    def test_null_verdict_still_rejected_without_guessing_or_retry(self):
        payload = review_draft(overall="pass")
        payload["criteria"][5]["verdict"] = None
        agent, provider = make_review_agent(payload)
        with self.assertRaises(AgentOutputValidationError):
            asyncio.run(agent.run(make_context(), review_input()))
        self.assertEqual(len(provider.requests), 1)
        self.assertIsNone(payload["criteria"][5]["verdict"])


class ResponsesProviderTests(unittest.TestCase):
    def invoke(self, body, *, status=200, raw_content=None, request_override=None):
        requests = []

        async def scenario():
            async def handler(request):
                requests.append(request)
                if raw_content is not None:
                    return httpx.Response(status, request=request, content=raw_content,
                                          headers={"Content-Type": "application/json"})
                return httpx.Response(status, request=request, json=body)

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
                provider = DeepSeekProvider(http, api_key=SecretStr("offline-test-value"),
                                            base_url="https://api.deepseek.com", connect_timeout_seconds=1,
                                            request_timeout_seconds=1)
                client = AIClient(provider, total_timeout_seconds=1, max_retries=0,
                                  retry_base_delay_seconds=0, max_retry_delay_seconds=0)
                try:
                    return await client.complete(request_override or schema_request()), None
                except AIClientError as exc:
                    return None, exc

        result, error = asyncio.run(scenario())
        self.assertEqual(len(requests), 1)
        return result, error, requests[0]

    def test_responses_payload_and_usage_map_without_tools_or_chat_fallback(self):
        result, error, posted = self.invoke(response_body())
        self.assertIsNone(error)
        self.assertEqual(str(posted.url), "https://api.deepseek.com/responses")
        sent = json.loads(posted.content)
        self.assertEqual(sent["text"]["format"]["type"], "json_schema")
        self.assertEqual(sent["text"]["format"]["name"], "practice_review_v1")
        self.assertEqual(sent["reasoning"], {"effort": "none"})
        self.assertEqual(sent["max_output_tokens"], 1500)
        for absent in ("messages", "response_format", "thinking", "tools", "previous_response_id"):
            self.assertNotIn(absent, sent)
        self.assertEqual(result.finish_reason, "completed")
        self.assertEqual(result.usage.model_dump(), {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})

    def test_http_schema_rejection_is_one_call_without_fallback(self):
        result, error, _ = self.invoke({"error": {"message": "synthetic-schema-rejection"}}, status=400)
        self.assertIsNone(result)
        self.assertEqual(error.category, AIFailureCategory.MODEL)
        self.assertFalse(error.retryable)

    def test_incomplete_failed_or_unexpected_outputs_retain_observed_usage(self):
        cases = []
        incomplete = response_body()
        incomplete.update(status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        cases.append(incomplete)
        failed = response_body()
        failed.update(status="failed", error={"message": "private-upstream-note"})
        cases.append(failed)
        tool = response_body()
        tool["output"] = [{"type": "function_call", "name": "must_not_execute"}]
        cases.append(tool)
        refusal = response_body()
        refusal["output"][0]["content"] = [{"type": "refusal"}]
        cases.append(refusal)
        multiple = response_body()
        multiple["output"].append(deepcopy(multiple["output"][0]))
        cases.append(multiple)
        invalid_json = response_body()
        invalid_json["output"][0]["content"][0]["text"] = "synthetic-not-json"
        cases.append(invalid_json)
        for body in cases:
            with self.subTest(body=body):
                result, error, _ = self.invoke(body)
                self.assertIsNone(result)
                self.assertEqual(error.category, AIFailureCategory.RESPONSE_FORMAT)
                self.assertEqual(error.observed_usage.total_tokens, 30)
                self.assertNotIn("private-upstream-note", str(error))

    def test_missing_usage_remains_unknown_and_invalid_usage_does_not_become_zero(self):
        missing = response_body()
        missing["usage"] = None
        result, error, _ = self.invoke(missing)
        self.assertIsNone(error)
        self.assertIsNone(result.usage.total_tokens)
        for usage in ({"input_tokens": True, "output_tokens": 20, "total_tokens": 21},
                      {"input_tokens": 10, "output_tokens": 20, "total_tokens": 31}):
            body = response_body()
            body["usage"] = usage
            result, error, _ = self.invoke(body)
            self.assertIsNone(result)
            self.assertEqual(error.category, AIFailureCategory.RESPONSE_FORMAT)
            self.assertIsNone(error.observed_usage)

    def test_utf8_chinese_emoji_and_code_escapes_round_trip(self):
        body = response_body()
        expected = json.dumps({"说明": "中文🙂 引号\"及换行\n下一行", "code": r'out["record_count"] += 2; path="C:\sample"'},
                              ensure_ascii=False)
        body["output"][0]["content"][0]["text"] = expected
        for encoding in ("utf-8", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                raw = json.dumps(body, ensure_ascii=False).encode(encoding)
                result, error, _ = self.invoke(None, raw_content=raw)
                self.assertIsNone(error)
                self.assertEqual(result.content, expected)
                self.assertEqual(json.loads(result.content)["说明"], "中文🙂 引号\"及换行\n下一行")

    def test_invalid_utf8_and_utf16_are_rejected_without_replacement(self):
        valid = json.dumps(response_body(), ensure_ascii=False)
        for raw in (valid.encode("utf-8") + b"\xff", valid.encode("utf-16")):
            with self.subTest(raw_start=raw[:5]):
                result, error, _ = self.invoke(None, raw_content=raw)
                self.assertIsNone(result)
                self.assertEqual(error.category, AIFailureCategory.RESPONSE_FORMAT)
                self.assertIsNone(error.observed_usage)

    def test_old_chat_utf8_boundary_preserves_text_and_rejects_bad_bytes(self):
        original = schema_request()
        request = AICompletionRequest(messages=original.messages, model=original.model,
                                      response_format=AIResponseFormat.JSON_OBJECT,
                                      max_tokens=1200, reasoning_enabled=False)
        expected = json.dumps({"建议": "中文🚀，引号\"，换行\n以及字面\\n"}, ensure_ascii=False)
        body = {"model": request.model, "choices": [{"finish_reason": "stop", "message": {"content": expected}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}
        text = json.dumps(body, ensure_ascii=False)
        for encoding in ("utf-8", "utf-8-sig"):
            result, error, posted = self.invoke(None, raw_content=text.encode(encoding), request_override=request)
            self.assertIsNone(error)
            self.assertEqual(result.content, expected)
            self.assertEqual(str(posted.url), "https://api.deepseek.com/chat/completions")
        result, error, _ = self.invoke(None, raw_content=text.encode("utf-16"), request_override=request)
        self.assertIsNone(result)
        self.assertEqual(error.category, AIFailureCategory.RESPONSE_FORMAT)


if __name__ == "__main__":
    unittest.main()
