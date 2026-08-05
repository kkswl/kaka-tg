from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Set


_BTih_RE = re.compile(r"(?:^|[?&])xt=urn:btih:([^&]+)", re.IGNORECASE)

ACTIVE_STATES = {
    "selected", "submitting", "submitted", "downloading", "downloaded",
    "waiting_organize", "organizing", "unknown", "reconciling",
}
UNKNOWN_STATES = {"unknown", "submit_timeout", "response_lost", "query_timeout", "query_error", "service_unavailable"}
SWITCHABLE_FAILURE_STATES = {
    "cancelled", "failed", "no_resource", "invalid_magnet", "task_rejected",
    "offline_parse_failed", "no_files",
}
COMPLETED_STATES = {"completed", "library_confirmed"}
INFLIGHT_COVERAGE_STATES = {
    "selected", "submitting", "submitted", "downloading", "downloaded",
    "waiting_organize", "unknown", "reconciling",
}

WAIT = "WAIT"
RECONCILE = "RECONCILE"
COMPLETE = "COMPLETE"
SUBMIT_NEXT = "SUBMIT_NEXT"
FALLBACK_TO_MOVIEPILOT = "FALLBACK_TO_MOVIEPILOT"
HOLD = "HOLD"


def btih_from_magnet(value: Any) -> str:
    match = _BTih_RE.search(str(value or "").strip())
    return match.group(1).lower() if match else ""


def normalize_candidate(candidate: Any, position: int) -> Dict[str, Any]:
    url = str(getattr(candidate, "page_url", "") or getattr(candidate, "enclosure", "") or "").strip()
    return {
        "candidate_id": f"candidate-{position}",
        "position": position,
        "source": str(getattr(candidate, "_tg115_source", "") or ""),
        "upstream_source": str(getattr(candidate, "_tg115_upstream_source", "") or ""),
        "title": str(getattr(candidate, "title", "") or "")[:240],
        "btih": btih_from_magnet(url),
        "resource_key": f"magnet:{btih_from_magnet(url)}",
        "attempt_state": "pending",
        "attempt_count": 0,
        "task_id": "",
        "failure_category": "",
        "submitted_at": "",
        "finished_at": "",
        "season": getattr(candidate, "_tg115_season", None),
        "declared_episodes": list(getattr(candidate, "_tg115_declared_episodes", []) or []),
        "is_complete": bool(getattr(candidate, "_tg115_is_complete", False)),
    }


