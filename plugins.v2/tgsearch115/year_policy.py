# -*- coding: utf-8 -*-
"""Year policy: strict for movies, season-aware and advisory for TV."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from .media_types import is_tv_media


_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


@dataclass(frozen=True)
class YearDecision:
    candidate_year: Optional[int]
    target_year: Optional[int]
    target_season: Optional[int]
    target_season_year: Optional[int]
    policy: str
    hard_reject: bool = False


def extract_candidate_year(value: Any) -> Optional[int]:
    match = _YEAR_RE.search(str(value or ""))
    return int(match.group(1)) if match else None


def season_year(media: Any, season: Any) -> Optional[int]:
    try:
        season = int(season)
    except (TypeError, ValueError):
        return None
    years = getattr(media, "season_years", None) or {}
    value = years.get(season, years.get(str(season))) if isinstance(years, dict) else None
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def decide_year_policy(subscribe: Any, target_media: Any, candidate_title: Any) -> YearDecision:
    candidate = extract_candidate_year(candidate_title)
    try:
        target_year = int(getattr(subscribe, "year", None) or getattr(target_media, "year", None) or 0) or None
    except (TypeError, ValueError):
        target_year = None
    target_season = getattr(subscribe, "season", None)
    if is_tv_media(getattr(target_media, "type", None) or getattr(subscribe, "type", None)):
        season_value = season_year(target_media, target_season)
        if candidate is not None and season_value == candidate:
            return YearDecision(candidate, target_year, target_season, season_value, "tv_season_year_match")
        return YearDecision(candidate, target_year, target_season, season_value, "tv_year_deferred_to_tmdb")
    # Mirror MoviePilot movie behavior: current year or adjacent release year.
    valid = not target_year or candidate in {target_year - 1, target_year, target_year + 1}
    return YearDecision(candidate, target_year, target_season, None, "movie_strict_match" if valid else "year_conflict_rejected", not valid)
