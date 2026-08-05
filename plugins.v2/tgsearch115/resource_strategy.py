# -*- coding: utf-8 -*-
"""Candidate ordering for automatic MoviePilot/115 processing."""
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional, Tuple

try:
    from .magnet_failover import (
        FALLBACK_TO_MOVIEPILOT,
        SUBMIT_NEXT,
        advance_magnet_candidate,
        build_magnet_queue,
    )
except ImportError:
    import importlib.util
    import sys
    from pathlib import Path

    _failover_path = Path(__file__).with_name("magnet_failover.py")
    _failover_spec = importlib.util.spec_from_file_location("tg115_magnet_failover", _failover_path)
    _failover_module = importlib.util.module_from_spec(_failover_spec)
    sys.modules[_failover_spec.name] = _failover_module
    _failover_spec.loader.exec_module(_failover_module)
    FALLBACK_TO_MOVIEPILOT = _failover_module.FALLBACK_TO_MOVIEPILOT
    SUBMIT_NEXT = _failover_module.SUBMIT_NEXT
    advance_magnet_candidate = _failover_module.advance_magnet_candidate
    build_magnet_queue = _failover_module.build_magnet_queue


_BTIH_RE = re.compile(r"(?:^|[?&])xt=urn:btih:([a-z0-9]+)", re.IGNORECASE)
_CHINESE_SUBTITLE_RE = re.compile(
    r"(?:中文字幕|国语中字|中字|中文|简中|繁中|简繁|内封.{0,6}(?:简|繁|中)|\b(?:chs|cht|chinese)\b)",
    re.IGNORECASE,
)
_AUTO_MAGNET_QUALITY_RE = re.compile(r"(?:1080[pi]?|2160p|\b4k\b|\buhd\b)", re.IGNORECASE)


def is_magnet_url(value: str) -> bool:
    return str(value or "").strip().lower().startswith("magnet:")


def filter_with_offline_seed_override(
    torrents: Iterable,
    filter_callback: Callable[[List[Any]], List[Any]],
) -> List[Any]:
    """Ignore swarm seed thresholds for 115 server-side magnet offline tasks."""
    torrent_list = list(torrents or [])
    original_seeders = []
    for torrent in torrent_list:
        url = str(
            getattr(torrent, "enclosure", "")
            or getattr(torrent, "page_url", "")
            or ""
        )
        if is_magnet_url(url):
            original_seeders.append((torrent, getattr(torrent, "seeders", 0)))
            setattr(torrent, "seeders", 2_147_483_647)
    try:
        return filter_callback(torrent_list)
    finally:
        for torrent, seeders in original_seeders:
            setattr(torrent, "seeders", seeders)


def _magnet_key(value: str) -> str:
    url = str(value or "").strip()
    match = _BTIH_RE.search(url)
    return (match.group(1) if match else url).lower()


