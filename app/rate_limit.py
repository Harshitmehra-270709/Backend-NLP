from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException


class RateLimiter:
    """Simple in-memory fixed-window limiter suitable for a single-process demo app."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def enforce(self, key: str) -> None:
        now = monotonic()
        with self._lock:
            bucket = self._requests[key]
            while bucket and now - bucket[0] > self.window_seconds:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please wait a moment before sending more commands.",
                )

            bucket.append(now)
