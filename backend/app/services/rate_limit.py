from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from app.core.exceptions import RateLimitError


class SensitiveActionLimiter:
    """适配当前单实例部署的进程内有界频率限制。"""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            if key not in self._events and len(self._events) >= 10_000:
                self._events.pop(next(iter(self._events)))
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                raise RateLimitError()
            events.append(now)


_limiter = SensitiveActionLimiter()


def get_sensitive_action_limiter() -> SensitiveActionLimiter:
    return _limiter
