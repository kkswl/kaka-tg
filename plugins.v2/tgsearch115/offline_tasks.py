# -*- coding: utf-8 -*-
"""Persistent, secret-free ledger shared by direct 115 and CMS tasks."""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional


STATUSES = {"waiting", "submitted", "downloading", "pending_organize", "completed", "failed", "timed_out", "cancelled"}
ACTIVE = {"waiting", "submitted", "downloading", "pending_organize"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _time(value: Any) -> Optional[datetime]:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class OfflineTaskLedger:
    def __init__(self, records: Optional[Iterable[Dict[str, Any]]] = None, now: Callable[[], datetime] = utc_now, max_records: int = 300):
        self._now, self._lock = now, threading.RLock()
        self.max_records = max(20, int(max_records))
        self.records: List[Dict[str, Any]] = []
        for item in records or []:
            if not isinstance(item, dict) or not item.get("btih"): continue
            record = dict(item); record.pop("magnet", None); record["source"] = record.get("source") or "cms"
            record["status"] = record.get("status") if record.get("status") in STATUSES else "waiting"
            self.records.append(record)
        self.records = self.records[-self.max_records:]

    def reserve(self, *, source: str, btih: str, title: str = "", subscribe: Any = None, task_id: str = "", target_cid: Any = 0) -> tuple[Dict[str, Any], bool]:
        key = str(btih or "").lower()
        if not key: raise ValueError("缺少有效 BTIH")
        with self._lock:
            for record in reversed(self.records):
                if ((record.get("btih") == key or (task_id and record.get("task_id") == str(task_id)))
                        and record.get("status") in ACTIVE):
                    return record, False
            stamp = self._now().isoformat(timespec="seconds")
            record = {"source": str(source or "cms"), "subscribe_id": getattr(subscribe, "id", None) if subscribe else None, "tmdb_id": getattr(subscribe, "tmdbid", None) if subscribe else None, "douban_id": getattr(subscribe, "doubanid", None) if subscribe else None, "title": str(title or "未命名资源")[:240], "btih": key, "task_id": str(task_id or ""), "target_cid": str(target_cid or 0), "submitted_at": stamp, "updated_at": stamp, "status": "waiting", "progress": None, "error_code": "", "error_message": "", "retry_count": 0}
            self.records.append(record); self.records = self.records[-self.max_records:]
            return record, True

    def update(self, btih: str = "", status: str = "", **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            for record in reversed(self.records):
                if record.get("btih") == str(btih or "").lower() or (fields.get("task_id") and record.get("task_id") == fields["task_id"]):
                    if status in STATUSES: record["status"] = status
                    for key in ("task_id", "progress", "error_code", "error_message", "target_cid"):
                        if key in fields: record[key] = fields[key]
                    record["updated_at"] = self._now().isoformat(timespec="seconds")
                    return record
        return None

    def by_btih(self, btih: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return next((dict(r) for r in reversed(self.records) if r.get("btih") == str(btih or "").lower()), None)

    def by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return next((dict(r) for r in reversed(self.records) if r.get("task_id") == str(task_id or "")), None)

    def public_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            result = []
            for record in reversed(self.records[-max(1, int(limit)):]):
                public = dict(record); task_id = str(public.get("task_id") or "")
                public["task_id"] = f"{task_id[:12]}..." if len(task_id) > 12 else task_id
                result.append(public)
            return result

    def dump_records(self) -> List[Dict[str, Any]]:
        with self._lock: return [dict(r) for r in self.records]

    def reconcile(self, timeout_hours: int, history_exists: Callable[[Dict[str, Any]], bool], restore_subscription: Callable[[int], None]) -> Dict[str, int]:
        now = self._now(); result = {"completed": 0, "timed_out": 0}
        with self._lock:
            for record in self.records:
                if record.get("status") not in ACTIVE: continue
                if record.get("status") == "pending_organize" and history_exists(record):
                    record["status"] = "completed"; record["updated_at"] = now.isoformat(timespec="seconds"); result["completed"] += 1; continue
                stamp = _time(record.get("submitted_at"))
                if stamp and (now - stamp).total_seconds() >= max(1, int(timeout_hours)) * 3600:
                    record["status"] = "timed_out"; record["error_code"] = "timeout"; record["error_message"] = "任务超时，订阅已恢复"; record["updated_at"] = now.isoformat(timespec="seconds")
                    if record.get("subscribe_id") is not None: restore_subscription(int(record["subscribe_id"]))
                    result["timed_out"] += 1
        return result
