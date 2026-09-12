"""Thread-safe, sanitized subscription diagnostic timeline."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

ACTIVE = {"running", "waiting", "waiting_organize"}
TERMINAL = {"completed", "failed", "skipped", "recovered"}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe(value: Any, limit: int = 180) -> str:
    text = str(value or "").replace("magnet:?", "[magnet]")
    for marker in ("http://", "https://"):
        if marker in text:
            text = text.split(marker, 1)[0].rstrip() + "[链接已脱敏]"
    return text[:limit]


class SubscriptionTimeline:
    schema_version = 1

    def __init__(self, records: Optional[Iterable[dict]] = None, max_runs: int = 160, max_events: int = 50):
        self.max_runs, self.max_events = max(20, max_runs), max(10, max_events)
        self._lock = threading.RLock()
        self._records: Dict[str, dict] = {}
        for record in records or []:
            if isinstance(record, dict) and record.get("run_id"):
                value = dict(record)
                value["events"] = list(value.get("events") or [])[-self.max_events:]
                if value.get("status") == "running":
                    value.update({"status": "recovered", "stage": "recovered", "ended_at": _now()})
                    value["events"].append({"at": _now(), "stage": "recovered", "status": "recovered", "summary": "插件重启，已安全恢复", "counts": {}})
                self._records[str(value["run_id"])] = value
        self._trim()

    @staticmethod
    def key(subscribe_id: int, season: Any) -> str:
        return f"{int(subscribe_id)}:{'' if season is None else season}"

    def start(self, subscribe: Any, trigger: str) -> str:
        sid = int(getattr(subscribe, "id", 0) or 0)
        season = getattr(subscribe, "season", None)
        with self._lock:
            for run in self._records.values():
                if run.get("key") == self.key(sid, season) and run.get("status") in ACTIVE:
                    return str(run["run_id"])
            run_id = uuid.uuid4().hex[:16]
            self._records[run_id] = {
                "run_id": run_id, "key": self.key(sid, season), "subscribe_id": sid,
                "title": _safe(getattr(subscribe, "name", ""), 80), "year": getattr(subscribe, "year", None),
                "season": season, "trigger": _safe(trigger, 30), "started_at": _now(), "updated_at": _now(),
                "ended_at": "", "stage": "queued", "status": "running", "reason": "",
                "source_stats": {}, "candidate_stats": {}, "final_source": "", "resource_kind": "", "subscription_written": False,
                "waiting_organize": False, "events": [],
            }
            self.event(run_id, "queued", "running", "已进入插件队列")
            self._trim()
            return run_id

    def event(self, run_id: str, stage: str, status: str = "running", summary: str = "", counts: Optional[dict] = None, **fields) -> None:
        with self._lock:
            run = self._records.get(str(run_id))
            if not run:
                return
            run.update({k: v for k, v in fields.items() if k in {"source_stats", "candidate_stats", "final_source", "resource_kind", "subscription_written", "waiting_organize"}})
            run.update({"stage": stage, "status": status, "updated_at": _now()})
            if summary:
                run["reason"] = _safe(summary)
            run.setdefault("events", []).append({"at": _now(), "stage": stage, "status": status, "summary": _safe(summary), "counts": dict(counts or {})})
            run["events"] = run["events"][-self.max_events:]
            if status in TERMINAL:
                run["ended_at"] = _now()

    def dump(self) -> list:
        with self._lock:
            return sorted((dict(r, events=list(r.get("events") or [])) for r in self._records.values()), key=lambda r: r.get("updated_at", ""), reverse=True)

    def list(self, status: str = "all", offset: int = 0, limit: int = 30) -> dict:
        all_records = self.dump()
        all_statuses = [str(record.get("status") or "") for record in all_records]
        records = all_records
        if status != "all":
            wanted = {"failed", "skipped"} if status == "failed" else {status}
            records = [r for r in records if r.get("status") in wanted]
        return {
            "total": len(records),
            "active_count": sum(item in ACTIVE for item in all_statuses),
            "terminal_count": sum(item in TERMINAL for item in all_statuses),
            "items": records[max(0, offset):max(0, offset) + min(100, max(1, limit))],
        }

    def counts(self) -> dict:
        """Return only state counts; safe to expose in the plugin runtime API."""
        with self._lock:
            statuses = [str(record.get("status") or "") for record in self._records.values()]
            return {
                "total": len(statuses),
                "active_count": sum(status in ACTIVE for status in statuses),
                "terminal_count": sum(status in TERMINAL for status in statuses),
            }

    def clear_terminal(self) -> int:
        with self._lock:
            if any(r.get("status") in ACTIVE for r in self._records.values()):
                raise RuntimeError("存在活动诊断任务，不能清理")
            old = len(self._records)
            self._records = {k: v for k, v in self._records.items() if v.get("status") not in TERMINAL}
            return old - len(self._records)

    def _trim(self) -> None:
        if len(self._records) <= self.max_runs:
            return
        kept = self.dump()[:self.max_runs]
        self._records = {r["run_id"]: r for r in kept}
