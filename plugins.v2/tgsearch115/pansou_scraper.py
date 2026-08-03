# -*- coding: utf-8 -*-
"""PanSou HTTP client and result normalizer.

PanSou is an aggregate search service.  Its response shape differs between
releases, so this module deliberately normalizes only public resource fields
and never exposes credentials or raw responses to callers.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlparse

from app.log import logger

from .site_scraper import SiteHit, _classify_pan


_TYPE_MAP = {
    "115": "115", "115网盘": "115", "magnet": "magnet", "bt": "magnet",
    "ed2k": "magnet", "quark": "quark", "夸克": "quark", "baidu": "baidu",
    "百度": "baidu", "aliyun": "aliyun", "alipan": "aliyun", "阿里": "aliyun",
    "xunlei": "xunlei", "迅雷": "xunlei", "tianyi": "cloud189", "cloud189": "cloud189",
    "189": "cloud189", "uc": "uc", "pikpak": "pikpak", "123": "123",
}
_MAGNET_RE = re.compile(r"magnet:\?[^\s<>\"']+", re.I)
_ED2K_RE = re.compile(r"ed2k://[^\s<>\"']+", re.I)


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        if any(key in value for key in (
            "url", "link", "share_url", "share_link", "magnet",
        )):
            return [value]
        result: List[Any] = []
        for item in value.values():
            result.extend(_as_list(item))
        return result
    return [value]


class PanSouClient:
    """Synchronous PanSou client used by the existing bounded search worker."""

    def __init__(self, base_url: str, token: str = "", timeout: float = 20.0,
                 proxy: Optional[str] = None, max_results: int = 100) -> None:
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.token = str(token or "").strip()
        self.timeout = max(3.0, float(timeout or 20.0))
        self.proxy = (proxy or "").strip() or None
        self.max_results = min(100, max(1, int(max_results or 100)))
        self.last_error_status: Optional[int] = None
        self.last_error: str = ""
        self.last_result_count = 0
        self.last_request_at = ""
        self.last_success_at = ""
        self.type_counts: Dict[str, int] = {}
        self._http = None

    def is_ready(self) -> bool:
        return bool(self.base_url)

    def close(self) -> None:
        client, self._http = self._http, None
        if client:
            try:
                client.close()
            except Exception:
                pass

    def _client(self):
        if self._http is None:
            import httpx
            kwargs: Dict[str, Any] = {
                "timeout": self.timeout,
                "follow_redirects": True,
                "headers": {"User-Agent": "MoviePilot-TgSearch115", "Accept": "application/json"},
                "mounts": {
                    "https://": httpx.HTTPTransport(trust_env=False),
                    "http://": httpx.HTTPTransport(trust_env=False),
                },
            }
            if self.proxy:
                kwargs["proxy"] = self.proxy
            self._http = httpx.Client(**kwargs)
        return self._http

    def _headers(self) -> Dict[str, str]:
        # The token is intentionally kept out of logs and normalized payloads.
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def health_check(self) -> Tuple[bool, str]:
        if not self.is_ready():
            return False, "PanSou 地址未配置"
        try:
            response = self._request("GET", self.base_url + "/")
            self.last_error_status = response.status_code if response.status_code >= 400 else None
            if response.status_code >= 400:
                self.last_error = self.safe_error(response.status_code, response.text)
                return False, self.last_error
            return True, "PanSou 服务可访问"
        except Exception as exc:
            self.last_error_status = None
            self.last_error = self.safe_error(None, exc)
            return False, self.last_error

    def search(self, keyword: str, year: Optional[int] = None, media_type: Any = None,
               season: Optional[int] = None, refresh: bool = False,
               cloud_types: Optional[Iterable[str]] = None,
               title_en: str = "") -> List[SiteHit]:
        self.last_error_status = None
        self.last_error = ""
        self.last_result_count = 0
        self.type_counts = {}
        keyword = str(keyword or "").strip()
        if not self.is_ready() or not keyword:
            return []
        clouds = [str(item).strip().lower() for item in (cloud_types or ("115", "magnet")) if str(item).strip()]
        payload: Dict[str, Any] = {
            "kw": keyword, "res": "all", "src": "all", "refresh": bool(refresh),
            "cloud_types": clouds, "ext": {"is_all": True},
        }
        if title_en:
            payload["ext"]["title_en"] = str(title_en)[:120]
        try:
            self.last_request_at = time.strftime("%Y-%m-%d %H:%M:%S")
            response = self._request("POST", self.base_url + "/api/search", json=payload)
            self.last_error_status = response.status_code if response.status_code >= 400 else None
            if response.status_code >= 400:
                self.last_error = self.safe_error(response.status_code, response.text)
                logger.warning("【TG115】PanSou 请求失败分类=%s", self.last_error)
                return []
            try:
                data = response.json()
            except Exception:
                self.last_error = "非 JSON 响应"
                logger.warning("【TG115】PanSou 响应非 JSON")
                return []
            if not self._is_success(data):
                self.last_error = "业务响应失败"
                logger.warning("【TG115】PanSou 业务响应失败")
                return []
            hits = [hit for hit in (self.normalize_item(item) for item in self.normalize_response(data)) if hit]
            self.last_result_count = len(hits)
            for hit in hits:
                self.type_counts[hit.pan_type] = self.type_counts.get(hit.pan_type, 0) + 1
            self.last_success_at = time.strftime("%Y-%m-%d %H:%M:%S")
            return hits[: self.max_results]
        except Exception as exc:
            self.last_error = self.safe_error(self.last_error_status, exc)
            logger.warning("【TG115】PanSou 请求异常分类=%s", self.last_error)
            return []

    def _request(self, method: str, url: str, **kwargs):
        """Retry only rate limiting and transient server failures."""
        last = None
        for attempt in range(3):
            last = self._client().request(method, url, headers=self._headers(), **kwargs)
            if last.status_code not in (429, 500, 502, 503, 504) or attempt >= 2:
                return last
            retry_after = str(last.headers.get("Retry-After") or "").strip()
            delay = self._retry_delay(retry_after, attempt)
            logger.warning(
                "【TG115】PanSou HTTP %s，退避 %.1f 秒后重试",
                last.status_code, delay,
            )
            time.sleep(delay)
        return last

    @staticmethod
    def _retry_delay(retry_after: str, attempt: int) -> float:
        """Accept both delta-seconds and RFC 7231 HTTP-date values."""
        value = str(retry_after or "").strip()
        if value:
            try:
                return max(0.0, min(30.0, float(value)))
            except (TypeError, ValueError):
                try:
                    target = parsedate_to_datetime(value)
                    if target.tzinfo is None:
                        target = target.replace(tzinfo=timezone.utc)
                    seconds = (target - datetime.now(timezone.utc)).total_seconds()
                    return max(0.0, min(30.0, seconds))
                except (TypeError, ValueError, OverflowError):
                    pass
        return float(2 ** max(0, int(attempt)))

    @staticmethod
    def _is_success(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        code = payload.get("code")
        status = str(payload.get("status") or "").lower()
        return code in (None, 0, "0", "success") and status not in {"error", "failed", "fail"}

    @staticmethod
    def normalize_response(payload: Any) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        candidates: List[Any] = []
        for key in ("results", "resources", "list", "items", "data"):
            if key in payload:
                value = payload[key]
                # ``data`` can contain ``merged_by_type`` or release-specific
                # nested result arrays. Scalar metadata such as ``total`` is
                # flattened too but discarded by the final dict filter.
                candidates.extend(_as_list(value))
        merged = payload.get("merged_by_type")
        candidates.extend(_as_list(merged))
        return [item for item in candidates if isinstance(item, dict)]

    @classmethod
    def classify_cloud_type(cls, url: str, declared_type: Any = "") -> str:
        value = str(url or "").strip()
        if value.lower().startswith("magnet:"):
            return "magnet"
        if value.lower().startswith("ed2k:"):
            return "magnet"
        detected = _classify_pan(value)
        if detected != "other":
            return detected
        return _TYPE_MAP.get(str(declared_type or "").strip().lower(), "other")

    @classmethod
    def normalize_item(cls, item: Dict[str, Any]) -> Optional[SiteHit]:
        if not isinstance(item, dict):
            return None
        url = str(item.get("url") or item.get("link") or item.get("share_url") or item.get("share_link") or item.get("magnet") or "").strip()
        if not url:
            text = " ".join(str(item.get(key) or "") for key in ("title", "name", "description", "content"))
            url = next(iter(_MAGNET_RE.findall(text) + _ED2K_RE.findall(text)), "")
        if not url:
            return None
        declared = item.get("cloud_type") or item.get("type") or item.get("resource_type") or item.get("pan_type")
        pan_type = cls.classify_cloud_type(url, declared)
        code = str(item.get("receive_code") or item.get("extraction_code") or item.get("password") or item.get("pwd") or "").strip()
        if not code:
            query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
            code = str(query.get("pwd") or query.get("password") or query.get("receive_code") or "").strip()
        title = str(item.get("resource_title") or item.get("title") or item.get("name") or item.get("movie_title") or "").strip()
        description = str(item.get("description") or item.get("content") or item.get("text") or title).strip()
        source_title = str(item.get("source_title") or item.get("movie_title") or item.get("title") or title).strip()
        return SiteHit(
            share_url=url, receive_code=code, resource_title=title or description[:300],
            text=description[:1000], pan_type=pan_type, pan_label=str(declared or ""),
            source_title=source_title, channel_name="PanSou", year=item.get("year"),
        )

    @staticmethod
    def safe_error(status_code: Optional[int], error: Any) -> str:
        if status_code == 401:
            return "HTTP 401 未授权"
        if status_code == 403:
            return "HTTP 403 被拒绝"
        if status_code == 429:
            return "HTTP 429 限流"
        if status_code is not None and status_code >= 500:
            return f"HTTP {status_code} 服务端错误"
        if isinstance(error, TimeoutError) or "timeout" in error.__class__.__name__.lower():
            return "请求超时"
        return "网络请求失败"
