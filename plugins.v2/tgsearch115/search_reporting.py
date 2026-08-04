# -*- coding: utf-8 -*-
"""Per-subscription source reporting without credentials or resource URLs."""
from __future__ import annotations

from typing import Any, Dict, Iterable


SOURCE_LABELS = {"tg": "TG 频道", "site": "观影", "pansou": "PanSou", "juying": "聚影"}


def candidate_source(candidate: Any) -> str:
    if isinstance(candidate, dict):
        value = candidate.get("source") or candidate.get("_tg115_source")
    else:
        value = getattr(candidate, "_tg115_source", "") or getattr(candidate, "source", "")
    return str(value or "").strip().lower()


def candidate_upstream_source(candidate: Any) -> str:
    if isinstance(candidate, dict):
        value = candidate.get("upstream_source") or candidate.get("_tg115_upstream_source")
    else:
        value = getattr(candidate, "_tg115_upstream_source", "") or getattr(candidate, "upstream_source", "")
    return str(value or "").strip()


def format_selected_source(candidate: Any) -> str:
    source = candidate_source(candidate)
    upstream = candidate_upstream_source(candidate)
    label = SOURCE_LABELS.get(source, source or "未知来源")
    if source == "pansou" and upstream:
        return f"{label}（上游：{upstream}）"
    return label


def _candidate_key(candidate: Any) -> tuple:
    if isinstance(candidate, dict):
        url = str(candidate.get("share_url") or "").strip().casefold()
        title = str(candidate.get("resource_title") or "").strip().casefold()
    else:
        url = str(getattr(candidate, "share_url", "") or "").strip().casefold()
        title = str(getattr(candidate, "resource_title", "") or "").strip().casefold()
    return (url,) if url else (title,)


class SearchReport:
    def __init__(self, enabled: Dict[str, bool]):
        self._states = {
            source: {
                "enabled": bool(enabled.get(source)),
                "keys": set(),
                "queries": 0,
                "cache_hits": 0,
                "status": "waiting" if enabled.get(source) else "disabled",
            }
            for source in SOURCE_LABELS
        }

    def record(self, source: str, candidates: Iterable[Any], cached: bool = False) -> None:
        state = self._states.get(source)
        if not state:
            return
        state["queries"] += 1
        state["cache_hits"] += int(bool(cached))
        state["status"] = "ok"
        for candidate in candidates or []:
            key = _candidate_key(candidate)
            if any(key):
                state["keys"].add(key)

    def mark(self, source: str, status: str) -> None:
        state = self._states.get(source)
        if state:
            state["status"] = status

    def counts(self) -> Dict[str, int]:
        return {source: len(state["keys"]) for source, state in self._states.items()}

    def text(self) -> str:
        parts = []
        for source, label in SOURCE_LABELS.items():
            state = self._states[source]
            status = state["status"]
            if status == "disabled":
                detail = "未启用"
            elif status == "cooldown":
                detail = "冷却中"
            elif status == "error":
                detail = "请求失败"
            elif status == "waiting":
                detail = "未执行"
            else:
                detail = f"{len(state['keys'])} 条"
                if state["cache_hits"]:
                    detail += "（含缓存）"
            parts.append(f"{label} {detail}")
        return "；".join(parts)
