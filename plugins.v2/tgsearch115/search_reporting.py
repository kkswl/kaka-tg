# -*- coding: utf-8 -*-
"""Per-subscription source reporting without credentials or resource URLs."""
from __future__ import annotations

from typing import Any, Dict, Iterable


SOURCE_LABELS = {"tg": "TG 频道", "site": "观影", "juying": "聚影"}


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