@dataclass
class MagnetCandidateQueue:
    media_key: str
    queue_key: str
    candidates: List[Dict[str, Any]]
    max_attempts: int = 5
    current_index: Optional[int] = None
    state: str = "ready"
    owner: str = "tg115"
    attempted_btih: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.max_attempts = max(1, min(10, int(self.max_attempts)))
        self._deduplicate()

    def _deduplicate(self) -> None:
        seen: Set[str] = set()
        result: List[Dict[str, Any]] = []
        for item in self.candidates:
            btih = str(item.get("btih") or "").lower()
            if not btih or btih in seen:
                continue
            seen.add(btih)
            result.append(item)
        self.candidates = result

    @property
    def current(self) -> Optional[Dict[str, Any]]:
        if self.current_index is None or not 0 <= self.current_index < len(self.candidates):
            return None
        return self.candidates[self.current_index]

    def next_unattempted(self) -> Optional[Dict[str, Any]]:
        if len(self.attempted_btih) >= self.max_attempts:
            return None
        for index, item in enumerate(self.candidates):
            if item.get("btih") in self.attempted_btih:
                continue
            self.current_index = index
            item["attempt_state"] = "selected"
            item["attempt_count"] = int(item.get("attempt_count") or 0) + 1
            self.attempted_btih.add(item["btih"])
            self.state = "claimed"
            self.updated_at = datetime.now(timezone.utc)
            return item
        return None

    def mark(self, status: str, reason: str = "") -> None:
        item = self.current
        if item is not None:
            item["attempt_state"] = status
            item["failure_category"] = reason if status in SWITCHABLE_FAILURE_STATES else ""
            if status in SWITCHABLE_FAILURE_STATES or status in COMPLETED_STATES:
                item["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.state = "monitoring" if status in ACTIVE_STATES else ("completed" if status in COMPLETED_STATES else "switch_pending")
        self.updated_at = datetime.now(timezone.utc)

    def dump(self) -> Dict[str, Any]:
        return {
            "media_key": self.media_key, "queue_key": self.queue_key,
            "candidates": [dict(item) for item in self.candidates],
            "max_attempts": self.max_attempts, "current_index": self.current_index,
            "state": self.state, "owner": self.owner,
            "attempted_btih": sorted(self.attempted_btih),
            "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else "",
        }


def advance_magnet_candidate(queue: MagnetCandidateQueue, current_task_status: str, now: Optional[datetime] = None) -> str:
    status = str(current_task_status or "").strip().lower()
    now = now or datetime.now(timezone.utc)
    if queue.owner != "tg115":
        return HOLD
    if queue.expires_at and now >= queue.expires_at:
        queue.state = "fallback_pending"
        return FALLBACK_TO_MOVIEPILOT
    if status in UNKNOWN_STATES:
        queue.state = "unknown"
        return RECONCILE
    if status in ACTIVE_STATES:
        queue.state = "monitoring"
        return WAIT
    if status in COMPLETED_STATES:
        queue.state = "completed"
        queue.owner = "none"
        return COMPLETE
    if status not in SWITCHABLE_FAILURE_STATES:
        return HOLD
    queue.mark(status, status)
    if queue.next_unattempted():
        return SUBMIT_NEXT
    queue.state = "fallback_pending"
    return FALLBACK_TO_MOVIEPILOT


def build_magnet_queue(media_key: str, queue_key: str, candidates: Iterable[Any], max_attempts: int = 5, now: Optional[datetime] = None, timeout_hours: int = 12) -> MagnetCandidateQueue:
    now = now or datetime.now(timezone.utc)
    return MagnetCandidateQueue(media_key, queue_key, [normalize_candidate(item, index + 1) for index, item in enumerate(candidates)], max_attempts=max_attempts, created_at=now, updated_at=now, expires_at=now + timedelta(hours=max(1, int(timeout_hours))))


def restore_magnet_queue(payload: Dict[str, Any]) -> MagnetCandidateQueue:
    def parse_time(value: Any) -> Optional[datetime]:
        if not value:
            return None
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    return MagnetCandidateQueue(
        media_key=str(payload.get("media_key") or ""),
        queue_key=str(payload.get("queue_key") or ""),
        candidates=[dict(item) for item in payload.get("candidates") or [] if isinstance(item, dict)],
        max_attempts=int(payload.get("max_attempts") or 5),
        current_index=payload.get("current_index"),
        state=str(payload.get("state") or "ready"),
        owner=str(payload.get("owner") or "tg115"),
        attempted_btih={str(item).lower() for item in payload.get("attempted_btih") or []},
        created_at=parse_time(payload.get("created_at")) or datetime.now(timezone.utc),
        updated_at=parse_time(payload.get("updated_at")) or datetime.now(timezone.utc),
        expires_at=parse_time(payload.get("expires_at")),
    )


def inflight_episodes(queue: MagnetCandidateQueue) -> Set[int]:
    current = queue.current
    if queue.owner != "tg115" or not current or current.get("attempt_state") not in INFLIGHT_COVERAGE_STATES:
        return set()
    return {int(item) for item in current.get("declared_episodes") or [] if str(item).isdigit() and int(item) > 0}


def effective_missing_episodes(library_missing: Iterable[int], queue: Optional[MagnetCandidateQueue] = None, moviepilot_downloading: Iterable[int] = ()) -> Set[int]:
    missing = {int(item) for item in library_missing or [] if int(item) > 0}
    covered = inflight_episodes(queue) if queue else set()
    downloading = {int(item) for item in moviepilot_downloading or [] if int(item) > 0}
    return missing - covered - downloading
