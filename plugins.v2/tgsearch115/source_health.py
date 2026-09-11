"""Persistable, privacy-safe rolling source-health counters."""
from __future__ import annotations
import threading
import time
from datetime import datetime
from typing import Any, Dict

SOURCES = ("tg", "site", "pansou", "juying")

class SourceHealth:
    schema_version = 1
    def __init__(self, data: Dict[str, dict] | None = None):
        self._lock = threading.RLock(); self._data = {s: dict((data or {}).get(s) or {}) for s in SOURCES}
    def record(self, source: str, outcome: str, elapsed: float = 0.0, count: int = 0) -> None:
        if source not in self._data: return
        with self._lock:
            item = self._data[source]; item["requests"] = int(item.get("requests", 0)) + 1
            item["elapsed_total"] = float(item.get("elapsed_total", 0)) + max(0, elapsed); item["last_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            item["results"] = int(item.get("results", 0)) + max(0, count)
            key = "success" if outcome == "success" else "empty" if outcome == "empty" else outcome if outcome in {"timeout", "401", "403", "429", "5xx"} else "failed"
            item[key] = int(item.get(key, 0)) + 1
            if key == "success": item["last_success"] = item["last_at"]
    def snapshot(self, breaker: Dict[str, dict] | None = None) -> Dict[str, dict]:
        with self._lock:
            result = {}
            for source, raw in self._data.items():
                req, success = int(raw.get("requests", 0)), int(raw.get("success", 0))
                failures = sum(int(raw.get(k, 0)) for k in ("timeout", "401", "403", "429", "5xx", "failed"))
                score = 100 if not req else max(0, min(100, round(100 * success / req - min(50, failures * 8))))
                state = (breaker or {}).get(source, {})
                result[source] = {"score": score, "requests": req, "success": success, "empty": int(raw.get("empty", 0)), "timeout": int(raw.get("timeout", 0)), "http_401": int(raw.get("401", 0)), "http_403": int(raw.get("403", 0)), "http_429": int(raw.get("429", 0)), "http_5xx": int(raw.get("5xx", 0)), "average_seconds": round(float(raw.get("elapsed_total", 0)) / req, 2) if req else 0, "results": int(raw.get("results", 0)), "last_success": raw.get("last_success", ""), "cooldown_seconds": int(state.get("cooldown_seconds", 0) or 0)}
            return result
    def dump(self) -> Dict[str, dict]:
        with self._lock: return {k: dict(v) for k, v in self._data.items()}
