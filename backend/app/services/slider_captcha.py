from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from secrets import token_urlsafe
from threading import Lock
from time import monotonic

from app.core.exceptions import AppError, InputError


class SliderCaptchaError(InputError):
    code = "slider_verification_required"
    default_message = "滑块验证无效或已过期，请重新验证"


class SliderCaptchaBusyError(AppError):
    status_code = 429
    code = "slider_verification_busy"
    default_message = "验证请求较多，请稍后重试"


@dataclass(frozen=True, slots=True)
class SliderTicket:
    value: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class _Entry:
    issued_at: float
    expires_at: float
    verified: bool


class SliderCaptchaService:
    """单进程开发部署的基础滑块校验；不替代专业反机器人服务。"""

    challenge_ttl = 120
    token_ttl = 60
    minimum_age = 0.5

    def __init__(
        self, *, clock: Callable[[], float] = monotonic, capacity: int = 2048
    ) -> None:
        self._clock = clock
        self._capacity = capacity
        self._entries: dict[str, _Entry] = {}
        self._lock = Lock()

    def create_challenge(self) -> SliderTicket:
        with self._lock:
            now = self._clock()
            self._entries = {
                key: entry
                for key, entry in self._entries.items()
                if entry.expires_at > now
            }
            if len(self._entries) >= self._capacity:
                raise SliderCaptchaBusyError()
            value = token_urlsafe(32)
            self._entries[value] = _Entry(now, now + self.challenge_ttl, False)
            return SliderTicket(value, self.challenge_ttl)

    def verify(self, challenge_id: str, position: int) -> SliderTicket:
        with self._lock:
            now = self._clock()
            entry = self._entries.pop(challenge_id, None)
            # 每次提交都会消费挑战，失败后需重新获取，避免重复试探。
            if (
                entry is None
                or entry.verified
                or entry.expires_at <= now
                or now - entry.issued_at < self.minimum_age
                or position != 100
            ):
                raise SliderCaptchaError()
            value = token_urlsafe(32)
            self._entries[value] = _Entry(now, now + self.token_ttl, True)
            return SliderTicket(value, self.token_ttl)

    def consume(self, token: str) -> None:
        with self._lock:
            entry = self._entries.pop(token, None)
            if (
                entry is None
                or not entry.verified
                or entry.expires_at <= self._clock()
            ):
                raise SliderCaptchaError()


@lru_cache
def get_slider_captcha_service() -> SliderCaptchaService:
    return SliderCaptchaService()
