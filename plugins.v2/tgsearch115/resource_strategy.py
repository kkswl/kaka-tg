# -*- coding: utf-8 -*-
"""Candidate ordering for automatic MoviePilot/115 processing."""
import re
from typing import Callable, Iterable, List


_BTIH_RE = re.compile(r"(?:^|[?&])xt=urn:btih:([a-z0-9]+)", re.IGNORECASE)


def is_magnet_url(value: str) -> bool:
    return str(value or "").strip().lower().startswith("magnet:")


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
    """Return deduplicated观影 magnets first, then deduplicated 115 shares."""
    magnets = []
    shares = []
    seen_magnets = set()
    seen_shares = set()

    for torrent in torrents or []:
        url = str(getattr(torrent, "page_url", "") or "").strip()
        pan_type = str(getattr(torrent, "_tg115_pan_type", "") or "").lower()
        if prefer_site_magnet and pan_type == "magnet" and is_magnet_url(url):
            if str(getattr(torrent, "site_name", "") or "") != "观影":
                continue
            if is_tv and not bool(getattr(torrent, "_tg115_is_complete", False)):
                continue
            key = _magnet_key(url)
            if key and key not in seen_magnets:
                seen_magnets.add(key)
                magnets.append(torrent)
            continue

        if is_115_url(url):
            key = url.lower()
            if key not in seen_shares:
                seen_shares.add(key)
                shares.append(torrent)

    return magnets + shares
