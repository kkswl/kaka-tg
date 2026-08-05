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


def classify_resource(
    torrent: Any,
    media_type: str = "unknown",
    identity_status: str = "unknown",
    mp_rule_status: str = "unknown",
    dedupe_status: str = "unknown",
    action: str = "",
    reject_reason: str = "",
) -> dict:
    title = str(getattr(torrent, "title", "") or getattr(torrent, "name", "") or "")
    description = str(getattr(torrent, "description", "") or "")
    text = " ".join((title, description))
    lower = text.lower()
    page_url = str(getattr(torrent, "page_url", "") or getattr(torrent, "url", "") or "")
    btih_match = _BTIH_RE.search(page_url)
    btih = str(btih_match.group(1) if btih_match else "").lower()
    valid_btih = bool(re.fullmatch(r"[0-9a-f]{40}|[a-z2-7]{32}", btih, re.IGNORECASE))
    resolution = next((value for pattern, value in (
        (r"(?:4320p|\b8k\b)", "4320p"),
        (r"(?:2160p|\b4k\b|\buhd\b)", "2160p"),
        (r"1080i", "1080i"),
        (r"1080p", "1080p"),
        (r"720p", "720p"),
        (r"(?:\b576[pi]\b|\b480[pi]\b|\bsd\b)", "SD"),
    ) if re.search(pattern, lower)), "unknown")
    quality = next((value for pattern, value in (
        (r"\bremux\b", "REMUX"),
        (r"blu[ ._-]?ray|b[dr]rip", "BluRay"),
        (r"web[ ._-]?dl", "WEB-DL"),
        (r"web[ ._-]?rip", "WEBRip"),
        (r"\bhdtv\b", "HDTV"),
        (r"\bdvdrip\b", "DVDRip"),
    ) if re.search(pattern, lower)), "unknown")
    video_codec = next((value for pattern, value in (
        (r"\bav1\b", "AV1"),
        (r"h[ .]?265|\bhevc\b|\bx265\b", "H.265"),
        (r"h[ .]?264|\bavc\b|\bx264\b", "H.264"),
        (r"mpeg[ ._-]?2", "MPEG-2"),
    ) if re.search(pattern, lower)), "unknown")
    audio_codec = next((value for pattern, value in (
        (r"truehd.*atmos|atmos.*truehd", "TrueHD Atmos"),
        (r"dts[ ._-]?hd[ ._-]?ma", "DTS-HD MA"),
        (r"dts[ ._-]?x", "DTS-X"),
        (r"\bdts\b", "DTS"),
        (r"\b(?:ddp|eac3|e-ac-3)\b", "DDP"),
        (r"\b(?:dd|ac3|ac-3)\b", "DD"),
        (r"\baac\b", "AAC"),
        (r"\bflac\b", "FLAC"),
    ) if re.search(pattern, lower)), "unknown")
    channels_match = re.search(r"\b([257]\.1(?:\.\d)?|[12]\.0)\b", lower)
    subtitle = next((value for pattern, value in (
        (r"无中字|无中文", "无中字"),
        (r"中英|双语字幕", "中英双语"),
        (r"简繁", "简繁"),
        (r"繁中|繁体", "繁中"),
        (r"外挂.{0,4}(?:中字|中文|简中)", "外挂中字"),
        (r"内(?:嵌|封).{0,4}(?:中字|中文|简中|chs)", "内嵌中字"),
        (r"简中|中字|中文字幕|中文|\bchs\b", "简中"),
    ) if re.search(pattern, lower)), "未知")
    language = next((value for pattern, value in (
        (r"国语|国粤|mandarin", "国语"),
        (r"粤语|cantonese", "粤语"),
        (r"英语|english", "英语"),
        (r"日语|japanese", "日语"),
        (r"韩语|korean", "韩语"),
    ) if re.search(pattern, lower)), "unknown")
    hdr = next((value for pattern, value in (
        (r"dolby[ ._-]?vision|\b(?:dovi|dv)\b", "Dolby Vision"),
        (r"hdr10\+", "HDR10+"),
        (r"\bhdr10\b|\bhdr\b", "HDR10"),
        (r"\bhlg\b", "HLG"),
        (r"\bsdr\b", "SDR"),
    ) if re.search(pattern, lower)), "unknown")
    year_match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
    season_match = re.search(r"\bS(\d{1,2})\b|第\s*(\d{1,2})\s*季", text, re.IGNORECASE)
    episode_match = re.search(r"\bE(\d{1,4})(?:\s*[-~]\s*E?(\d{1,4}))?\b", text, re.IGNORECASE)
    pan_type = str(getattr(torrent, "_tg115_pan_type", "") or "").lower()
    resource_type = "magnet" if pan_type == "magnet" or is_magnet_url(page_url) else "115_share" if pan_type == "115" or "115.com/" in page_url.lower() else "site_torrent" if pan_type == "torrent" else "cloud_share" if page_url.startswith("http") else "unknown"
    final_action = action or ("submit_115" if resource_type == "magnet" else "transfer_115_share" if resource_type == "115_share" else "reject")
    return {
        "source": str(getattr(torrent, "_tg115_source", "") or "unknown"),
        "source_name": str(getattr(torrent, "source_name", "") or getattr(torrent, "site_name", "") or "unknown"),
        "resource_type": resource_type,
        "media_type": media_type or "unknown",
        "title": title,
        "year": int(year_match.group(1)) if year_match else None,
        "season": int(next((value for value in season_match.groups() if value), 0)) if season_match else None,
        "episodes": f"E{int(episode_match.group(1)):02d}-E{int(episode_match.group(2)):02d}" if episode_match and episode_match.group(2) else f"E{int(episode_match.group(1)):02d}" if episode_match else "unknown",
        "resolution": resolution,
        "quality": quality,
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "audio_channels": channels_match.group(1) if channels_match else "unknown",
        "subtitle": subtitle,
        "language": language,
        "has_chinese_subtitle": subtitle not in {"无中字", "未知"},
        "hdr": hdr,
        "dolby_vision": hdr == "Dolby Vision",
        "complete_magnet": resource_type == "magnet" and is_magnet_url(page_url) and valid_btih,
        "valid_btih": valid_btih,
        "btih_prefix": btih[:12],
        "tmdb_id": getattr(torrent, "tmdb_id", None),
        "douban_id": str(getattr(torrent, "douban_id", "") or ""),
        "identity_status": identity_status or "unknown",
        "mp_rule_status": mp_rule_status or "unknown",
        "dedupe_status": dedupe_status or "unknown",
        "action": final_action,
        "reject_reason": reject_reason,
    }


def format_resource_classification(classification: dict) -> str:
    fields = (
        "source", "source_name", "resource_type", "media_type", "year", "season",
        "episodes", "resolution", "quality", "video_codec", "audio_codec",
        "audio_channels", "subtitle", "language", "hdr", "valid_btih",
        "btih_prefix", "identity_status", "mp_rule_status", "dedupe_status",
        "action", "reject_reason",
    )
    return " ".join(f"{field}={classification.get(field) if classification.get(field) not in (None, '') else 'unknown'}" for field in fields)


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
    """Try confirmed magnets through built-in 115, then eligible shares."""
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
        result.errors.append(f"插件内置 115 磁力离线任务提交失败: {message}")
        status = "failed"
