# -*- coding: utf-8 -*-
"""Persistent CMS task records and conservative MoviePilot reconciliation."""
from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


_BTIH_RE = re.compile(r"(?:^|[?&])xt=urn:btih:([a-z0-9]+)", re.IGNORECASE)
ACTIVE_STATUSES = {"waiting", "submitted", "downloading", "pending_organize", "unknown"}


def has_explicit_clear_confirmation(payload: Any) -> bool:
    """Require an exact opt-in before destructive ledger cleanup."""
    return isinstance(payload, dict) and payload.get("confirm") is True
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


def _normalize_media_type(value: Any) -> str:
    text = str(getattr(value, "value", value) or "").upper()
    if "MOVIE" in text or "电影" in text:
        return "MOVIE"
    if "TV" in text or "电视剧" in text:
        return "TV"
    return text


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
                "position": 0,
                "candidate_total": 0,
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
                    for key in ("task_id", "target_cid", "download_name", "progress", "error_code", "error_message", "retry_count", "source", "completion_notified"):
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

    def attempted_by_subscription(self, subscribe_id: Any) -> set:
        with self._lock:
            return {
                str(record.get("btih") or "").lower()
                for record in self.records
                if record.get("subscribe_id") == subscribe_id and record.get("btih")
            }

    def active_by_subscription(self, subscribe_id: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            for record in reversed(self.records):
                if record.get("subscribe_id") == subscribe_id and record.get("status") in ACTIVE_STATUSES:
                    return record
        return None

    def match_transfer_complete(
        self,
        tmdb_id: Any = None,
        douban_id: Any = None,
        media_type: str = "",
        season: Any = None,
    ) -> Optional[Dict[str, Any]]:
        tmdb_key = str(tmdb_id or "").strip()
        douban_key = str(douban_id or "").strip()
        if not tmdb_key and not douban_key:
            return None
        event_type = _normalize_media_type(media_type)
        event_season = str(season).strip() if season is not None else ""
        matches = []
        with self._lock:
            for record in self.records:
                if record.get("status") != "pending_organize":
                    continue
                record_tmdb = str(record.get("tmdb_id") or "").strip()
                record_douban = str(record.get("douban_id") or "").strip()
                if tmdb_key:
                    if not record_tmdb or record_tmdb != tmdb_key:
                        continue
                elif not record_douban or record_douban != douban_key:
                    continue
                record_type = _normalize_media_type(record.get("media_type"))
                if event_type and record_type and event_type != record_type:
                    continue
                record_season = record.get("season")
                if record_season is not None:
                    if not event_season or str(record_season).strip() != event_season:
                        continue
                matches.append(record)
            return matches[0] if len(matches) == 1 else None

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
        unknown_timeout_minutes: Optional[int] = None,
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
                    record["completion_notified"] = False
                    result["completed"] += 1
                    continue
                if sid and not subscription_exists(int(sid)):
                    record["status"] = "failed"
                    record["updated_at"] = now.isoformat(timespec="seconds")
                    record["error"] = "订阅已不存在，但 MoviePilot 没有对应完成历史"
                    result["failed"] += 1
                    continue
                submitted_at = _parse_time(record.get("submitted_at"))
                if record.get("status") == "unknown" and unknown_timeout_minutes is not None:
                    timeout_seconds = max(1, int(unknown_timeout_minutes)) * 60
                else:
                    hours = direct_timeout_hours if record.get("source") == "115_direct" and direct_timeout_hours is not None else timeout_hours
                    timeout_seconds = max(1, int(hours)) * 3600
                if not submitted_at or (now - submitted_at).total_seconds() < timeout_seconds:
                    continue
                was_unknown = record.get("status") == "unknown"
                record["status"] = "timed_out"
                record["updated_at"] = now.isoformat(timespec="seconds")
                record["error"] = (
                    "115 未知状态对账超时，订阅已恢复"
                    if was_unknown
                    else "MoviePilot 在超时时间内未确认完成，订阅已恢复"
                )
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