def select_auto_candidates(
    torrents: Iterable,
    prefer_site_magnet: bool,
    is_tv: bool,
    is_115_url: Callable[[str], bool],
) -> List:
    """Order safe candidates without allowing aggregate sources to outrank direct sources."""
    buckets = {
        "tg": [], "site_share": [], "pansou_share": [],
        "site_magnet": [], "pansou_magnet": [], "juying": [],
    }
    bucket_seen = {name: set() for name in buckets}

    def add(bucket: str, key: str, torrent: Any) -> None:
        if key and key not in bucket_seen[bucket]:
            bucket_seen[bucket].add(key)
            buckets[bucket].append(torrent)

    for torrent in torrents or []:
        url = str(getattr(torrent, "page_url", "") or "").strip()
        pan_type = str(getattr(torrent, "_tg115_pan_type", "") or "").lower()
        source = str(getattr(torrent, "_tg115_source", "") or "").lower()
        description = " ".join((
            str(getattr(torrent, "title", "") or ""),
            str(getattr(torrent, "description", "") or ""),
        ))
        has_chinese_subtitle = bool(_CHINESE_SUBTITLE_RE.search(description))

        if source == "tg" and is_115_url(url):
            add("tg", url.lower(), torrent)
            continue

        if source == "site" and is_115_url(url) and has_chinese_subtitle:
            add("site_share", url.lower(), torrent)
            continue

        if source == "pansou" and is_115_url(url) and has_chinese_subtitle:
            add("pansou_share", url.lower(), torrent)
            continue

        if source == "site" and prefer_site_magnet and pan_type == "magnet" and is_magnet_url(url):
            if not has_chinese_subtitle or not _AUTO_MAGNET_QUALITY_RE.search(description):
                continue
            if is_tv and not bool(getattr(torrent, "_tg115_is_complete", False)):
                continue
            add("site_magnet", _magnet_key(url), torrent)
            continue

        if source == "pansou" and prefer_site_magnet and pan_type == "magnet" and is_magnet_url(url):
            if not has_chinese_subtitle or not _AUTO_MAGNET_QUALITY_RE.search(description):
                continue
            if is_tv and not bool(getattr(torrent, "_tg115_is_complete", False)):
                continue
            add("pansou_magnet", _magnet_key(url), torrent)
            continue

        if source == "juying" and is_115_url(url):
            add("juying", url.lower(), torrent)

    ordered = (
        buckets["tg"] + buckets["site_share"] + buckets["pansou_share"]
        + buckets["site_magnet"] + buckets["pansou_magnet"] + buckets["juying"]
    )
    result = []
    seen = set()
    for torrent in ordered:
        url = str(getattr(torrent, "page_url", "") or "").strip()
        key = ("magnet", _magnet_key(url)) if is_magnet_url(url) else ("share", url.lower())
        if key not in seen:
            seen.add(key)
            result.append(torrent)
    return result


@dataclass
class CandidateExecutionResult:
    candidate: Optional[Any] = None
    message: str = ""
    via_magnet: bool = False
    recognition_attempts: int = 0
    errors: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)

    def rejection_summary(self) -> str:
        """Return a safe, stable reason without leaking candidate data."""
        if not self.rejection_reasons:
            return ""
        counts = {}
        for reason in self.rejection_reasons:
            counts[reason] = counts.get(reason, 0) + 1
        return max(counts, key=counts.get)


def _identity_rejection_category(identity: Any) -> str:
    reason = str(getattr(identity, "reason", "") or "")
    source = str(getattr(identity, "match_source", "") or "")
    if source == "identity_unavailable" or "识别" in reason:
        return "MoviePilot 媒体识别不可用"
    if "TMDB ID 不匹配" in reason:
        return "TMDB ID 不一致"
    if "豆瓣 ID 不匹配" in reason:
        return "豆瓣 ID 不一致"
    if "季号" in reason:
        return "候选季号不匹配"
    if "媒体类型" in reason:
        return "候选媒体类型不一致"
    if "标题" in reason or "别名" in reason or "年份" in reason:
        return "候选标题、年份或别名不匹配"
    if "缺少 TMDB/豆瓣 ID" in reason:
        return "订阅缺少媒体 ID，已安全拒绝"
    return "候选未通过 MoviePilot/TMDB 身份确认"


