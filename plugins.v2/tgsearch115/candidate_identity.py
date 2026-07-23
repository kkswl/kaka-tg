# -*- coding: utf-8 -*-
"""Safe, bounded candidate preparation for MoviePilot identity matching."""
from __future__ import annotations

import re
from typing import Any, Iterable, List
from urllib.parse import unquote


_TMDB_RE = re.compile(r"(?:tmdb(?:id)?[=:_-]|\{tmdb[-_:])\s*(\d{3,})", re.I)
_YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_NOISE_RE = re.compile(
    r"(?:https?://\S+|提取码\s*[:：]?\s*\w+|访问码\s*[:：]?\s*\w+|\b(?:磁力|网盘|离线|种子|详情)\b|\d+(?:\.\d+)?\s*(?:GB|MB)|\b\d+\s*(?:seeds?|做种)\b)",
    re.I,
)
_BRACKET_RE = re.compile(r"[\[【(（].{0,80}[\]】)）]")


def extract_candidate_tmdb(value: Any) -> str:
    match = _TMDB_RE.search(str(value or ""))
    return match.group(1) if match else ""


def _compact(value: Any) -> str:
    text = unquote(str(value or "")).replace("\n", " ").strip()
    text = _NOISE_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:500].strip(" -|:")


def clean_identity_title(resource_title: Any, source_title: Any = "", year: Any = None,
                         description: Any = "") -> str:
    """Build one title for MetaInfo; never concatenate the same work twice."""
    resource = _compact(resource_title)
    source = _compact(source_title)
    desc = _compact(description)
    # File names carry quality/season information and are preferred. A site
    # source title is only a fallback or a short disambiguating prefix.
    title = resource or source or desc or "未命名资源"
    if source and source.casefold() not in title.casefold() and not resource:
        title = source
    # Avoid the common "Title (2025) Title ..." construction. Keep one year;
    # year policy still parses it and validates it later.
    years = _YEAR_RE.findall(title)
    if len(years) > 1:
        first = years[0]
        title = re.sub(rf"\b{re.escape(first)}\b", " ", title, count=len(years) - 1)
        title = re.sub(r"\s+", " ", title).strip()
    return title[:500]


def identity_candidate_score(candidate: Any, target_media: Any = None,
                             target_subscribe: Any = None) -> int:
    """Score only the bounded identity probe order, never transfer priority."""
    title = str(getattr(candidate, "title", "") or "")
    source_title = str(getattr(candidate, "_tg115_source_title", "") or "")
    source = str(getattr(candidate, "_tg115_source", "") or "").lower()
    target_names = [str(getattr(target_media, "title", "") or ""),
                    str(getattr(target_subscribe, "name", "") or "")]
    target_names.extend(str(x) for x in list(getattr(target_media, "names", None) or [])[:8])
    score = 0
    candidate_tmdb = extract_candidate_tmdb(" ".join((title, source_title)))
    target_tmdb = str(getattr(target_subscribe, "tmdbid", "") or getattr(target_media, "tmdb_id", "") or "")
    if candidate_tmdb and target_tmdb and candidate_tmdb == target_tmdb:
        score += 1000
    elif candidate_tmdb and target_tmdb and candidate_tmdb != target_tmdb:
        score -= 1000
    if getattr(candidate, "_tg115_metadata_verified", False):
        score += 250
    if source == "site":
        score += 100
    haystack = (title + " " + source_title).casefold()
    for name in target_names:
        name = name.strip().casefold()
        if name and len(name) >= 2 and name in haystack:
            score += 80
            break
    if _YEAR_RE.search(title):
        score += 10
    return score


def order_identity_candidates(candidates: Iterable[Any], target_media: Any = None,
                              target_subscribe: Any = None) -> List[Any]:
    indexed = list(enumerate(candidates or []))
    indexed.sort(key=lambda item: (-identity_candidate_score(item[1], target_media, target_subscribe), item[0]))
    return [item[1] for item in indexed]
