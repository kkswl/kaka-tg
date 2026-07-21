# -*- coding: utf-8 -*-
"""Persistent CMS task records and conservative MoviePilot reconciliation."""
from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


_BTIH_RE = re.compile(r"(?:^|[?&])xt=urn:btih:([a-z0-9]+)", re.IGNORECASE)
ACTIVE_STATUSES = {"waiting", "submitted", "downloading", "pending_organize"}
TERMINAL_STATUSES = {"completed", "failed", "timed_out"}

# v4.7.0 public generic ledger.  The compatibility class below keeps the
# existing MoviePilot call signatures while old records are migrated safely.
try:
    from .offline_tasks import OfflineTaskLedger  # noqa: E402,F401
except ImportError:  # direct unit-test module loading
    OfflineTaskLedger = None  # type: ignore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def btih_from_magnet(magnet: str) -> str:
    match = _BTIH_RE.search(str(magnet or ""))
    return (match.group(1) if match else "").lower()


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class CmsTaskLedger:
    """Store only non-secret CMS task metadata in MoviePilot plugin data."""

    def __init__(self, records: Optional[Iterable[Dict[str, Any]]] = None,
                 now: Callable[[], datetime] = utc_now, max_records: int = 200):
        self._now = now
        self._lock = threading.RLock()
        self.max_records = max(20, int(max_records))
        self.records: List[Dict[str, Any]] = []
        for record in records or []:
            if isinstance(record, dict) and record.get("btih"):
                migrated = dict(record)
                migrated.pop("magnet", None)
                migrated["source"] = migrated.get("source") or "cms"
                migrated["error_message"] = migrated.get("error_message") or migrated.get("error") or ""
                self.records.append(migrated)
        self.records = self.records[-self.max_records:]

    def active_by_btih(self, btih: str) -> Optional[Dict[str, Any]]:
        key = str(btih or "").lower()
        with self._lock:
            for record in reversed(self.records):
                if record.get("btih") == key and record.get("status") in ACTIVE_STATUSES:
                    return record
        return None

    def add(self, magnet: str, title: str, subscribe: Any = None,
            status: str = "downloading") -> Dict[str, Any]:
        record, _created = self.reserve(magnet, title, subscribe, status)
        return record

    def reserve(self, magnet: str, title: str, subscribe: Any = None,
                status: str = "waiting", source: str = "cms", task_id: str = "",
                target_cid: Any = "") -> Tuple[Dict[str, Any], bool]:
        """Atomically reserve a BTIH before the external CMS request is sent."""
        btih = btih_from_magnet(magnet)
        if not btih:
            raise ValueError("磁力链接缺少有效 BTIH")
        with self._lock:
            existing = self.active_by_btih(btih)
            if existing:
                return existing, False
            now_text = self._now().isoformat(timespec="seconds")
            record = {
                "source": str(source or "cms"),
                "btih": btih,
                "title": str(title or "未命名资源")[:240],
                "subscribe_id": getattr(subscribe, "id", None) if subscribe else None,
                "tmdb_id": getattr(subscribe, "tmdbid", None) if subscribe else None,
                "douban_id": getattr(subscribe, "doubanid", None) if subscribe else None,
                "media_type": str(getattr(subscribe, "type", "") or "") if subscribe else "",
                "season": getattr(subscribe, "season", None) if subscribe else None,
                "status": status if status in ACTIVE_STATUSES else "waiting",
                "task_id": str(task_id or ""),
                "target_cid": str(target_cid or ""),
                "progress": None,
                "error_code": "",
                "error_message": "",
                "retry_count": 0,
                "submitted_at": now_text,
                "updated_at": now_text,
                "error": "",
            }
            self.records.append(record)
            self.records = self.records[-self.max_records:]
            return record, True

    def update(self, btih: str, status: str, error: str = "", **fields: Any) -> Optional[Dict[str, Any]]:
        key = str(btih or "").lower()
        with self._lock:
            for record in reversed(self.records):
                if record.get("btih") == key:
                    record["status"] = status
                    record["updated_at"] = self._now().isoformat(timespec="seconds")
                    record["error"] = str(error or "")[:300]
                    record["error_message"] = record["error"]
                    for key in ("task_id", "target_cid", "download_name", "progress", "error_code", "error_message", "retry_count", "source"):
                        if key in fields:
                            record[key] = fields[key]
                    return record
        return None

    def latest(self, btih: str) -> Optional[Dict[str, Any]]:
        key = str(btih or "").lower()
        with self._lock:
            for record in reversed(self.records):
                if record.get("btih") == key:
                    return record
        return None

    def restart(self, btih: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self.latest(btih)
            if not record:
                return None
            now_text = self._now().isoformat(timespec="seconds")
            record.update({
                "status": "downloading",
                "submitted_at": now_text,
                "updated_at": now_text,
                "error": "",
            })
            return record

    def reconcile(
        self,
        timeout_hours: int,
        subscription_exists: Callable[[int], bool],
        history_exists: Callable[[Dict[str, Any]], bool],
        restore_subscription: Callable[[int], None],
        direct_timeout_hours: Optional[int] = None,
    ) -> Dict[str, int]:
        """Complete records observed by MP, or time out and restore subscriptions."""
        now = self._now()
        result = {"completed": 0, "failed": 0, "timed_out": 0}
        with self._lock:
            for record in self.records:
                if record.get("status") not in ACTIVE_STATUSES:
                    continue
                sid = record.get("subscribe_id")
                if sid and history_exists(record):
                    record["status"] = "completed"
                    record["updated_at"] = now.isoformat(timespec="seconds")
                    record["error"] = ""
                    result["completed"] += 1
                    continue
                if sid and not subscription_exists(int(sid)):
                    record["status"] = "failed"
                    record["updated_at"] = now.isoformat(timespec="seconds")
                    record["error"] = "订阅已不存在，但 MoviePilot 没有对应完成历史"
                    result["failed"] += 1
                    continue
                submitted_at = _parse_time(record.get("submitted_at"))
                hours = direct_timeout_hours if record.get("source") == "115_direct" and direct_timeout_hours is not None else timeout_hours
                timeout_seconds = max(1, int(hours)) * 3600
                if not submitted_at or (now - submitted_at).total_seconds() < timeout_seconds:
                    continue
                record["status"] = "timed_out"
                record["updated_at"] = now.isoformat(timespec="seconds")
                record["error"] = "CMS/MP 在超时时间内未确认完成，订阅已恢复"
                if sid:
                    restore_subscription(int(sid))
                result["timed_out"] += 1
        return result

    def public_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            result = []
            for item in reversed(self.records[-max(1, int(limit)):]):
                public = dict(item)
                public.pop("magnet", None)
                public.pop("error", None)
                task_id = str(public.get("task_id") or "")
                public["task_id"] = f"{task_id[:12]}..." if len(task_id) > 12 else task_id
                result.append(public)
            return result

    def dump_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self.records]

    def clear_if_idle(self) -> Tuple[int, int]:
        """Clear ledger history only when no active task would lose tracking."""
        with self._lock:
            active = sum(
                1 for item in self.records if item.get("status") in ACTIVE_STATUSES
            )
            if active:
                return 0, active
            cleared = len(self.records)
            self.records.clear()
            return cleared, 0