def execute_auto_candidates(
    candidates: Iterable,
    confirm_identity: Callable[[Any], Any],
    submit_magnet: Callable[[Any], Tuple[bool, str]],
    transfer_share: Callable[[Any], Tuple[bool, str]],
    max_recognition_attempts: int = 3,
    max_magnet_attempts: int = 5,
    magnet_failover_enabled: bool = True,
    magnet_queue_timeout_hours: int = 12,
) -> CandidateExecutionResult:
    """Try magnets then shares while preserving the safe CMS failure fallback."""
    result = CandidateExecutionResult()
    candidate_list = list(candidates or [])
    first_magnet = next(
        (index for index, item in enumerate(candidate_list)
         if is_magnet_url(getattr(item, "page_url", "") or "")),
        len(candidate_list),
    )
    magnet_candidates = [item for item in candidate_list if is_magnet_url(getattr(item, "page_url", "") or "")]
    magnet_by_btih = {_magnet_key(getattr(item, "page_url", "") or ""): item for item in magnet_candidates}
    non_magnet_candidates = [item for item in candidate_list[:first_magnet] if not is_magnet_url(getattr(item, "page_url", "") or "")]
    trailing_non_magnets = [item for item in candidate_list[first_magnet:] if not is_magnet_url(getattr(item, "page_url", "") or "")]

    for candidate in non_magnet_candidates:
        identity = confirm_identity(candidate)
        if bool(getattr(identity, "recognition_attempted", False)):
            result.recognition_attempts += 1
        if not bool(getattr(identity, "confirmed", False)):
            result.rejection_reasons.append(_identity_rejection_category(identity))
            if result.recognition_attempts >= max_recognition_attempts:
                return result
            continue
        ok, message = transfer_share(candidate)
        if ok:
            result.candidate = candidate
            result.message = message
            return result
        result.errors.append(f"115 转存失败: {message}")

    if not magnet_candidates:
        return result
    queue = build_magnet_queue(
        media_key="execution",
        queue_key="execution",
        candidates=magnet_candidates,
        max_attempts=min(max_magnet_attempts if magnet_failover_enabled else 1, len(magnet_candidates)),
        timeout_hours=magnet_queue_timeout_hours,
    )
    status = "failed"
    while True:
        action = advance_magnet_candidate(queue, status)
        if action == FALLBACK_TO_MOVIEPILOT:
            for candidate in trailing_non_magnets:
                identity = confirm_identity(candidate)
                if bool(getattr(identity, "recognition_attempted", False)):
                    result.recognition_attempts += 1
                if not bool(getattr(identity, "confirmed", False)):
                    result.rejection_reasons.append(_identity_rejection_category(identity))
                    continue
                ok, message = transfer_share(candidate)
                if ok:
                    result.candidate = candidate
                    result.message = message
                    return result
                result.errors.append(f"115 转存失败: {message}")
            result.errors.append("磁力候选已耗尽，交由 MoviePilot 原生搜索")
            return result
        if action != SUBMIT_NEXT:
            return result
        queue_candidate = queue.current
        candidate = magnet_by_btih.get(queue_candidate.get("btih")) if queue_candidate else None
        if candidate is None:
            return result
        setattr(candidate, "_tg115_candidate_position", int(queue_candidate.get("position") or 0))
        setattr(candidate, "_tg115_candidate_total", min(queue.max_attempts, len(queue.candidates)))
        identity = confirm_identity(candidate)
        if bool(getattr(identity, "recognition_attempted", False)):
            result.recognition_attempts += 1
        if not bool(getattr(identity, "confirmed", False)):
            result.rejection_reasons.append(_identity_rejection_category(identity))
            status = "failed"
            if result.recognition_attempts >= max_recognition_attempts:
                return result
            continue
        ok, message = submit_magnet(candidate)
        if ok:
            result.candidate = candidate
            result.message = message
            result.via_magnet = True
            return result
        result.errors.append(f"CMS 115 磁力离线任务提交失败: {message}")
        status = "failed"


def submit_magnet_with_fallback(
    mode: str,
    submit_direct: Callable[[], Tuple[bool, str]],
    submit_cms: Callable[[], Tuple[bool, str]],
) -> Tuple[bool, str, str]:
    """Apply direct/CMS mode without treating task creation as completion."""
    normalized = str(mode or "direct_then_cms").lower()
    if normalized in {"direct_115", "direct_then_cms"}:
        ok, message = submit_direct()
        if ok:
            return True, message, "115_direct"
        if normalized == "direct_115":
            return False, message, "115_direct"
    ok, message = submit_cms()
    return ok, message, "cms"
