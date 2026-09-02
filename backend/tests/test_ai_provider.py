import asyncio
from datetime import UTC, datetime
import io
import json
import logging
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import AsyncMock, Mock

import httpx
from pydantic import SecretStr, ValidationError

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.ai.client import AIClient
from app.ai.deepseek import DeepSeekProvider
from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIMessage,
    AIMessageRole,
    AIProvider,
    AIProviderResult,
    AIUsage,
)
from app.api.deps import get_ai_service, get_current_user
from app.core.config import AISettings
from app.core.exceptions import AIConfigurationError
from app.core.logging import JsonFormatter
from app.main import create_app
from app.services.ai import AICompletionData, AICompletionInput, AIService
from app.services.auth import UserIdentity
from tests.test_api_foundation import request

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)


def make_request(prompt: str = "请返回健康状态") -> AICompletionRequest:
    return AICompletionRequest(
        messages=(AIMessage(role=AIMessageRole.USER, content=prompt),),
        model="deepseek-v4-flash",
        temperature=0.2,
        max_tokens=128,
    )


def make_provider_result() -> AIProviderResult:
    return AIProviderResult(
        provider="fake",
        model="deepseek-v4-flash",
        content="ok",
        finish_reason="stop",
        usage=AIUsage(
            prompt_tokens=4,
            completion_tokens=1,
            total_tokens=5,
        ),
    )


class FakeProvider(AIProvider):
    def __init__(self, outcomes: list[AIProviderResult | AIClientError]) -> None:
        self._outcomes = outcomes.copy()
        self.requests: list[AICompletionRequest] = []

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request_data: AICompletionRequest) -> AIProviderResult:
        self.requests.append(request_data)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, AIClientError):
            raise outcome
        return outcome


class BlockingProvider(AIProvider):
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    @property
    def name(self) -> str:
        return "blocking"

    async def complete(self, request_data: AICompletionRequest) -> AIProviderResult:
        del request_data
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("unreachable")


class AIClientTests(unittest.TestCase):
    @staticmethod
    def build_client(
        provider: AIProvider,
        *,
        total_timeout_seconds: float = 1.0,
        max_retries: int = 1,
        sleep: AsyncMock | None = None,
    ) -> AIClient:
        return AIClient(
            provider,
            total_timeout_seconds=total_timeout_seconds,
            max_retries=max_retries,
            retry_base_delay_seconds=0.1,
            max_retry_delay_seconds=1.0,
            sleep=sleep or asyncio.sleep,
            jitter=lambda _minimum, _maximum: 1.0,
        )

    def test_fake_provider_returns_uniform_result_and_safe_log(self) -> None:
        provider = FakeProvider([make_provider_result()])
        client = self.build_client(provider)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger("scholarhub.ai")
        original_handlers = logger.handlers.copy()
        original_propagate = logger.propagate
        original_level = logger.level
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

        try:
            result = asyncio.run(client.complete(make_request("private-prompt-value")))
        finally:
            logger.handlers = original_handlers
            logger.propagate = original_propagate
            logger.setLevel(original_level)

        self.assertEqual(result.provider, "fake")
        self.assertEqual(result.content, "ok")
        log_payload = json.loads(stream.getvalue())
        self.assertEqual(log_payload["provider"], "fake")
        self.assertEqual(log_payload["status"], "succeeded")
        self.assertEqual(log_payload["attempt_count"], 1)
        self.assertNotIn("private-prompt-value", stream.getvalue())
        self.assertNotIn("Authorization", stream.getvalue())

    def test_retries_only_explicit_retryable_failure(self) -> None:
        retryable_error = AIClientError(
            "连接失败",
            category=AIFailureCategory.NETWORK,
            retryable=True,
        )
        provider = FakeProvider([retryable_error, make_provider_result()])
        sleep = AsyncMock()
        result = asyncio.run(
            self.build_client(provider, sleep=sleep).complete(make_request())
        )

        self.assertEqual(result.content, "ok")
        self.assertEqual(len(provider.requests), 2)
        sleep.assert_awaited_once_with(0.1)

    def test_does_not_retry_model_or_ambiguous_failure(self) -> None:
        provider = FakeProvider(
            [
                AIClientError(
                    "模型错误",
                    category=AIFailureCategory.MODEL,
                    retryable=False,
                )
            ]
        )
        sleep = AsyncMock()

        with self.assertRaises(AIClientError) as raised:
            asyncio.run(
                self.build_client(provider, sleep=sleep).complete(make_request())
            )

        self.assertEqual(raised.exception.category, AIFailureCategory.MODEL)
        self.assertEqual(len(provider.requests), 1)
        sleep.assert_not_awaited()

    def test_total_timeout_bounds_provider_and_retry_work(self) -> None:
        class SlowProvider(AIProvider):
            @property
            def name(self) -> str:
                return "slow"

            async def complete(
                self, request_data: AICompletionRequest
            ) -> AIProviderResult:
                del request_data
                await asyncio.sleep(0.05)
                return make_provider_result()

        with self.assertRaises(AIClientError) as raised:
            asyncio.run(
                self.build_client(
                    SlowProvider(), total_timeout_seconds=0.01
                ).complete(make_request())
            )
        self.assertEqual(raised.exception.category, AIFailureCategory.TOTAL_TIMEOUT)

    def test_cancellation_is_propagated_without_retry(self) -> None:
        async def run_scenario() -> BlockingProvider:
            provider = BlockingProvider()
            task = asyncio.create_task(
                self.build_client(provider).complete(make_request())
            )
            await provider.started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            return provider

        provider = asyncio.run(run_scenario())
        self.assertTrue(provider.cancelled)


