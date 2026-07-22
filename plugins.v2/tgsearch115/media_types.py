# -*- coding: utf-8 -*-
"""MoviePilot media type compatibility helpers for legacy and current subscriptions."""
from __future__ import annotations

from typing import Any, Optional, Type


_TV_VALUES = {"tv", "电视剧"}
_MOVIE_VALUES = {"movie", "电影"}


def media_type_key(value: Any) -> str:
    """Return the stable plugin media-type key without depending on a database dialect."""
    raw_value = getattr(value, "value", value)
    text = str(raw_value or "").strip()
    lowered = text.casefold()
    if lowered in _TV_VALUES:
        return "TV"
    if lowered in _MOVIE_VALUES:
        return "MOVIE"
    return text.upper()


def is_tv_media(value: Any) -> bool:
    """Determine whether an enum or persisted legacy value represents television."""
    return media_type_key(value) == "TV"


def same_media_type(left: Any, right: Any) -> bool:
    """Compare MoviePilot enum values and persisted strings with one representation."""
    left_key = media_type_key(left)
    right_key = media_type_key(right)
    return bool(left_key and right_key and left_key == right_key)


def to_moviepilot_media_type(value: Any, media_type_cls: Type[Any]) -> Optional[Any]:
    """Convert a persisted subscription type to the MoviePilot ``MediaType`` enum."""
    if value is None or not media_type_cls:
        return None
    if isinstance(value, media_type_cls):
        return value
    key = media_type_key(value)
    enum_name = {"TV": "TV", "MOVIE": "MOVIE"}.get(key)
    if enum_name and hasattr(media_type_cls, enum_name):
        return getattr(media_type_cls, enum_name)
    try:
        return media_type_cls(value)
    except (TypeError, ValueError):
        return None


def subscription_notification_title(subscribe: Any) -> str:
    """Build a stable notification title that distinguishes movie years and TV seasons."""
    name = str(getattr(subscribe, "name", "") or "未命名订阅").strip()
    year = str(getattr(subscribe, "year", "") or "").strip()
    label = f"{name}（{year}）" if year else name
    if not is_tv_media(getattr(subscribe, "type", None)):
        return f"TG115 搜索完成：{label}"
    try:
        season = int(getattr(subscribe, "season", None))
    except (TypeError, ValueError):
        season = 1
    return f"TG115 搜索完成：{label}S{season:02d}"
