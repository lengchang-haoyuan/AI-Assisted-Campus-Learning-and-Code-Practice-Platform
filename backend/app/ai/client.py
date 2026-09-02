import asyncio
from collections.abc import Awaitable, Callable
import logging
import random
from time import perf_counter

from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AICompletionResult,
    AIFailureCategory,
    AIProvider,
    AIProviderResult,
)

SleepCallable = Callable[[float], Awaitable[None]]
JitterCallable = Callable[[float, float], float]


class AIClient:
    def __init__(
        self,
        provider: AIProvider,
        *,
        total_timeout_seconds: float,
        max_retries: int,
        retry_base_delay_seconds: float,
        max_retry_delay_seconds: float,
        sleep: SleepCallable = asyncio.sleep,
        jitter: JitterCallable = random.uniform,
    ) -> None:
        if total_timeout_seconds <= 0:
            raise ValueError("total_timeout_seconds 必须大于 0")
        if max_retries < 0:
            raise ValueError("max_retries 不能小于 0")
        if retry_base_delay_seconds < 0:
            raise ValueError("retry_base_delay_seconds 不能小于 0")
        if max_retry_delay_seconds < retry_base_delay_seconds:
            raise ValueError("max_retry_delay_seconds 不能小于基础延迟")
        self._provider = provider
        self._total_timeout_seconds = total_timeout_seconds
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._max_retry_delay_seconds = max_retry_delay_seconds
        self._sleep = sleep
        self._jitter = jitter
        self._logger = logging.getLogger("scholarhub.ai")

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def complete(self, request: AICompletionRequest) -> AICompletionResult:
        started_at = perf_counter()
        attempt_count = 0
        try:
            async with asyncio.timeout(self._total_timeout_seconds):
                while True:
                    attempt_count += 1
                    try:
                        provider_result = await self._provider.complete(request)
                        break
                    except AIClientError as exc:
                        if not self._can_retry(exc, attempt_count):
                            raise
                        delay_seconds = self._retry_delay(exc, attempt_count)
                        self._logger.info(
                            "ai_request_retrying",
                            extra={
                                "provider": self._provider.name,
                                "model": request.model,
                                "status": "retrying",
                                "failure_category": exc.category.value,
                                "attempt_count": attempt_count,
                            },
                        )
                        await self._sleep(delay_seconds)
        except asyncio.CancelledError:
            self._log_terminal_event(
                level=logging.INFO,
                request=request,
                status="cancelled",
                latency_ms=self._elapsed_ms(started_at),
                attempt_count=attempt_count,
                failure_category="cancelled",
            )
            raise
        except TimeoutError as exc:
            error = AIClientError(
                "AI 调用超过总超时",
                category=AIFailureCategory.TOTAL_TIMEOUT,
            )
            self._log_terminal_event(
                level=logging.WARNING,
                request=request,
                status="failed",
                latency_ms=self._elapsed_ms(started_at),
                attempt_count=attempt_count,
                failure_category=error.category.value,
            )
            raise error from exc
        except AIClientError as exc:
            self._log_terminal_event(
                level=logging.WARNING,
                request=request,
                status="failed",
                latency_ms=self._elapsed_ms(started_at),
                attempt_count=attempt_count,
                failure_category=exc.category.value,
            )
            raise

        latency_ms = self._elapsed_ms(started_at)
        result = self._to_completion_result(provider_result, latency_ms)
        self._log_terminal_event(
            level=logging.INFO,
            request=request,
            status="succeeded",
            latency_ms=latency_ms,
            attempt_count=attempt_count,
        )
        return result

    def _can_retry(self, error: AIClientError, attempt_count: int) -> bool:
        if not error.retryable or attempt_count > self._max_retries:
            return False
        retry_after = error.retry_after_seconds
        return retry_after is None or retry_after <= self._max_retry_delay_seconds

    def _retry_delay(self, error: AIClientError, attempt_count: int) -> float:
        exponential_delay = self._retry_base_delay_seconds * (2 ** (attempt_count - 1))
        jittered_delay = exponential_delay * self._jitter(0.8, 1.2)
        delay = min(jittered_delay, self._max_retry_delay_seconds)
        if error.retry_after_seconds is not None:
            delay = max(delay, error.retry_after_seconds)
        return min(delay, self._max_retry_delay_seconds)

    @staticmethod
    def _to_completion_result(
        result: AIProviderResult, latency_ms: int
    ) -> AICompletionResult:
        return AICompletionResult(
            provider=result.provider,
            model=result.model,
            content=result.content,
            finish_reason=result.finish_reason,
            usage=result.usage,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(0, round((perf_counter() - started_at) * 1000))

    def _log_terminal_event(
        self,
        *,
        level: int,
        request: AICompletionRequest,
        status: str,
        latency_ms: int,
        attempt_count: int,
        failure_category: str | None = None,
    ) -> None:
        self._logger.log(
            level,
            "ai_request_finished",
            extra={
                "provider": self._provider.name,
                "model": request.model,
                "status": status,
                "latency_ms": latency_ms,
                "attempt_count": attempt_count,
                "failure_category": failure_category,
            },
        )
