# -*- coding: utf-8 -*-
"""Serialize MoviePilot recognition calls and retry cursor lifecycle failures."""
from __future__ import annotations

import random
import threading
import time
from typing import Any, Callable, Dict, Optional


class RecognitionUnavailable(RuntimeError):
    """Identify a safe reason category without retaining an exception's raw details."""

    def __init__(self, message: str, reason: str = "unknown") -> None:
        super().__init__(message)
        self.reason = reason


class RecognitionGate:
    def __init__(
        self,
        sleep: Callable[[float], None] = time.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._sleep = sleep
        self._random_uniform = random_uniform
        self._lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self._stop = threading.Event()
        self._waiting = 0
        self._active = 0
        self._max_active = 0
        self._last_wait_seconds = 0.0
        self._retries = 0
        self._unavailable = 0

    @staticmethod
    def _cursor_failure(exc: BaseException) -> bool:
        text = str(exc or "").casefold()
        return "kill_cursor" in text and "nonetype" in text

    def run(
        self,
        factory: Callable[[], Any],
        operation: Callable[[Any], Any],
        label: str = "media",
        on_retry: Optional[Callable[[str, int, str], None]] = None,
        retry_none: bool = False,
    ) -> Any:
        last_error: Optional[BaseException] = None
        for attempt in range(2):
            if self._stop.is_set():
                raise RecognitionUnavailable("插件正在停止，媒体识别已取消")
            started = time.monotonic()
            with self._metrics_lock:
                self._waiting += 1
            acquired = False
            try:
                while not acquired:
                    if self._stop.is_set():
                        raise RecognitionUnavailable("插件正在停止，媒体识别已取消")
                    acquired = self._lock.acquire(timeout=0.2)
                waited = max(0.0, time.monotonic() - started)
                with self._metrics_lock:
                    self._waiting -= 1
                    self._last_wait_seconds = waited
                    self._active += 1
                    self._max_active = max(self._max_active, self._active)
                try:
                    chain = factory()
                    result = operation(chain)
                    if result is not None or not retry_none:
                        return result
                    last_error = RuntimeError("empty recognition result")
                    if attempt >= 1:
                        break
                    with self._metrics_lock:
                        self._retries += 1
                    if on_retry:
                        on_retry(label, attempt + 1, "empty_result")
                finally:
                    with self._metrics_lock:
                        self._active = max(0, self._active - 1)
            except RecognitionUnavailable:
                raise
            except Exception as exc:
                last_error = exc
                if not self._cursor_failure(exc) or attempt >= 1:
                    break
                with self._metrics_lock:
                    self._retries += 1
                if on_retry:
                    on_retry(label, attempt + 1, "kill_cursor")
            finally:
                if acquired:
                    self._lock.release()
                else:
                    with self._metrics_lock:
                        self._waiting = max(0, self._waiting - 1)
            if attempt == 0:
                self._sleep(self._random_uniform(1.0, 3.0))
        with self._metrics_lock:
            self._unavailable += 1
        reason = "cursor_lifecycle" if last_error and self._cursor_failure(last_error) \
            else type(last_error).__name__ if last_error else "unknown"
        raise RecognitionUnavailable(
            f"{label} identity_unavailable: {reason}", reason=reason
        ) from last_error

    def stop(self, timeout: float = 5.0) -> bool:
        self._stop.set()
        acquired = self._lock.acquire(timeout=max(0.0, float(timeout)))
        if acquired:
            self._lock.release()
        return acquired

    def status(self) -> Dict[str, Any]:
        with self._metrics_lock:
            return {
                "waiting": self._waiting,
                "active": self._active,
                "max_active": self._max_active,
                "last_wait_seconds": round(self._last_wait_seconds, 3),
                "retries": self._retries,
                "identity_unavailable": self._unavailable,
                "stopping": self._stop.is_set(),
            }