class DeepSeekProviderTests(unittest.TestCase):
    def test_maps_http_response_to_provider_result(self) -> None:
        async def run_scenario() -> AIProviderResult:
            async def handler(request_data: httpx.Request) -> httpx.Response:
                self.assertEqual(
                    request_data.url,
                    httpx.URL("https://api.deepseek.com/chat/completions"),
                )
                self.assertEqual(request_data.headers["Authorization"], "Bearer test-key")
                sent_payload = json.loads(request_data.content)
                self.assertEqual(sent_payload["model"], "deepseek-v4-flash")
                self.assertEqual(sent_payload["messages"][0]["role"], "user")
                return httpx.Response(
                    200,
                    request=request_data,
                    json={
                        "model": "deepseek-v4-flash",
                        "choices": [
                            {
                                "message": {"content": "统一响应"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 3,
                            "completion_tokens": 2,
                            "total_tokens": 5,
                        },
                    },
                )

            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as http_client:
                provider = DeepSeekProvider(
                    http_client,
                    api_key=SecretStr("test-key"),
                    base_url="https://api.deepseek.com",
                    connect_timeout_seconds=1,
                    request_timeout_seconds=2,
                )
                return await provider.complete(make_request())

        result = asyncio.run(run_scenario())
        self.assertEqual(result.provider, "deepseek")
        self.assertEqual(result.content, "统一响应")
        self.assertEqual(result.usage.total_tokens, 5)

    def test_missing_key_fails_before_network_request(self) -> None:
        async def run_scenario() -> bool:
            called = False

            async def handler(request_data: httpx.Request) -> httpx.Response:
                nonlocal called
                called = True
                return httpx.Response(500, request=request_data)

            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as http_client:
                provider = DeepSeekProvider(
                    http_client,
                    api_key=None,
                    base_url="https://api.deepseek.com",
                    connect_timeout_seconds=1,
                    request_timeout_seconds=2,
                )
                with self.assertRaises(AIClientError) as raised:
                    await provider.complete(make_request())
                self.assertEqual(
                    raised.exception.category, AIFailureCategory.CONFIGURATION
                )
            return called

        self.assertFalse(asyncio.run(run_scenario()))

    def test_rate_limit_and_invalid_json_are_classified(self) -> None:
        async def run_status(
            response_factory: str,
        ) -> AIClientError:
            async def handler(request_data: httpx.Request) -> httpx.Response:
                if response_factory == "rate_limit":
                    return httpx.Response(
                        429,
                        request=request_data,
                        headers={"Retry-After": "1"},
                    )
                return httpx.Response(200, request=request_data, content=b"not-json")

            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as http_client:
                provider = DeepSeekProvider(
                    http_client,
                    api_key=SecretStr("test-key"),
                    base_url="https://api.deepseek.com",
                    connect_timeout_seconds=1,
                    request_timeout_seconds=2,
                )
                with self.assertRaises(AIClientError) as raised:
                    await provider.complete(make_request())
                return raised.exception

        rate_limit = asyncio.run(run_status("rate_limit"))
        self.assertEqual(rate_limit.category, AIFailureCategory.RATE_LIMIT)
        self.assertTrue(rate_limit.retryable)
        self.assertEqual(rate_limit.retry_after_seconds, 1)

        invalid_json = asyncio.run(run_status("invalid_json"))
        self.assertEqual(invalid_json.category, AIFailureCategory.RESPONSE_FORMAT)
        self.assertFalse(invalid_json.retryable)


class AISettingsTests(unittest.TestCase):
    def test_api_key_is_optional_and_hidden_from_repr(self) -> None:
        settings = AISettings(_env_file=None, deepseek_api_key="test-secret")
        self.assertNotIn("test-secret", repr(settings))

        missing_key = AISettings(_env_file=None, deepseek_api_key=" ")
        self.assertIsNone(missing_key.deepseek_api_key)

    def test_rejects_non_official_or_insecure_base_url(self) -> None:
        with self.assertRaises(ValidationError):
            AISettings(_env_file=None, deepseek_base_url="http://api.deepseek.com")


class AIServiceTests(unittest.TestCase):
    def test_missing_key_is_mapped_to_safe_application_error(self) -> None:
        provider = FakeProvider(
            [
                AIClientError(
                    "未配置底层密钥",
                    category=AIFailureCategory.CONFIGURATION,
                )
            ]
        )
        service = AIService(
            AIClientTests.build_client(provider),
            default_model="deepseek-v4-flash",
            api_key_env_name="DEEPSEEK_API_KEY",
        )

        with self.assertRaises(AIConfigurationError) as raised:
            asyncio.run(
                service.complete_test(
                    AICompletionInput(
                        prompt="test",
                        model=None,
                        temperature=0.2,
                        max_tokens=64,
                    )
                )
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.code, "ai_configuration_error")
        self.assertIn("DEEPSEEK_API_KEY", raised.exception.message)
        self.assertNotIn("未配置底层密钥", raised.exception.message)


class AIProviderAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=AIService)
        self.service.complete_test = AsyncMock(
            return_value=AICompletionData(
                provider="fake",
                model="deepseek-v4-flash",
                content="provider-ok",
                finish_reason="stop",
                prompt_tokens=3,
                completion_tokens=2,
                total_tokens=5,
                latency_ms=12,
            )
        )
        self.app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1,
            username="student",
            email="student@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.app.dependency_overrides[get_ai_service] = lambda: self.service

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_authenticated_endpoint_returns_uniform_json(self) -> None:
        response = request(
            self.app,
            "POST",
            "/api/v1/ai/test",
            body={"prompt": "测试 Provider", "max_tokens": 64},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "provider": "fake",
                "model": "deepseek-v4-flash",
                "content": "provider-ok",
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                },
                "latency_ms": 12,
            },
        )
        service_input = self.service.complete_test.await_args.args[0]
        self.assertEqual(service_input.prompt, "测试 Provider")
        self.assertEqual(service_input.max_tokens, 64)

    def test_endpoint_requires_authentication_and_valid_payload(self) -> None:
        app = create_app()
        app.dependency_overrides[get_ai_service] = lambda: self.service
        unauthenticated = request(
            app,
            "POST",
            "/api/v1/ai/test",
            body={"prompt": "test"},
        )
        self.assertEqual(unauthenticated.status_code, 401)

        invalid = request(
            self.app,
            "POST",
            "/api/v1/ai/test",
            body={"prompt": " ", "unknown": True},
        )
        self.assertEqual(invalid.status_code, 422)
        self.service.complete_test.assert_not_awaited()

    def test_configuration_error_is_safe_and_actionable(self) -> None:
        self.service.complete_test.side_effect = AIConfigurationError(
            "未配置 DEEPSEEK_API_KEY，请在后端环境变量中配置后重试"
        )
        response = request(
            self.app,
            "POST",
            "/api/v1/ai/test",
            body={"prompt": "test"},
        )

        self.assertEqual(response.status_code, 503)
        error = response.json()["error"]
        self.assertEqual(error["code"], "ai_configuration_error")
        self.assertIn("DEEPSEEK_API_KEY", error["message"])
        self.assertNotIn("Authorization", response.body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
