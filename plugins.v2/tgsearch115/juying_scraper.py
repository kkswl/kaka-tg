"""Privacy-safe client for the documented Juying developer search API.

The plugin already owns an independent PanSou source, so this client asks the
aggregate endpoint for ``source=juying``. Credentials are sent only in HTTP
headers and are never included in log text.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

from app.log import logger

from .media_types import media_type_key
from .site_scraper import SiteHit, _classify_pan

DEFAULT_JUYING_DOMAIN = "https://www.jying.top"

_TYPE_MAP = {
    "115": "115",
    "quark": "quark",
    "baidu": "baidu",
    "aliyun": "aliyun",
    "aliyundrive": "aliyun",
    "alipan": "aliyun",
    "xunlei": "xunlei",
    "cloud189": "cloud189",
    "189": "cloud189",
    "uc": "uc",
    "magnet": "magnet",
    "bt": "magnet",
    "ed2k": "magnet",
}


def _developer_media_type(value: Any) -> str:
    """Translate MoviePilot enum and legacy values to the documented type."""
    key = media_type_key(value)
    if key == "MOVIE":
        return "movie"
    if key == "TV":
        return "tv"
    text = str(getattr(value, "value", value) or "").strip().casefold()
    return text if text in {"movie", "tv", "anime", "doc", "other"} else ""


def _safe_domain(value: str) -> str:
    """Return a normalized HTTP(S) origin, rejecting paths and other schemes."""
    raw = str(value or DEFAULT_JUYING_DOMAIN).strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _retry_after_seconds(headers: Any) -> int:
    try:
        value = int(float(str((headers or {}).get("Retry-After") or 0).strip()))
    except (TypeError, ValueError):
        return 0
    return max(0, min(value, 3600))


def _valid_year(value: Any) -> int | None:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if 1900 <= year <= 2100 else None


class JuyingApi:
    """Read-only client for ``/api/dev/search/aggregate/``."""

    def __init__(
        self,
        app_id: str = "",
        api_key: str = "",
        domain: str = "",
        proxy: str | None = None,
    ) -> None:
        self.app_id = str(app_id or "").strip()
        self.api_key = str(api_key or "").strip()
        self.domain = _safe_domain(domain)
        self.proxy = str(proxy or "").strip() or None
        self._http = None
        self.app_auth_valid = True
        self.last_error = ""
        self.last_error_status: int | None = None
        self.last_retry_after = 0
        self.last_source_status: dict[str, str] = {}
        self.last_summary: dict[str, int] = {}
        self.last_cache_hit = False
        self.last_result_count = 0

    def is_ready(self) -> bool:
        return bool(self.app_id and self.api_key and self.domain)

    def search(
        self,
        keyword: str,
        year: int | None = None,
        media_type: Any = "",
    ) -> list[SiteHit]:
        """Search Juying with fuzzy recall; downstream identity checks stay strict."""
        self._reset_diagnostics()
        if not self.is_ready():
            self.last_error = "聚影开发者凭证或域名未配置"
            logger.warning("【TG115】聚影开发者接口未完成配置，跳过")
            return []
        keyword = str(keyword or "").strip()
        if len(keyword) < 2:
            self.last_error = "搜索关键词长度不足"
            return []
        try:
            return self._do_search(keyword, year, media_type)
        except Exception as exc:  # noqa: BLE001 - httpx hierarchy varies by release
            self.last_error = "聚影网络请求异常"
            logger.warning("【TG115】聚影搜索异常 type=%s", type(exc).__name__)
            return []

    def check(self) -> tuple[bool, str]:
        """Run one minimal read-only authenticated search without exposing secrets."""
        self._reset_diagnostics()
        if not self.is_ready():
            return False, "未配置 AppID、API Key 或有效域名"
        try:
            response = self._request(
                {
                    "q": "测试",
                    "fuzzy": "false",
                    "source": "juying",
                    "local_limit": 1,
                    "pansou_limit": 1,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("【TG115】聚影连通检查异常 type=%s", type(exc).__name__)
            return False, "聚影接口连接失败"
        data = self._decode_response(response)
        if data is None:
            return False, self._public_error_message()
        if str(data.get("status") or "").casefold() != "success":
            self.last_error = "聚影返回业务错误"
            return False, "聚影鉴权或请求参数校验失败"
        self.app_auth_valid = True
        self._capture_diagnostics(data)
        return True, "连通正常，开发者鉴权有效"

    def close(self) -> None:
        if self._http is not None:
            try:
                self._http.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("【TG115】关闭聚影客户端失败 type=%s", type(exc).__name__)
            self._http = None

    def _reset_diagnostics(self) -> None:
        self.last_error = ""
        self.last_error_status = None
        self.last_retry_after = 0
        self.last_source_status = {}
        self.last_summary = {}
        self.last_cache_hit = False
        self.last_result_count = 0

    def _request(self, params: dict[str, Any]):
        url = f"{self.domain}/api/dev/search/aggregate/?{urlencode(params)}"
        return self._client().get(url, headers=self._headers())

    def _decode_response(self, response) -> dict[str, Any] | None:
        status = int(getattr(response, "status_code", 0) or 0)
        if status == 401:
            self.app_auth_valid = False
            self.last_error_status = 401
            self.last_error = "聚影开发者鉴权失败"
            logger.warning("【TG115】聚影开发者鉴权失败 HTTP 401")
            return None
        if status == 403:
            self.last_error_status = 403
            self.last_error = "聚影访问被拒绝或 IP 白名单不匹配"
            logger.warning("【TG115】聚影访问被拒绝 HTTP 403")
            return None
        if status == 429:
            self.last_error_status = 429
            self.last_retry_after = _retry_after_seconds(getattr(response, "headers", {}))
            suffix = f"，{self.last_retry_after} 秒后重试" if self.last_retry_after else ""
            self.last_error = f"聚影接口限流{suffix}"
            logger.warning(
                "【TG115】聚影接口限流 HTTP 429 retry_after=%s", self.last_retry_after
            )
            return None
        if status >= 500:
            self.last_error_status = status
            self.last_error = "聚影服务暂时不可用"
            logger.warning("【TG115】聚影服务异常 HTTP %s", status)
            return None
        if status != 200:
            self.last_error_status = status
            self.last_error = "聚影请求失败"
            logger.warning("【TG115】聚影请求失败 HTTP %s", status)
            return None
        try:
            data = response.json()
        except Exception:  # noqa: BLE001
            self.last_error = "聚影响应不是有效 JSON"
            logger.warning("【TG115】聚影响应解析失败 category=non_json")
            return None
        if not isinstance(data, dict):
            self.last_error = "聚影响应结构无效"
            return None
        return data

    def _public_error_message(self) -> str:
        if self.last_error_status == 401:
            return "AppID/API Key 无效或凭证已禁用（401）"
        if self.last_error_status == 403:
            return "访问被拒绝，请检查 IP 白名单（403）"
        if self.last_error_status == 429:
            return self.last_error or "接口限流（429）"
        if self.last_error_status and self.last_error_status >= 500:
            return "聚影服务暂时不可用"
        return self.last_error or "聚影接口返回异常"

    def _capture_diagnostics(self, data: dict[str, Any]) -> None:
        self.last_cache_hit = data.get("cache_hit") is True
        source_status = data.get("source_status")
        if isinstance(source_status, dict):
            self.last_source_status = {
                str(key): str(value)
                for key, value in source_status.items()
                if str(key) in {"juying", "pansou"}
                and str(value) in {"ok", "unavailable", "skipped"}
            }
            if self.last_source_status.get("juying") == "unavailable":
                self.last_error = "聚影站内来源暂时不可用"
        summary = data.get("summary")
        if isinstance(summary, dict):
            for key in ("movies", "resources", "juying_resources", "pansou_resources"):
                try:
                    self.last_summary[key] = max(0, int(summary.get(key) or 0))
                except (TypeError, ValueError):
                    continue

    def _do_search(self, keyword: str, year: int | None, media_type: Any) -> list[SiteHit]:
        params: dict[str, Any] = {
            "q": keyword,
            "fuzzy": "true",
            "source": "juying",
            "local_limit": 20,
            "pansou_limit": 1,
        }
        requested_year = _valid_year(year)
        if requested_year:
            params["year"] = requested_year
        developer_type = _developer_media_type(media_type)
        if developer_type:
            params["type"] = developer_type

        data = self._decode_response(self._request(params))
        if data is None:
            return []
        if str(data.get("status") or "").casefold() != "success":
            self.last_error = "聚影返回业务错误"
            logger.warning("【TG115】聚影搜索失败 category=business_error")
            return []
        self.app_auth_valid = True
        self._capture_diagnostics(data)

        container = data.get("data") if isinstance(data.get("data"), dict) else data
        resources = container.get("resources") if isinstance(container, dict) else []
        movies = container.get("movies") if isinstance(container, dict) else []
        if not isinstance(resources, list):
            self.last_error = "聚影资源列表结构无效"
            return []
        movie_map: dict[str, dict[str, Any]] = {}
        if isinstance(movies, list):
            movie_map = {
                str(item.get("id")): item
                for item in movies
                if isinstance(item, dict) and item.get("id") is not None
            }

        hits: list[SiteHit] = []
        seen = set()
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            provider = str(resource.get("provider") or "juying").strip().casefold()
            if provider not in {"", "juying"}:
                continue
            link = str(resource.get("share_link") or "").strip()
            if not link or link.casefold() == "javascript:;" or link.casefold() in seen:
                continue
            parsed_link = urlparse(link)
            if parsed_link.scheme not in {"http", "https", "magnet"}:
                continue
            seen.add(link.casefold())

            movie = movie_map.get(str(resource.get("movie_id")), {})
            movie_title = str(
                resource.get("movie_title") or movie.get("title") or keyword
            ).strip()
            description = str(resource.get("description") or "").strip()
            resource_type = str(resource.get("resource_type") or "").strip().casefold()
            pan_type = _TYPE_MAP.get(resource_type) or _classify_pan(link)
            receive_code = str(resource.get("extraction_code") or "").strip()
            if not receive_code:
                query = dict(parse_qsl(parsed_link.query, keep_blank_values=True))
                receive_code = str(
                    query.get("pwd")
                    or query.get("password")
                    or query.get("receive_code")
                    or ""
                ).strip()
            actual_year = _valid_year(
                resource.get("release_year") or movie.get("release_year")
            ) or requested_year
            pan_label = str(
                resource.get("resource_type_display") or resource_type
            ).strip()
            hits.append(
                SiteHit(
                    share_url=link,
                    receive_code=receive_code,
                    resource_title=description or movie_title,
                    text=description or movie_title,
                    pan_type=pan_type,
                    pan_label=pan_label,
                    source_title=movie_title,
                    channel_name="聚影",
                    pub_date=str(resource.get("added_at") or "").strip() or None,
                    year=actual_year,
                )
            )
        self.last_result_count = len(hits)
        logger.info(
            "【TG115】聚影开发者搜索完成 count=%s cache_hit=%s source_status=%s",
            len(hits),
            self.last_cache_hit,
            self.last_source_status.get("juying", "unknown"),
        )
        return hits

    def _headers(self) -> dict[str, str]:
        return {
            "X-App-Id": self.app_id,
            "X-App-Key": self.api_key,
            "Accept": "application/json",
        }

    def _client(self):
        if self._http is None:
            import httpx

            kwargs: dict[str, Any] = {
                "timeout": 20.0,
                "headers": {"User-Agent": "MoviePilot-TgSearch115/4.8"},
                "follow_redirects": True,
                "trust_env": False,
            }
            if self.proxy:
                kwargs["proxy"] = self.proxy
            self._http = httpx.Client(**kwargs)
        return self._http
