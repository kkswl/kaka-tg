# -*- coding: utf-8 -*-
"""MoviePilot 插件：拦截订阅 -> TG 频道搜索 115 -> 转存 -> 完成订阅（自定义 Vue 前端版 v2）。

================================================================================
 一、整体设计
================================================================================
1. 触发：监听 ``EventType.SubscribeAdded``，并按配置每 1/2/3 小时扫描一次
   MoviePilot ``state=N`` 活动订阅。新增订阅、周期订阅和手动搜索统一进入单一
   有界优先队列，避免创建无界线程；手动操作优先于等待中的周期任务。

2. TG 搜索：用网页爬虫（httpx + BeautifulSoup）抓取 ``t.me/s/{channel}`` 公开频道，
   通过服务端搜索 ``?q=关键字`` 检索频道全部历史消息，提取其中的 115 分享链接
   （见 ``tg_scraper.py``）。免登录、无需 TG 账号，支持多频道与 MP 代理。

3. 规则匹配：每条命中构造为 ``TorrentInfo``，复用 MoviePilot 内置的
   ``SubscribeChain().filter_torrents`` 与 ``TorrentHelper.filter_torrent``，
   按用户在 MP 中配置的过滤规则二次校验。

4. 115 转存：命中后用 ``httpx`` + 用户 Cookie 直连 115 Web API（``share_snap``
   取 file_id -> ``share_receive`` 转存）到指定 115 目录（见 ``p115_transfer.py``）。
   注意：MoviePilot 核心的 ``app.modules.filemanager.storages.u115.U115Pan``
   是基于 OAuth 的存储模块，仅提供 list/upload/download/move，**不包含**
   分享链接转存（share_receive）接口。早期版本用 ``p115client``，但它依赖很重
   （冷启动 pip 安装慢、拖慢插件加载），故改为 ``httpx`` 直连同一组 webapi.115.com
   接口，零额外重依赖。

5. 完成订阅：转存成功后镜像 ``SubscribeChain.__finish_subscribe``，写历史、
   删订阅、发 ``SubscribeComplete`` 事件、推送通知。

6. 回退：任何环节失败都静默 ``return``，不删除/不修改订阅。

================================================================================
 二、与 v1 的区别（自定义 Vue 前端架构）
================================================================================
- 配置 UI 由自定义 Vue 前端接管：插件随包附带 ``frontend/dist/remoteEntry.js``
  （Module Federation，暴露 ``Config`` / ``Page`` 组件），MoviePilot 前端加载
  ``Config`` 组件渲染配置弹窗、``Page`` 组件渲染插件详情页。
- 后端因此把 ``get_form`` / ``get_page`` 返回空桩；配置的读写完全由
  ``get_api`` 暴露的 RESTful 接口驱动：
    GET  /api/v1/plugin/{plugin_id}/config/get   读取配置
    POST /api/v1/plugin/{plugin_id}/config/save  保存配置并即时生效
    GET  /api/v1/plugin/{plugin_id}/check_channel?index=N   检查单频道连通性
    GET  /api/v1/plugin/{plugin_id}/check_all               检查全部频道连通性
- 配置持久化改用 ``self.get_data("config")`` / ``self.save_data("config", ...)``
  （PluginData 表，自动 JSON 序列化），不再使用 VForm 的 update_config。
"""
# ============================ 依赖说明 ============================
# 本插件只用 beautifulsoup4 + httpx，均为懒导入（用到时才 import）。
# **不做运行时 pip 安装**：之前加载期 pip install 会触发 MP 的「主程序依赖恢复 +
# pip check 健康检查」，而 MP 自身存在 langchain 版本冲突（langchain-experimental
# vs langchain-community），导致健康检查失败、插件装不上/加载失败。去掉 pip 安装后
# MP 不再被触发该检查，插件正常加载。依赖由 MP 环境提供（httpx 核心必带；bs4 缺失
# 时 TG 频道搜索不可用，观影搜索/115转存仍正常，缺依赖会在日志告警）。

import json
import random
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Body

from app.core.config import settings
from app.chain.subscribe import SubscribeChain, build_subscribe_meta
from app.chain.media import MediaChain
from app.chain.tmdb import TmdbChain
from app.core.context import MediaInfo, TorrentInfo
from app.core.event import Event, eventmanager
from app.db.subscribe_oper import SubscribeOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.torrent import TorrentHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, MediaType, NotificationType, SystemConfigKey

from .p115_transfer import P115Transfer
from .tg_scraper import TgChannelScraper, repair_mojibake
from .site_scraper import FilejinScraper, SiteHit
from .juying_scraper import JuyingApi
from .pansou_scraper import PanSouClient
from .identity_matcher import confirm_candidate_identity
from .media_types import is_tv_media, subscription_notification_title, to_moviepilot_media_type
from .search_relevance import extract_year, is_manual_relevant_result
from .candidate_identity import clean_identity_title, order_identity_candidates
from .resource_strategy import (
    execute_auto_candidates,
    filter_with_offline_seed_override,
    format_rejection_detail,
    has_chinese_subtitle_file,
    is_magnet_url,
    select_auto_candidates,
    summarize_rejections,
    classify_resource,
    format_resource_classification,
)
from .offline_rule_compat import RuleCompatibilityDiagnostics, filter_offline_share_rules
from .cms_tasks import CmsTaskLedger, btih_from_magnet, has_explicit_clear_confirmation
from .p115_offline import P115OfflineClient
from .runtime_control import (
    BoundedSourceRunner,
    SearchCoordinator,
    SourceCircuitBreaker,
    TtlCache,
    should_cache_source_result,
)
from .season_support import (
    can_stop_keyword_search,
    cache_covers_season,
    candidate_seasons,
    deduplicate_search_hits,
    parse_seasons,
    season_distribution,
    season_keywords,
    site_title_keyword,
    supports_target_season,
    supports_target_season_or_unknown_share,
    source_cache_key,
    target_seasons,
)
from .recognition_control import RecognitionGate, RecognitionUnavailable
from .search_reporting import SearchReport, candidate_source, candidate_upstream_source, format_selected_source
from .tmdb_support import season_year_map
from .site_query_policy import site_query_years
from .resource_metadata import normalize_resource_metadata
from .subscription_timeline import SubscriptionTimeline
from .source_health import SourceHealth


# get_data / save_data 存储本插件配置使用的 key
CONFIG_KEY = "config"
CMS_TASKS_KEY = "cms_tasks"
MAGNET_QUEUES_KEY = "magnet_queues"
TIMELINE_KEY = "subscription_timeline"
SOURCE_HEALTH_KEY = "source_health"


# ============================ 115 扫码登录（直连稳定 115 二维码接口） ============================
# 说明：p115client 的扫码方法散落在 p115qrcode 子包（非 pip 安装内容）与 client 类方法
# 之间，随版本变化较大、 import 路径不稳定。为「最稳妥、不易报错」，这里直连 115 官方
# 稳定的二维码接口（与 p115client.p115qrcode 走的是同一组 URL），仅用标准库 urllib，
# 无额外依赖，且不随 p115client 版本波动。流程：
#   1) POST /api/1.0/web/1.0/token/            -> {uid, time, sign}
#   2) GET  /api/1.0/web/1.0/qrcode?uid=<uid>  -> 二维码图片
#   3) GET  /get/status/?uid=&time=&sign=      -> {status, msg}  (0等待 1已扫描 2已确认 -1过期)
#   4) POST /app/1.0/<app>/1.0/login/qrcode/   -> 登录成功，返回含 UID/CID/SEID 的 Cookie
import re as _re
import urllib.parse as _urlparse
import urllib.request as _urlreq

_QR_BASE = "http://qrcodeapi.115.com"
# 不同 app 的 User-Agent（与 p115client.p115qrcode.qrcode_result 一致）
_QR_UA_MAP = {
    "ios": "UPhone/1.0.0",
    "qios": "OfficePhone/1.0.0",
    "ipad": "UPad/1.0.0",
    "qipad": "OfficePad/1.0.0",
}


def _qr_normalize_app(app: str) -> str:
    """归一化 app 名（与 p115qrcode 一致）：desktop->web，ios/qios/ipad/qipad->ios。"""
    a = (app or "web").strip().lower()
    if a == "desktop":
        return "web"
    if a in ("ios", "qios", "ipad", "qipad"):
        return "ios"
    return a


def _qr_request(method: str, path: str, params: dict = None, data: dict = None,
                headers: dict = None, timeout: int = 20):
    url = _QR_BASE + path
    body = None
    hdrs = {"User-Agent": "Mozilla/5.0 (MoviePilot-TgSearch115)"}
    if headers:
        hdrs.update(headers)
    if params:
        url = f"{url}?{_urlparse.urlencode(params)}"
    if data is not None:
        body = _urlparse.urlencode(data).encode("utf-8")
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    req = _urlreq.Request(url, data=body, headers=hdrs, method=method)
    with _urlreq.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
        # UID/CID/SEID 可能分别落在多个 Set-Cookie 头里，必须用 get_all 取全部，
        # 否则 headers.get 只返回第一个，会漏掉 CID/SEID 导致 Cookie 提取失败。
        set_cookies = resp.headers.get_all("Set-Cookie") or []
        set_cookie = "; ".join(set_cookies)
        return raw, set_cookie


def _qr_token() -> dict:
    """获取二维码 token：GET /api/1.0/web/1.0/token/ -> {state, data:{uid, time, sign, qrcode}}。"""
    raw, _ = _qr_request("GET", "/api/1.0/web/1.0/token/")
    return json.loads(raw)


def _qr_image_data_url(uid: str) -> str:
    """拉取二维码图片并转 data URL，避免前端 HTTPS 页面引用 HTTP 图片被混合内容拦截。"""
    import base64
    url = f"{_QR_BASE}/api/1.0/web/1.0/qrcode?uid={uid}"
    req = _urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _urlreq.urlopen(req, timeout=15) as resp:
        return "data:image/png;base64," + base64.b64encode(resp.read()).decode("ascii")


def _qr_status(uid: str, t: str, sign: str) -> dict:
    """轮询扫码状态（仅用于展示「已扫描/过期」）。115 该接口为长轮询，这里用 10s
    超时；登录成功的判定靠 ``_qr_result`` 直接取 Cookie，不依赖此接口的 status 字段。"""
    raw, _ = _qr_request("GET", "/get/status/",
                         params={"uid": uid, "time": t, "sign": sign}, timeout=10)
    return json.loads(raw)


def _pick_uid_cid_seid(text: str) -> str:
    """从任意文本（响应体 / Set-Cookie 头）提取 UID、CID、SEID，拼成标准 Cookie 串。"""
    text = text or ""
    found = {}
    for k in ("UID", "CID", "SEID", "KID"):
        m = _re.search(rf"\b{k}\s*=\s*([^;,\"\s]+)", text)
        if m:
            found[k] = m.group(1).strip()
    if {"UID", "CID", "SEID"} <= set(found):
        return "; ".join(f"{k}={found[k]}" for k in ("UID", "CID", "SEID", "KID") if k in found)
    return ""


def _qr_result(uid: str, app: str):
    """扫码确认后获取 Cookie：POST /app/1.0/{app}/1.0/login/qrcode/，返回 (raw_body, set_cookie)。"""
    a = _qr_normalize_app(app)
    ua = _QR_UA_MAP.get((app or "").strip().lower(), "Mozilla/5.0 (MoviePilot-TgSearch115)")
    return _qr_request(
        "POST", f"/app/1.0/{a}/1.0/login/qrcode/",
        data={"account": uid}, headers={"User-Agent": ua}, timeout=15,
    )


class TgSearch115(_PluginBase):
    """新增/周期订阅 -> 多来源搜索 -> 115 处理；失败平滑回退。"""

    # ============================ 插件元信息 ============================
    plugin_name = "拦截mp订阅"
    plugin_desc = (
        "新增订阅和周期任务聚合搜索 Telegram、观影、PanSou 和聚影，候选经 MoviePilot 规则与精确媒体身份确认后处理；"
        "支持 115 分享直接转存，磁力优先通过插件内置 115 离线；"
        "未命中或处理失败则平滑回退到 MoviePilot 默认站点搜索。"
    )
    plugin_version = "4.8.7"
    plugin_author = "MoviePilot User"
    plugin_icon = "T"
    plugin_config_prefix = "plugin.tgsearch115"
    author_url = ""
    plugin_url = "https://github.com/jxxghp/MoviePilot-Plugins"

    # ============================ 运行态 ============================
    _enabled = False
    _lock = threading.Lock()
    _running_ids: set = set()
    _claimed_ids: set = set()
    _forced_process_states: Dict[int, str] = {}
    _scraper: Optional[TgChannelScraper] = None
    _site_scraper: Optional[FilejinScraper] = None
    _juying_api: Optional[JuyingApi] = None
    _mp_proxy: str = ""
    _transfer: Optional[P115Transfer] = None
    _coordinator: Optional[SearchCoordinator] = None
    _search_cache: Optional[TtlCache] = None
    _source_breaker: Optional[SourceCircuitBreaker] = None
    _cms_tasks: Optional[CmsTaskLedger] = None
    _offline_client: Optional[P115OfflineClient] = None
    _recognition_gate: Optional[RecognitionGate] = None
    _notification_cache: Optional[TtlCache] = None
    _share_metadata_cache: Optional[TtlCache] = None
    _season_year_cache: Optional[TtlCache] = None
    _target_tmdb_cache: Optional[TtlCache] = None
    _timeline: Optional[SubscriptionTimeline] = None
    _source_health: Optional[SourceHealth] = None
    _source_runner: Optional[BoundedSourceRunner] = None

    # 配置项（运行态缓存）
    _tg_search_enabled = True
    _tg_channels: List[Dict[str, Any]] = []
    _p115_cookie = ""
    _p115_app = ""
    _p115_target = "/"
    _use_rule_groups = True
    _notify_success = True
    _notify_fail = False
    _search_detail_notify = False
    _auto_finish = True  # True=插件直接标记完成(不用MP整理); False=只阻断搜索让MP自己整理
    _site_enabled = False
    _site_app_auth = ""
    _site_magnet_priority = True
    _periodic_enabled = True
    _period_hours = 2
    _jitter_minutes = 10
    _source_item_delay_min = 5.0
    _source_item_delay_max = 10.0
    _source_request_timeout_seconds = 20.0
    _auto_search_budget_seconds = 60.0
    _cms_timeout_hours = 12
    _magnet_download_mode = "direct_115"
    _direct_timeout_hours = 12
    _offline_poll_seconds = 45
    _offline_last_poll = 0.0
    _offline_allow_cancel = False
    _magnet_failover_enabled = True
    _magnet_max_attempts = 5
    _magnet_download_wait_minutes = 1
    _magnet_queue_timeout_hours = 12
    _magnet_cancel_failover = True
    _magnet_rotation_unknown_timeout_minutes = 20
    _magnet_fallback_enabled = True
    _offline_stop: Optional[threading.Event] = None
    _offline_thread: Optional[threading.Thread] = None
    _reconcile_lock = threading.Lock()
    # ============================ 生命周期 ============================
    def init_plugin(self, config: dict = None):
        """生效配置。

        - 自定义前端 ``POST /config`` 会显式传入 config 并即时调用本方法；
        - MoviePilot 启动 / 重载插件时，框架调用 ``init_plugin(get_config())``。
          由于本插件用 ``get_data`` 持久化，``get_config()`` 为空，故 config 为
          None 时回退到 ``get_data(CONFIG_KEY)`` 读取已保存配置。
        """
        self._stop_coordinator()
        if config is None:
            config = self.get_data(CONFIG_KEY) or {}
        if not isinstance(config, dict):
            config = {}
        # Persist a complete migrated shape, not merely runtime fallbacks.  This
        # lets a host/API read the same timeout controls that are active after
        # upgrades, while preserving all existing user-provided values.
        migrated_config = self._default_config()
        migrated_config.update(config)
        config = migrated_config

        self._apply_config(config)
        stored_tasks = self.get_data(CMS_TASKS_KEY) or []
        self._cms_tasks = CmsTaskLedger(stored_tasks if isinstance(stored_tasks, list) else [])
        stored_queues = self.get_data(MAGNET_QUEUES_KEY) or {}
        self._magnet_queues = stored_queues if isinstance(stored_queues, dict) else {}
        self._share_metadata_cache = TtlCache(ttl_seconds=6 * 3600, max_entries=256)
        self._timeline = SubscriptionTimeline(self.get_data(TIMELINE_KEY) or [])
        self._source_health = SourceHealth(self.get_data(SOURCE_HEALTH_KEY) or {})

        # 持久化（保证 get_data 可读、字段干净）
        try:
            self.save_data(CONFIG_KEY, config)
        except Exception as e:
            logger.warn(f"【TG115】保存配置失败: {e}")
        if self._enabled:
            logger.info("【TG115】插件已启用")
            self._check_deps()
            self._start_coordinator()

    def _save_diagnostics(self) -> None:
        """Persist bounded sanitized diagnostic state; failure never stops search."""
        try:
            if self._timeline:
                self.save_data(TIMELINE_KEY, self._timeline.dump())
            if self._source_health:
                self.save_data(SOURCE_HEALTH_KEY, self._source_health.dump())
        except Exception as exc:
            logger.warning("【TG115】诊断状态保存失败 reason=%s", type(exc).__name__)

    def _apply_config(self, config: dict):
        """把配置字典解析到运行态字段，并重建搜索器 / 转存器。"""
        self._enabled = self._to_bool(config.get("enabled"), False)
        # 如果用户没配 TG 代理，自动用 MoviePilot 的代理（settings.PROXY）
        self._p115_cookie = config.get("p115_cookie") or ""
        self._p115_app = config.get("p115_app") or ""
        self._p115_target = config.get("p115_target") or "/"
        self._use_rule_groups = self._to_bool(config.get("use_rule_groups"), True)
        self._notify_success = self._to_bool(config.get("notify_success"), True)
        self._notify_fail = self._to_bool(config.get("notify_fail"), False)
        self._search_detail_notify = self._to_bool(config.get("search_detail_notify"), False)
        self._wait_for_mp_organize = self._to_bool(
            config.get("wait_for_mp_organize"), True
        )
        # ``auto_finish`` is retained only as an explicit legacy opt-out.  The
        # default workflow must wait for MP organization/history confirmation.
        self._auto_finish = (
            self._to_bool(config.get("auto_finish"), False)
            and not self._wait_for_mp_organize
        )
        self._periodic_enabled = self._to_bool(config.get("periodic_enabled"), True)
        self._period_hours = min(3, max(1, self._safe_int(config.get("period_hours"), 2)))
        self._jitter_minutes = min(10, max(0, self._safe_int(config.get("jitter_minutes"), 10)))
        self._source_item_delay_min = self._safe_float(config.get("source_item_delay_min"), 5.0)
        self._source_item_delay_max = max(
            self._source_item_delay_min,
            self._safe_float(config.get("source_item_delay_max"), 10.0),
        )
        self._source_request_timeout_seconds = min(
            60.0, max(5.0, self._safe_float(config.get("source_request_timeout_seconds"), 20.0))
        )
        self._auto_search_budget_seconds = min(
            180.0, max(15.0, self._safe_float(config.get("auto_search_budget_seconds"), 60.0))
        )
        cache_hours = min(6, max(1, self._safe_int(config.get("search_cache_hours"), 2)))
        failure_threshold = min(10, max(1, self._safe_int(config.get("source_failure_threshold"), 5)))
        cooldown_minutes = min(60, max(1, self._safe_int(config.get("source_cooldown_minutes"), 5)))
        self._cms_timeout_hours = min(72, max(1, self._safe_int(config.get("cms_timeout_hours"), 12)))
        self._magnet_download_mode = "direct_115"
        self._direct_timeout_hours = min(72, max(1, self._safe_int(config.get("direct_timeout_hours"), 12)))
        self._offline_poll_seconds = min(3600, max(15, self._safe_int(config.get("offline_poll_seconds"), 45)))
        self._offline_max_retries = min(6, max(0, self._safe_int(config.get("offline_max_retries"), 3)))
        self._offline_allow_cancel = self._to_bool(config.get("offline_allow_cancel"), False)
        self._tg_search_enabled = self._to_bool(config.get("tg_search_enabled"), True)
        self._magnet_failover_enabled = self._to_bool(config.get("magnet_failover_enabled"), True)
        self._magnet_max_attempts = min(10, max(1, self._safe_int(config.get("magnet_max_attempts"), 5)))
        self._magnet_download_wait_minutes = min(180, max(1, self._safe_int(config.get("magnet_download_wait_minutes"), 1)))
        self._magnet_attempt_timeout_minutes = self._magnet_download_wait_minutes
        self._magnet_no_progress_timeout_minutes = self._magnet_download_wait_minutes
        self._magnet_queue_timeout_hours = min(48, max(1, self._safe_int(config.get("magnet_queue_timeout_hours"), 12)))
        self._magnet_cancel_failover = self._to_bool(config.get("magnet_cancel_failover"), True)
        self._magnet_rotation_unknown_timeout_minutes = min(1440, max(1, self._safe_int(config.get("magnet_rotation_unknown_timeout_minutes"), 20)))
        self._magnet_fallback_enabled = self._to_bool(config.get("magnet_fallback_enabled"), True)
        self._search_cache = TtlCache(ttl_seconds=cache_hours * 3600)
        self._notification_cache = TtlCache(ttl_seconds=600, max_entries=256)
        self._season_year_cache = TtlCache(ttl_seconds=6 * 3600, max_entries=128)
        self._target_tmdb_cache = TtlCache(ttl_seconds=6 * 3600, max_entries=128)
        self._source_breaker = SourceCircuitBreaker(
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_minutes * 60,
        )
        self._source_runner = BoundedSourceRunner()
        self._recognition_gate = RecognitionGate()
        # TG 频道列表：自定义前端直接以数组/JSON 字符串形式提交 tg_channels
        self._tg_channels = self._parse_channels(config.get("tg_channels"))

        # 爬虫只接收「已启用」的频道；代理自动用 MP 的 settings.PROXY
        enabled_channels = [ch for ch in self._tg_channels if ch.get("enabled", True)] if self._tg_search_enabled else []
        _proxy = ""
        try:
            _mp_proxy = settings.PROXY
            if _mp_proxy:
                _proxy = _mp_proxy.get("https") or _mp_proxy.get("http") or ""
        except Exception:
            pass
        old_pansou = getattr(self, "_pansou_client", None)
        if old_pansou:
            old_pansou.close()
        self._pansou_enabled = self._to_bool(config.get("pansou_enabled"), True)
        self._pansou_url = str(config.get("pansou_url") or "http://192.168.1.15:8888").strip().rstrip("/")
        self._pansou_token = str(config.get("pansou_token") or "").strip()
        self._pansou_timeout = min(180.0, max(3.0, self._safe_float(config.get("pansou_timeout"), 20.0)))
        self._pansou_refresh = self._to_bool(config.get("pansou_refresh"), False)
        self._pansou_max_results = min(100, max(1, self._safe_int(config.get("pansou_max_results"), 100)))
        self._pansou_cloud_types = self._parse_string_list(config.get("pansou_cloud_types"), ["115", "magnet"])
        # PanSou is normally a LAN service.  Do not inherit MP's outbound proxy
        # implicitly; an explicit value is required when a proxy is desired.
        pansou_proxy = str(config.get("pansou_proxy") or "").strip()
        if pansou_proxy.lower() in {"direct", "none", "false"}:
            pansou_proxy = ""
        elif pansou_proxy.lower() in {"mp", "global"}:
            pansou_proxy = _proxy
        self._pansou_client = PanSouClient(
            base_url=self._pansou_url, token=self._pansou_token,
            timeout=self._pansou_timeout, proxy=pansou_proxy,
            max_results=self._pansou_max_results,
        ) if self._pansou_enabled and self._pansou_url else None
        self._pansou_cache_hits = 0
        self._pansou_dedup_count = 0
        self._pansou_rule_passed = 0
        self._pansou_identity_checked = 0
        self._pansou_safe_candidates = 0
        tg_concurrency = min(3, max(1, self._safe_int(config.get("tg_concurrency"), 2)))
        tg_delay_min = self._safe_float(config.get("tg_page_delay_min"), 0.8)
        tg_delay_max = max(tg_delay_min, self._safe_float(config.get("tg_page_delay_max"), 1.5))
        self._scraper = TgChannelScraper(
            channels=enabled_channels,
            proxy=_proxy,
            concurrency=tg_concurrency,
            page_delay=(tg_delay_min, tg_delay_max),
        )
        self._mp_proxy = _proxy  # 供 /check_site 临时测试用
        # 观影爬虫（PoW + 搜索 + 全网盘提取；115 分享和确认后的磁力可自动处理）
        self._site_enabled = self._to_bool(config.get("site_enabled"), False)
        self._site_app_auth = config.get("site_app_auth") or ""
        self._site_magnet_priority = self._to_bool(
            config.get("site_magnet_priority"), True
        )
        # 观影专用代理：优先用配置的，否则默认不走代理（与 TG 区分开）。
        # 因为观影站对国外代理节点/机房IP往往会封锁 downurl 导致 403，直连反而更稳。
        # 如果填了 'proxy' 则强制用全局代理，留空或填 direct 都是直连。
        sp = (config.get("site_proxy") or "").strip()
        self._site_proxy = _proxy if sp == 'proxy' else (None if not sp or sp == 'direct' else sp)
        self._site_domain = (config.get("site_domain") or "").strip()  # 观影域名（换域名时改这里）
        if self._site_enabled and self._site_app_auth:
            site_delay_min = self._safe_float(config.get("site_detail_delay_min"), 1.5)
            site_delay_max = max(
                site_delay_min, self._safe_float(config.get("site_detail_delay_max"), 3.0)
            )
            self._site_scraper = FilejinScraper(
                app_auth=self._site_app_auth,
                proxy=self._site_proxy,
                site_base=self._site_domain,
                detail_delay=(site_delay_min, site_delay_max),
            )
        else:
            self._site_scraper = None
        # 聚影开发者 API（官方接口，稳定无 IP 封锁；需 AppID+API Key+域名）
        self._juying_enabled = self._to_bool(config.get("juying_enabled"), False)
        self._juying_app_id = config.get("juying_app_id") or ""
        self._juying_api_key = config.get("juying_api_key") or ""
        self._juying_domain = (config.get("juying_domain") or "").strip()
        # 聚影也加专用代理机制，逻辑同观影
        jp = (config.get("juying_proxy") or "").strip()
        self._juying_proxy = None if jp == 'direct' else (jp or None)
        if self._juying_enabled and self._juying_app_id and self._juying_api_key and self._juying_domain:
            self._juying_api = JuyingApi(
                app_id=self._juying_app_id, api_key=self._juying_api_key,
                domain=self._juying_domain, proxy=self._juying_proxy,
            )
        else:
            self._juying_api = None
        self._transfer = P115Transfer(
            cookie=self._p115_cookie, default_target_path=self._p115_target
        )
        self._offline_client = P115OfflineClient(
            cookie=self._p115_cookie, target_cid=self._p115_target,
            max_retries=self._offline_max_retries,
        ) if self._p115_cookie else None

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """注册插件 RESTful API，供自定义 Vue 前端调用。

        MoviePilot 会把每个端点挂载到 ``/api/v1/plugin/{plugin_id}{path}``，
        并按需校验 apikey。端点为「绑定方法」，形参会从 query / body 中按名注入。
        """
        # 路径与官方插件仓 agentresourceofficer 保持一致：get/save 拆成独立路径，
        # 避免 MoviePilot 插件路由对「同路径不同方法」的兼容性差异。
        # 鉴权：MP 自定义前端 props.api 默认携带 Authorization: Bearer <用户令牌>，
        # 故端点统一用 "bear"(verify_token) 鉴权；若用默认 apikey 鉴权，前端调用会 401。
        apis = [
            {
                "path": "/config/get",
                "endpoint": self.__get_config_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取插件配置",
                "description": "返回当前插件配置，供自定义前端 Config.vue 初始化读取",
            },
            {
                "path": "/config/save",
                "endpoint": self.__save_config_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "保存插件配置",
                "description": "保存配置并即时生效（写入 get_data 并重新 init_plugin）",
            },
            {
                "path": "/check_channel",
                "endpoint": self.__check_channel_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "检查指定 TG 频道连通性",
            },
            {
                "path": "/check_all",
                "endpoint": self.__check_all_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "检查所有 TG 频道连通性",
            },
            {
                "path": "/qrcode/get",
                "endpoint": self.__qrcode_get_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取 115 登录二维码",
                "description": "GET /qrcode/get?app=web|tv|ipad|android|ios，返回二维码图片(data URL)及会话凭证",
            },
            {
                "path": "/qrcode/status",
                "endpoint": self.__qrcode_status_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "轮询 115 扫码状态",
                "description": "GET /qrcode/status?uid=&time=&sign=&app=，扫码成功时自动提取并保存 Cookie",
            },
            {
                "path": "/transfer",
                "endpoint": self.__transfer_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "手动转存 115 分享链接",
                "description": "GET /transfer?share_url=&target=，target 留空用默认目录",
            },
            {
                "path": "/manual/subscriptions",
                "endpoint": self.__manual_subscriptions_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "列出手动验证可用的订阅",
            },
            {
                "path": "/manual/process",
                "endpoint": self.__manual_process_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "按订阅规则验证并处理一个手动候选",
            },
            {
                "path": "/magnet/offline",
                "endpoint": self.__magnet_offline_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "添加 115 磁力离线任务",
                "description": "POST /magnet/offline，body: {magnet, title}；仅使用插件内置 115",
            },
            {
                "path": "/check_115_offline",
                "endpoint": self.__check_115_offline_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "只读检查 115 云下载接口",
                "description": "只读取签名和任务列表能力，不创建或修改任务",
            },
            {
                "path": "/runtime/status",
                "endpoint": self.__runtime_status_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取周期搜索、来源冷却和 115 磁力任务状态",
            },
            {"path": "/runtime/timeline", "endpoint": self.__timeline_api, "methods": ["GET"], "auth": "bear", "summary": "获取订阅处理诊断"},
            {"path": "/runtime/source-health", "endpoint": self.__source_health_api, "methods": ["GET"], "auth": "bear", "summary": "获取来源健康评分"},
            {"path": "/runtime/timeline/clear", "endpoint": self.__clear_timeline_api, "methods": ["POST"], "auth": "bear", "summary": "清除终态订阅诊断"},
            {
                "path": "/tasks/retry",
                "endpoint": self.__retry_cms_task_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "重试失败或超时的 115 磁力任务",
            },
            {
                "path": "/tasks/cancel",
                "endpoint": self.__cancel_offline_task_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "取消 115 直接离线任务",
            },
            {
                "path": "/tasks/clear",
                "endpoint": self.__clear_offline_tasks_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清除已结束的磁力任务账本记录",
            },
            {
                "path": "/subscription/dry-run",
                "endpoint": self.__subscription_dry_run_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "只读验证订阅候选",
                "description": "仅搜索、读取分享文件名、运行规则和身份确认；不转存、不提交任务、不修改订阅。",
            },
            {
                "path": "/subscription/process",
                "endpoint": self.__subscription_process_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "确认后正式处理单个订阅",
                "description": "必须传 confirm=true；复用手动高优先级队列和严格身份确认，只有安全候选才会转存或提交下载。",
            },
            {
                "path": "/search",
                "endpoint": self.__search_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "手动搜索 TG 频道 115 资源",
                "description": "GET /search?keyword=",
            },
            {
                "path": "/dir_info",
                "endpoint": self.__dir_info_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "根据 cid 查询 115 目录名称",
                "description": "GET /dir_info?cid=",
            },
            {
                "path": "/dirs",
                "endpoint": self.__dirs_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "列出 115 子目录（目录浏览）",
                "description": "GET /dirs?cid=0",
            },
            {
                "path": "/verify_cookie",
                "endpoint": self.__verify_cookie_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "验证 115 Cookie 是否有效",
                "description": "调 fs_files(0) 实测 Cookie 有效性",
            },
            {
                "path": "/check_site",
                "endpoint": self.__check_site_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "检查观影连通性与登录态",
                "description": "解 PoW + 试搜，验证 app_auth 是否有效",
            },
            {
                "path": "/check_juying",
                "endpoint": self.__check_juying_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "检查聚影 API 鉴权",
                "description": "用 AppID+API Key 试搜，验证聚影开发者接口是否可用",
            },
            {
                "path": "/check_pansou",
                "endpoint": self.__check_pansou_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "只读检查 PanSou 服务",
                "description": "只检查服务可访问性，不创建任务或修改资源",
            },
        ]
        return apis

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """配置页由自定义 Vue 前端（Config.vue）接管，这里返回空桩。

        若尚未构建前端产物（frontend/dist/remoteEntry.js），可临时改为返回
        Vuetify/VForm schema 作为兜底；当前面向自定义前端架构，故返回空。
        """
        return [], {}

    def get_page(self) -> List[dict]:
        """返回宿主详情页能力标记，实际内容由 Vue Page 组件渲染。

        MoviePilot v2.14 的详情页会把空列表当作“没有详情页面”，即使插件已
        声明 Vue Federation 的 ``./Page``。返回这个无状态占位项只用于保持
        ``has_page`` 与页面接口为真；不携带凭据、任务或订阅数据。
        """
        return [{
            "component": "VSpacer",
            "props": {"class": "d-none"},
        }]

    @staticmethod
    def get_render_mode() -> Tuple[str, Optional[str]]:
        """声明使用自定义 Vue 前端渲染配置页/详情页。

        MoviePilot 通过 ``plugin.get_render_mode()`` 判断插件是否使用 Vue 自定义前端：
        返回 ``("vue", dist_path)`` 时，MP 会把本插件登记进 ``plugin/remotes``，
        前端再经 Module Federation 加载 ``{dist_path}/remoteEntry.js`` 暴露的
        Config / Page 组件；否则回退到 ``get_form()``（本插件返回空，故表现为空白）。

        ``dist_path`` 为 remoteEntry.js 所在目录（相对插件目录）。本插件构建产物在
        ``frontend/dist/assets/remoteEntry.js``，故返回 ``frontend/dist/assets``。
        """
        return "vue", "frontend/dist/assets"

    def stop_service(self):
        """停止插件并等待内部调度线程退出。"""
        self._stop_coordinator()
        pansou_client = getattr(self, "_pansou_client", None)
        if pansou_client:
            pansou_client.close()
        with self._lock:
            self._running_ids.clear()

    def _start_coordinator(self):
        """Start the single bounded queue used by event, periodic and manual searches."""
        self._stop_coordinator()
        # ``init_plugin`` creates the recognition gate before starting runtime
        # services.  The defensive stop above disposes the previous runtime,
        # including that gate, so always create a fresh accepting gate here.
        # Without this, every candidate immediately falls into the unavailable
        # path after a plugin install/reload.
        self._recognition_gate = RecognitionGate()
        self._coordinator = SearchCoordinator(
            process_subscription=self._handle_subscribe,
            list_subscriptions=self._periodic_subscriptions,
            interval_hours=self._period_hours,
            jitter_minutes=self._jitter_minutes,
            between_items=(self._source_item_delay_min, self._source_item_delay_max),
            queue_size=100,
            periodic_enabled=self._periodic_enabled,
            on_subscription_queued=self._record_queued_subscription,
        )
        self._coordinator.start()
        self._start_offline_poller()
        logger.info(
            f"【TG115】搜索队列已启动，周期搜索"
            f"{'已开启' if self._periodic_enabled else '已关闭'}，"
            f"周期 {self._period_hours} 小时，随机抖动 0-{self._jitter_minutes} 分钟"
        )

    def _stop_coordinator(self):
        self._stop_offline_poller()
        coordinator = self._coordinator
        self._coordinator = None
        if coordinator:
            coordinator.stop()
        recognition_gate = self._recognition_gate
        self._recognition_gate = None
        if recognition_gate and not recognition_gate.stop(timeout=5):
            logger.warning("【TG115】媒体识别仍在退出，已停止接收新的识别任务")
        with self._lock:
            claimed_ids = list(self._claimed_ids)
        for subscribe_id in claimed_ids:
            self._restore_claim(subscribe_id)

    def _start_offline_poller(self):
        """Start one stoppable status thread; the first poll waits one interval."""
        self._stop_offline_poller()
        if not self._offline_client:
            return
        self._offline_stop = threading.Event()
        self._offline_thread = threading.Thread(
            target=self._offline_poll_loop, name="tg115-offline-status", daemon=True,
        )
        self._offline_thread.start()

    def _offline_poll_loop(self):
        stop = self._offline_stop
        while stop and not stop.wait(self._offline_poll_seconds):
            if not self._enabled:
                continue
            try:
                self._reconcile_cms_tasks(force_direct_poll=True)
            except Exception as exc:
                logger.warning("【TG115】115 状态轮询异常 reason=%s", type(exc).__name__)

    def _stop_offline_poller(self):
        stop, thread = self._offline_stop, self._offline_thread
        self._offline_stop, self._offline_thread = None, None
        if stop:
            stop.set()
        if thread and thread is not threading.current_thread():
            thread.join(timeout=5)

    def _periodic_subscriptions(self):
        """Reconcile CMS records, then return all subscriptions for active filtering."""
        self._reconcile_cms_tasks()
        return SubscribeOper().list() or []

    def _claim_subscription(self, subscribe_id: int) -> bool:
        """Temporarily pause one subscription while all plugin sources are evaluated."""
        with self._lock:
            if subscribe_id in self._claimed_ids:
                return True
            forced_state = self._forced_process_states.get(subscribe_id)
        subscribe = SubscribeOper().get(subscribe_id)
        if not subscribe:
            return False
        state = str(getattr(subscribe, "state", "N") or "N").upper()
        if state != "N" and forced_state != state:
            return False
        try:
            SubscribeOper().update(subscribe_id, {"state": "P"})
        except Exception as exc:
            logger.warning(
                f"【TG115】订阅 {subscribe_id} 临时认领失败 reason={type(exc).__name__}"
            )
            return False
        with self._lock:
            self._claimed_ids.add(subscribe_id)
        return True

    def _restore_claim(self, subscribe_id: int) -> None:
        with self._lock:
            claimed = subscribe_id in self._claimed_ids
            original_state = self._forced_process_states.get(subscribe_id)
        if not claimed:
            with self._lock:
                self._forced_process_states.pop(subscribe_id, None)
            return
        restored = False
        try:
            subscribe = SubscribeOper().get(subscribe_id)
            if subscribe and str(getattr(subscribe, "state", "") or "").upper() == "P":
                restore_state = original_state or "N"
                SubscribeOper().update(subscribe_id, {"state": restore_state})
                logger.info(f"【TG115】订阅 {subscribe_id} 未命中，已恢复 state={restore_state}")
            restored = True
        except Exception as exc:
            logger.warning(
                f"【TG115】订阅 {subscribe_id} 恢复失败 reason={type(exc).__name__}"
            )
        if restored:
            with self._lock:
                self._claimed_ids.discard(subscribe_id)
                self._forced_process_states.pop(subscribe_id, None)

    def _complete_claim(self, subscribe_id: int) -> None:
        with self._lock:
            self._claimed_ids.discard(subscribe_id)
            self._forced_process_states.pop(subscribe_id, None)

    # ============================ 事件入口 ============================
    def _record_queued_subscription(self, subscribe_id: int, trigger: str) -> None:
        """Expose queued work immediately; worker startup may be delayed by a source timeout."""
        if not self._timeline:
            return
        try:
            subscribe = SubscribeOper().get(int(subscribe_id))
            if subscribe:
                self._timeline.start(subscribe, trigger)
                self._save_diagnostics()
        except Exception as exc:
            logger.warning("【TG115】写入排队诊断失败 type=%s", type(exc).__name__)

    @eventmanager.register(EventType.SubscribeAdded)
    def on_subscribe_added(self, event: Event):
        """订阅新增事件：异步触发 TG+115 优先处理。

        EventBus 在独立消费线程派发事件，本方法只做最轻量校验后另起守护线程，
        避免占用事件消费线程、影响其它插件事件的处理。
        """
        if not self._enabled:
            return
        data = getattr(event, "event_data", None) or {}
        subscribe_id = data.get("subscribe_id")
        if not subscribe_id:
            return
        if not self._claim_subscription(int(subscribe_id)):
            logger.warning(f"【TG115】订阅 {subscribe_id} 未能进入插件优先处理状态")
            return
        if self._coordinator and self._coordinator.enqueue_subscription(
                int(subscribe_id), priority=0, trigger="event"):
            return
        self._restore_claim(int(subscribe_id))
        logger.warn(f"【TG115】订阅 {subscribe_id} 未能进入搜索队列，将由周期任务重试")

    @eventmanager.register(EventType.TransferComplete)
    def on_transfer_complete(self, event: Event):
        if not self._enabled or not self._cms_tasks:
            return
        data = getattr(event, "event_data", None) or {}
        mediainfo = data.get("mediainfo") or {}
        meta = data.get("meta") or {}

        def value(source, name):
            return source.get(name) if isinstance(source, dict) else getattr(source, name, None)

        tmdb_id = value(mediainfo, "tmdb_id")
        douban_id = value(mediainfo, "douban_id")
        media_type = value(mediainfo, "type") or value(meta, "type")
        season = value(mediainfo, "season")
        if season is None:
            season = value(meta, "begin_season")
        if not tmdb_id and not douban_id:
            logger.warning(
                "【MP整理】状态=事件无法匹配 动作=等待历史补偿 缺少字段=tmdb_id,douban_id"
            )
            return
        record = self._cms_tasks.match_transfer_complete(
            tmdb_id=tmdb_id,
            douban_id=douban_id,
            media_type=media_type,
            season=season,
        )
        if not record:
            logger.info(
                "【MP整理】媒体=%s 年份=%s 季=%s 状态=未唯一匹配 动作=等待历史补偿",
                value(mediainfo, "title") or value(meta, "name") or "未知",
                value(mediainfo, "year") or value(meta, "year") or "未知",
                season if season is not None else "无",
            )
            return
        if not self._reconcile_lock.acquire(blocking=False):
            return
        try:
            self._complete_task_record(record, "MoviePilot 整理事件")
        finally:
            self._reconcile_lock.release()

    # ============================ 核心流程 ============================
    def _new_source_report(self) -> SearchReport:
        return SearchReport({
            "tg": bool(self._tg_search_enabled and self._scraper and any(
                channel.get("enabled", True) for channel in self._tg_channels
            )),
            "site": bool(self._site_scraper),
            "pansou": bool(self._pansou_client),
            "juying": bool(self._juying_api),
        })

    def _evaluate_subscription_candidates(self, subscribe) -> Dict[str, Any]:
        """Evaluate a subscription without transfer, ledger, notification or state writes.

        This is deliberately the one candidate path used by both formal handling and
        ``/subscription/dry-run``.  The caller alone decides whether an already
        confirmed candidate may be acted on.
        """
        report = self._new_source_report()
        result: Dict[str, Any] = {
            "source_report": report, "meta": None, "mediainfo": None,
            "hits": [], "torrents": [], "matched": [], "candidates": [],
            "identities": {}, "confirmed": [], "reason": "", "diagnostics": None,
            "season_before": 0, "season_after": 0,
            "site_query_years": [], "site_query_hits": {}, "source_stats": {},
        }
        try:
            meta = build_subscribe_meta(subscribe)
        except Exception:
            result["reason"] = "订阅元信息构造失败"
            return result
        mediainfo = self._recognize(subscribe, meta)
        if not mediainfo:
            result["reason"] = "MoviePilot 媒体识别不可用"
            return result
        result["meta"], result["mediainfo"] = meta, mediainfo

        seasons = target_seasons(subscribe)
        target_season = seasons[0] if len(seasons) == 1 else getattr(subscribe, "season", None)
        site_years = site_query_years(subscribe, mediainfo, target_season)
        result["site_query_years"] = site_years
        hits: List[Any] = []
        source_raw = Counter()
        source_relevance_rejected = Counter()
        keywords = self._build_keywords(subscribe, mediainfo, target_season)
        search_deadline = time.monotonic() + self._auto_search_budget_seconds
        result["search_budget_seconds"] = self._auto_search_budget_seconds
        result["search_timed_out"] = False
        pending_base_keywords = {
            keyword.casefold() for keyword in keywords
            if target_season is not None and site_title_keyword(keyword) == keyword
        }
        for keyword in keywords:
            if time.monotonic() >= search_deadline:
                result["search_timed_out"] = True
                result["reason"] = "来源搜索超过本轮总时限，已释放队列等待下次重试"
                logger.warning("【TG115】订阅 [%s] 来源搜索达到总时限，停止本轮", subscribe.name)
                break
            logger.info(
                "【TG115】订阅 [%s] %s开始搜索，关键字: %s",
                subscribe.name,
                f"S{target_season:02d} " if target_season is not None else "",
                keyword,
            )
            keyword_hits = self._search_auto_sources(
                keyword=keyword, year=getattr(subscribe, "year", None),
                media_type=getattr(subscribe, "type", ""), target_season=target_season,
                source_report=report, site_years=site_years,
                search_diagnostics=result["site_query_hits"],
                deadline=search_deadline,
            )
            result["season_before"] += len(keyword_hits)
            for hit in keyword_hits:
                source_raw[candidate_source(hit)] += 1
            if target_season is not None:
                season_kept = []
                for hit in keyword_hits:
                    if supports_target_season_or_unknown_share(
                        hit,
                        target_season,
                        P115Transfer._is_115_share_url(
                            str(getattr(hit, "share_url", "") or "")
                        ),
                    ):
                        season_kept.append(hit)
                    else:
                        source_relevance_rejected[candidate_source(hit)] += 1
                        hit_seasons = candidate_seasons(hit)
                        season_label = ",".join(
                            f"S{s:02d}" for s in sorted(hit_seasons)
                        ) or "无明确季号"
                        logger.info(
                            f"【TG115】订阅 [{subscribe.name}] S{target_season:02d} "
                            f"本地季号初筛拒绝: title=%s 候选季号=%s",
                            str(getattr(hit, "resource_title", "")
                                or getattr(hit, "title", "") or "")[:80],
                            season_label,
                        )
                keyword_hits = season_kept
            result["season_after"] += len(keyword_hits)
            hits.extend(keyword_hits)
            pending_base_keywords.discard(keyword.casefold())
            # A season-qualified site lookup may already return five results,
            # but TG multi-season shares are often published under the base
            # title only. Do not stop until both bounded base fallbacks ran.
            if can_stop_keyword_search(len(keyword_hits), pending_base_keywords):
                break
        before_dedup = Counter(candidate_source(hit) for hit in hits)
        hits = deduplicate_search_hits(hits)
        after_dedup = Counter(candidate_source(hit) for hit in hits)
        source_dedupe_rejected = before_dedup - after_dedup
        self._pansou_dedup_count = source_dedupe_rejected.get("pansou", 0)
        result["source_stats"] = {
            source: {
                "raw_count": source_raw.get(source, 0),
                "relevance_rejected": source_relevance_rejected.get(source, 0),
                "dedupe_rejected": source_dedupe_rejected.get(source, 0),
                "returned_count": after_dedup.get(source, 0),
            }
            for source in ("tg", "site", "pansou", "juying")
        }
        logger.info("【TG115】搜索渠道统计: %s", result["source_stats"])
        result["hits"] = hits
        if not hits:
            result["reason"] = result.get("reason") or "未找到符合目标季与标题的候选"
            return result

        torrents = self._build_torrents(hits)
        self._enrich_share_metadata(torrents, subscribe=subscribe, mediainfo=mediainfo)
        if target_season is not None:
            before_metadata_season_filter = len(torrents)
            torrents = [
                torrent for torrent in torrents
                if supports_target_season(torrent, target_season)
            ]
            logger.info(
                "【TG115】订阅 [%s] S%02d 分享元数据季号复核: %d 条 -> %d 条",
                subscribe.name,
                target_season,
                before_metadata_season_filter,
                len(torrents),
            )
        result["torrents"] = torrents
        matched, rule_diagnostics = self._filter_resources(subscribe, mediainfo, torrents)
        self._pansou_rule_passed = sum(
            str(getattr(item, "_tg115_source", "") or "").lower() == "pansou"
            for item in matched
        )
        result["matched"], result["diagnostics"] = matched, rule_diagnostics
        if not matched:
            result["reason"] = rule_diagnostics.summary() if rule_diagnostics else "候选未通过 MoviePilot 规则"
            return result

        bounded_matched = order_identity_candidates(matched, mediainfo, subscribe)[:20]
        auto_rejections: list = []
        auto_candidates = select_auto_candidates(
            torrents=bounded_matched,
            prefer_site_magnet=(self._site_magnet_priority and bool(
                self._offline_client and self._p115_cookie
            )),
            is_tv=is_tv_media(getattr(subscribe, "type", None)),
            is_115_url=P115Transfer._is_115_share_url,
            rejection_collector=auto_rejections,
        )
        # ``select_auto_candidates`` already applies the contractual source
        # order and de-duplicates within/cross buckets. Rebuilding the result as
        # ``magnets + shares`` silently reversed Guanying 115 and magnet priority.
        candidates = list(auto_candidates)
        result["candidates"] = candidates
        result["rejections"] = auto_rejections
        if not candidates:
            result["reason"] = summarize_rejections(auto_rejections)
            return result

        identity_candidates = order_identity_candidates(candidates, mediainfo, subscribe)
        # A technical title parsing failure must not consume the entire
        # identity budget when other candidates have already passed the same
        # strict MoviePilot rule/subtitle/quality filters. Five is still a
        # bounded read-only recognition budget and keeps source pressure low.
        identity_limit = min(len(identity_candidates), 5)
        logger.info(
            "【TG115】候选身份确认排序完成: 总数=%d，进入有界确认=%d",
            len(candidates), identity_limit,
        )
        for candidate in identity_candidates[:identity_limit]:
            identity = confirm_candidate_identity(
                subscribe=subscribe, target_media=mediainfo, torrent=candidate,
                recognize_candidate=self._recognize_candidate,
            )
            result["identities"][id(candidate)] = identity
            if identity.confirmed:
                result["confirmed"].append(candidate)
        self._pansou_identity_checked = sum(
            str(getattr(item, "_tg115_source", "") or "").lower() == "pansou"
            for item in identity_candidates[:identity_limit]
        )
        # Identity probing is relevance-ranked, but all side effects must retain
        # the contractual TG -> Guanying share -> magnet -> Juying order.
        confirmed_ids = {id(item) for item in result["confirmed"]}
        result["confirmed"] = [item for item in candidates if id(item) in confirmed_ids]
        self._pansou_safe_candidates = sum(
            str(getattr(item, "_tg115_source", "") or "").lower() == "pansou"
            for item in result["confirmed"]
        )
        if not result["confirmed"]:
            identities = list(result["identities"].values())
            result["reason"] = next((item.reason for item in reversed(identities) if item.reason),
                                    "候选未通过 MoviePilot/TMDB 身份确认")
            if any(item.year_policy in {"tv_season_year_match", "tv_year_deferred_to_tmdb"}
                   for item in identities):
                result["reason"] += "；电视剧候选年份已按季级 TMDB 确认处理"
        return result

    @staticmethod
    def _dry_run_summary(subscribe, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """Return bounded diagnostics only; never return URLs, credentials or magnets."""
        mediainfo = evaluation.get("mediainfo")
        identities = list((evaluation.get("identities") or {}).values())
        target_season = getattr(subscribe, "season", None)
        try:
            target_season = int(target_season) if target_season is not None else None
        except (TypeError, ValueError):
            target_season = None
        season_years = getattr(mediainfo, "season_years", None) or {}
        target_season_year = season_years.get(target_season, season_years.get(str(target_season))) \
            if isinstance(season_years, dict) and target_season is not None else None
        candidates = []
        for candidate in evaluation.get("candidates", [])[:10]:
            identity = (evaluation.get("identities") or {}).get(id(candidate))
            candidates.append({
                "title": str(getattr(candidate, "title", "") or "")[:120],
                "source": str(getattr(candidate, "_tg115_source", "") or ""),
                "metadata_verified": bool(getattr(candidate, "_tg115_metadata_verified", False)),
                "confirmed": bool(identity and identity.confirmed),
                "reason": str(getattr(identity, "reason", "未进入身份确认") or "")[:120],
                "year_policy": str(getattr(identity, "year_policy", "") or ""),
                "identity_path": str(getattr(identity, "identity_path", "") or ""),
            })
        # A set of years is insufficient for diagnosing season-specific aliases:
        # expose only a bounded year -> candidate count histogram, never titles or
        # source URLs.  A 2026 S03 can therefore be distinguished from a stale
        # 2023/S02 candidate without weakening the final ID/type/season checks.
        candidate_year_distribution = {
            str(year): count for year, count in sorted(Counter(
                item.candidate_year for item in identities if item.candidate_year
            ).items())
        }
        site_torrents = [
            item for item in evaluation.get("torrents") or []
            if str(getattr(item, "_tg115_source", "") or "").lower() == "site"
        ]
        site_magnets = [
            item for item in site_torrents
            if str(getattr(item, "_tg115_pan_type", "") or "").lower() == "magnet"
        ]
        def site_quality_count(pattern: str) -> int:
            return sum(
                1 for item in site_magnets
                if _re.search(pattern, " ".join((
                    str(getattr(item, "title", "") or ""),
                    str(getattr(item, "description", "") or ""),
                )), _re.IGNORECASE)
            )
        return {
            "subscription": {"id": getattr(subscribe, "id", None), "title": str(getattr(subscribe, "name", "") or "")[:120],
                             "year": getattr(subscribe, "year", None), "season": target_season,
                             "target_season_year": target_season_year},
            "sources": evaluation["source_report"].text(),
            "counts": {
                "source_hits": len(evaluation.get("hits") or []),
                "season_before": evaluation.get("season_before", 0),
                "season_after": evaluation.get("season_after", 0),
                "metadata_verified": sum(bool(getattr(item, "_tg115_metadata_verified", False)) for item in evaluation.get("torrents") or []),
                "rule_passed": len(evaluation.get("matched") or []),
                "identity_checked": len(identities), "identity_confirmed": len(evaluation.get("confirmed") or []),
                "year_rejected": sum(item.year_policy == "year_conflict_rejected" for item in identities),
                "year_deferred": sum(item.year_policy == "tv_year_deferred_to_tmdb" for item in identities),
                "tmdb_matched": sum(item.match_source == "tmdb_id" for item in identities),
                "tmdb_mismatch": sum("TMDB ID 不匹配" in item.reason for item in identities),
                "type_mismatch": sum("媒体类型" in item.reason for item in identities),
                "season_mismatch": sum("季号" in item.reason for item in identities),
                "site_magnets": len(site_magnets),
                "site_chinese_1080p": site_quality_count(
                    r"(?:中字|中文|简中|繁中|简繁|\b(?:chs|cht|chinese)\b).*(?:1080[pi]?)|(?:1080[pi]?).*(?:中字|中文|简中|繁中|简繁|\b(?:chs|cht|chinese)\b)"
                ),
                "site_chinese_4k": site_quality_count(
                    r"(?:中字|中文|简中|繁中|简繁|\b(?:chs|cht|chinese)\b).*(?:4k|2160p|uhd)|(?:4k|2160p|uhd).*(?:中字|中文|简中|繁中|简繁|\b(?:chs|cht|chinese)\b)"
                ),
                "safe_candidates": len(evaluation.get("confirmed") or []),
            },
            "site_search": {
                "years": ["无年份" if item is None else item for item in evaluation.get("site_query_years", [])],
                "hits_by_year": dict(evaluation.get("site_query_hits") or {}),
            },
            "source_stats": dict(evaluation.get("source_stats") or {}),
            "candidate_year_distribution": candidate_year_distribution,
            "reason": str(evaluation.get("reason") or ""),
            "candidates": candidates,
        }

    def _handle_subscribe(self, subscribe_id: int):
        """单订阅的 TG 搜索 -> 匹配 -> 转存 -> 完成流程；任何失败均平滑回退。"""
        handled = False
        run_id = ""
        try:
            with self._lock:
                if subscribe_id in self._running_ids:
                    return
                self._running_ids.add(subscribe_id)

            subscribe = SubscribeOper().get(subscribe_id)
            if not subscribe:
                return
            if self._timeline:
                run_id = self._timeline.start(subscribe, "automatic")
                self._timeline.event(run_id, "loading_subscription", "running", "已读取订阅")
            if not self._claim_subscription(subscribe_id):
                logger.info(f"【TG115】订阅 {subscribe_id} 当前不可认领，本轮跳过")
                return

            if self._cms_tasks:
                active = self._cms_tasks.active_by_subscription(subscribe_id)
                if active:
                    logger.info(
                        "【TG115】订阅存在有效在途磁力任务: btih_prefix=%s state=%s decision=hold",
                        str(active.get("btih") or "")[:12],
                        active.get("status"),
                    )
                    handled = True
                    if self._timeline:
                        self._timeline.event(run_id, "pending_organize", "waiting_organize", "存在在途 115 任务", waiting_organize=True)
                    return
            if self._timeline:
                self._timeline.event(run_id, "searching_sources", "running", "开始搜索来源")
            evaluation = self._evaluate_subscription_candidates(subscribe)
            source_report = evaluation["source_report"]
            meta, mediainfo = evaluation.get("meta"), evaluation.get("mediainfo")
            candidates = evaluation.get("confirmed") or []
            if self._timeline:
                self._timeline.event(run_id, "source_results", "running", "来源召回完成", counts=dict(evaluation.get("source_stats") or {}))
                self._timeline.event(run_id, "identity_confirmation", "running", "规则与身份确认完成", counts={"confirmed": len(candidates)})
            attempted = set()
            if self._cms_tasks:
                attempted = self._cms_tasks.attempted_by_subscription(subscribe_id)
            queue_key = str(subscribe_id)
            magnet_candidates = [
                candidate for candidate in candidates
                if is_magnet_url(getattr(candidate, "page_url", "") or "")
            ]
            queue_snapshot = self._magnet_queues.get(queue_key) if isinstance(self._magnet_queues, dict) else None
            if not isinstance(queue_snapshot, dict):
                ordered_btih = [
                    btih_from_magnet(getattr(candidate, "page_url", "") or "")
                    for candidate in magnet_candidates
                ]
                queue_snapshot = {
                    "queue_id": queue_key,
                    "subscribe_id": subscribe_id,
                    "state": "ready",
                    "owner": "tg115",
                    "ordered_btih": ordered_btih,
                    "current_index": len(attempted),
                    "attempted_btih": sorted(attempted),
                    "max_attempts": self._magnet_max_attempts,
                    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "expires_at": (datetime.now().astimezone() + timedelta(hours=self._magnet_queue_timeout_hours)).isoformat(timespec="seconds"),
                }
                self._magnet_queues[queue_key] = queue_snapshot
                self._save_magnet_queues()
            queue_expired = False
            if queue_snapshot.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(str(queue_snapshot["expires_at"]).replace("Z", "+00:00"))
                    expires_at = expires_at if expires_at.tzinfo else expires_at.astimezone()
                    queue_expired = datetime.now().astimezone() >= expires_at
                except (TypeError, ValueError):
                    queue_expired = False
            if queue_expired:
                queue_snapshot["state"] = "released" if self._magnet_fallback_enabled else "expired"
                queue_snapshot["owner"] = "moviepilot" if self._magnet_fallback_enabled else "tg115"
                self._save_magnet_queues()
            ordered_btih = list(queue_snapshot.get("ordered_btih") or [])
            magnet_by_btih = {
                btih_from_magnet(getattr(candidate, "page_url", "") or ""): candidate
                for candidate in magnet_candidates
            }
            ordered_magnets = [
                magnet_by_btih[btih] for btih in ordered_btih
                if btih in magnet_by_btih and btih not in attempted
            ]
            if len(attempted) >= self._magnet_max_attempts or queue_expired:
                ordered_magnets = []
            first_magnet = next(
                (index for index, candidate in enumerate(candidates)
                 if is_magnet_url(getattr(candidate, "page_url", "") or "")),
                len(candidates),
            )
            leading = [candidate for candidate in candidates[:first_magnet] if not is_magnet_url(getattr(candidate, "page_url", "") or "")]
            trailing = [candidate for candidate in candidates[first_magnet:] if not is_magnet_url(getattr(candidate, "page_url", "") or "")]
            candidates = leading + ordered_magnets + trailing
            if not candidates:
                reason = evaluation.get("reason") or "候选未通过 MoviePilot/TMDB 身份确认"
                logger.info("【TG115】订阅 [%s] 只读候选评估未命中：%s", subscribe.name, reason)
                self._send_fail_notify(
                    subscribe, reason, source_report,
                    rejections=evaluation.get("rejections"),
                )
                if self._timeline:
                    self._timeline.event(run_id, "skipped", "skipped", reason)
                return

            identities = evaluation.get("identities") or {}

            def confirm(candidate):
                return identities[id(candidate)]

            def transfer_share(candidate):
                ok, message, _data = (
                    self._transfer.transfer(candidate.page_url or "", self._p115_target)
                    if self._transfer else (False, "转存模块未初始化", {})
                )
                return ok, message

            def inspect_share_cb(candidate):
                if not self._transfer:
                    return False, "转存模块未初始化", []
                return self._transfer.inspect_share(candidate.page_url or "", limit=32)

            execution = execute_auto_candidates(
                candidates=candidates,
                confirm_identity=confirm,
                submit_magnet=lambda candidate: self._submit_magnet_to_115(candidate, subscribe=subscribe),
                transfer_share=transfer_share,
                max_magnet_attempts=max(1, self._magnet_max_attempts - len(attempted)),
                magnet_failover_enabled=self._magnet_failover_enabled and len(attempted) < self._magnet_max_attempts,
                magnet_queue_timeout_hours=self._magnet_queue_timeout_hours,
                inspect_share=inspect_share_cb,
            )
            for error in execution.errors:
                logger.warning("【TG115】订阅 [%s] 候选处理失败，继续尝试下一候选: %s", subscribe.name, error)
            best = execution.candidate
            if not best:
                queue = self._magnet_queues.get(str(subscribe_id)) if isinstance(self._magnet_queues, dict) else None
                if isinstance(queue, dict):
                    queue["state"] = "released" if self._magnet_fallback_enabled else "exhausted"
                    queue["owner"] = "moviepilot" if self._magnet_fallback_enabled else "tg115"
                    self._save_magnet_queues()
                self._send_fail_notify(
                    subscribe,
                    execution.errors[-1] if execution.errors else "候选未能安全提交",
                    source_report,
                )
                handled = not self._magnet_fallback_enabled
                if self._timeline:
                    self._timeline.event(run_id, "recovered", "recovered", execution.errors[-1] if execution.errors else "候选未能安全提交")
                return
            if self._timeline:
                self._timeline.event(run_id, "submitting_magnet" if execution.via_magnet else "transferring_share", "running", "候选已提交", final_source=str(getattr(best, "_tg115_source", "") or ""), resource_kind="magnet" if execution.via_magnet else "pan")
            handled = self._finish_subscribe(
                subscribe, meta, mediainfo, best, execution.message,
                via_offline_magnet=execution.via_magnet,
                source_summary=source_report.text(),
            )
            if execution.via_magnet and isinstance(self._magnet_queues, dict):
                queue = self._magnet_queues.get(str(subscribe_id))
                if isinstance(queue, dict):
                    queue["state"] = "monitoring"
                    queue["owner"] = "tg115"
                    queue["current_index"] = len(attempted)
                    self._save_magnet_queues()
            if self._timeline:
                wait_organize = bool(execution.via_magnet or self._wait_for_mp_organize)
                self._timeline.event(run_id, "pending_organize" if wait_organize else "completed", "waiting_organize" if wait_organize else "completed", "等待 MoviePilot 整理确认" if wait_organize else "订阅处理完成", waiting_organize=wait_organize, subscription_written=bool(handled))
            return

            source_report = SearchReport({
                "tg": bool(self._tg_search_enabled and self._scraper and any(
                    channel.get("enabled", True) for channel in self._tg_channels
                )),
                "site": bool(self._site_scraper),
                "pansou": bool(self._pansou_client),
                "juying": bool(self._juying_api),
            })

            try:
                meta = build_subscribe_meta(subscribe)
            except Exception as e:
                logger.warn(f"【TG115】构造订阅 meta 失败，回退: {e}")
                return
            mediainfo = self._recognize(subscribe, meta)
            if not mediainfo:
                logger.warn(f"【TG115】订阅 {subscribe.name} 未识别到媒体信息，回退到默认搜索")
                return

            seasons = target_seasons(subscribe)
            target_season = seasons[0] if len(seasons) == 1 else getattr(subscribe, "season", None)
            season_text = ",".join(f"S{season:02d}" for season in seasons) or "未指定"
            logger.info(f"【TG115】订阅 [{subscribe.name}] 目标季解析完成: {season_text}")
            keywords = self._build_keywords(subscribe, mediainfo, target_season)
            hits = []
            for keyword in keywords:
                logger.info(
                    f"【TG115】订阅 [{subscribe.name}] "
                    f"{f'S{target_season:02d} ' if target_season is not None else ''}"
                    f"开始搜索，关键字: {keyword}"
                )
                keyword_hits = self._search_auto_sources(
                    keyword=keyword,
                    year=subscribe.year,
                    media_type=getattr(subscribe, "type", ""),
                    target_season=target_season,
                    source_report=source_report,
                )
                if target_season is not None:
                    matched_season = []
                    for hit in keyword_hits:
                        if supports_target_season(hit, target_season):
                            matched_season.append(hit)
                        else:
                            hit_seasons = candidate_seasons(hit)
                            season_label = ",".join(
                                f"S{s:02d}" for s in sorted(hit_seasons)
                            ) or "无明确季号"
                            logger.info(
                                f"【TG115】订阅 [{subscribe.name}] S{target_season:02d} "
                                f"本地季号初筛拒绝: title=%s 候选季号=%s",
                                str(getattr(hit, "resource_title", "")
                                    or getattr(hit, "title", "") or "")[:80],
                                season_label,
                            )
                    logger.info(
                        f"【TG115】订阅 [{subscribe.name}] S{target_season:02d} "
                        f"本地季号初筛: {len(keyword_hits)} 条 -> {len(matched_season)} 条"
                    )
                    hits.extend(matched_season)
                    if len(matched_season) >= 5:
                        break
                else:
                    hits.extend(keyword_hits)
                    if keyword_hits:
                        break
            hits = deduplicate_search_hits(hits)
            if not hits:
                logger.info(f"【TG115】订阅 [{subscribe.name}] 未找到资源，回退到默认搜索")
                self._send_fail_notify(
                    subscribe, "未找到符合目标季与标题的候选", source_report
                )
                return

            torrents = self._build_torrents(hits)
            self._enrich_share_metadata(torrents, subscribe=subscribe, mediainfo=mediainfo)
            matched, rule_diagnostics = self._filter_resources(subscribe, mediainfo, torrents)
            if not matched:
                reason = rule_diagnostics.summary() if rule_diagnostics else "候选未通过 MoviePilot 规则"
                logger.info(
                    f"【TG115】订阅 [{subscribe.name}] 资源均不符合 MP 过滤规则，"
                    f"原因: {reason}，回退到默认搜索"
                )
                self._send_fail_notify(
                    subscribe, reason, source_report
                )
                return

            is_tv = is_tv_media(getattr(subscribe, "type", None))
            auto_rejections: list = []
            auto_candidates = select_auto_candidates(
                torrents=matched,
                prefer_site_magnet=(
                self._site_magnet_priority
                    and bool(self._offline_client and self._p115_cookie)
                ),
                is_tv=is_tv,
                is_115_url=P115Transfer._is_115_share_url,
                rejection_collector=auto_rejections,
            )
            # Preserve TG 115 -> Guanying 115 -> Guanying magnet -> Juying.
            auto_candidates = list(auto_candidates)
            if not auto_candidates:
                reason = summarize_rejections(auto_rejections)
                logger.info(
                    f"【TG115】订阅 [{subscribe.name}] 命中 {len(matched)} 条资源，"
                    f"但没有可安全自动处理的资源：{reason}"
                )
                self._send_fail_notify(
                    subscribe,
                    reason,
                    source_report,
                    rejections=auto_rejections,
                )
                return
            def confirm(candidate):
                identity = confirm_candidate_identity(
                    subscribe=subscribe,
                    target_media=mediainfo,
                    torrent=candidate,
                    recognize_candidate=self._recognize_candidate,
                )
                logger.info(
                    f"【TG115】候选身份确认 [{candidate.title}]: "
                    f"confirmed={identity.confirmed}, source={identity.match_source}, "
                    f"reason={identity.reason}"
                )
                return identity

            def transfer_share(candidate):
                ok, message, _data = (
                    self._transfer.transfer(candidate.page_url or "", self._p115_target)
                    if self._transfer
                    else (False, "转存模块未初始化", {})
                )
                return ok, message

            def inspect_share_cb(candidate):
                if not self._transfer:
                    return False, "转存模块未初始化", []
                return self._transfer.inspect_share(candidate.page_url or "", limit=32)

            execution = execute_auto_candidates(
                candidates=auto_candidates,
                confirm_identity=confirm,
                submit_magnet=lambda candidate: self._submit_magnet_to_115(
                    candidate, subscribe=subscribe
                ),
                transfer_share=transfer_share,
                max_magnet_attempts=self._magnet_max_attempts,
                magnet_failover_enabled=self._magnet_failover_enabled,
                magnet_queue_timeout_hours=self._magnet_queue_timeout_hours,
                inspect_share=inspect_share_cb,
            )
            for error in execution.errors:
                logger.warn(f"【TG115】订阅 [{subscribe.name}] 候选处理失败，继续回退: {error}")
            best = execution.candidate
            if not best:
                logger.warn(
                    f"【TG115】订阅 [{subscribe.name}] 已检查 {len(auto_candidates)} 条自动候选，"
                    f"其中 {execution.recognition_attempts} 条进入 MoviePilot 识别，"
                    "没有候选成功提交，回退到默认搜索"
                )
                reason = execution.errors[-1] if execution.errors \
                    else execution.rejection_summary() or "候选未通过 MoviePilot/TMDB 身份确认"
                self._send_fail_notify(subscribe, reason, source_report)
                return
            logger.info(f"【TG115】订阅 [{subscribe.name}] 命中资源: {best.title}（链接已省略）")

            handled = self._finish_subscribe(
                subscribe, meta, mediainfo, best, execution.message,
                via_offline_magnet=execution.via_magnet,
                source_summary=source_report.text(),
            )
        except Exception as e:
            logger.error(f"【TG115】处理订阅 {subscribe_id} 异常，回退到默认搜索: {e}")
            if self._timeline and run_id:
                self._timeline.event(run_id, "failed", "failed", "处理异常，已安全回退")
        finally:
            if handled:
                self._complete_claim(subscribe_id)
            else:
                self._restore_claim(subscribe_id)
            with self._lock:
                self._running_ids.discard(subscribe_id)
            self._save_diagnostics()

    # ============================ 辅助方法 ============================
    def _search_auto_sources(
            self, keyword: str, year: Optional[int], media_type: Any = "",
            target_season: Optional[int] = None,
            source_report: Optional[SearchReport] = None,
            site_years: Optional[List[Optional[int]]] = None,
            search_diagnostics: Optional[Dict[str, int]] = None,
            deadline: Optional[float] = None) -> List[Any]:
        """Search enabled sources with per-source TTL caching and circuit breaking."""
        hits: List[Any] = []
        source_calls = []
        if self._tg_search_enabled and self._scraper and any(
                channel.get("enabled", True) for channel in self._tg_channels):
            source_calls.append(("tg", lambda: self._scraper.search(keyword), self._scraper))
        elif source_report:
            source_report.mark("tg", "disabled" if not self._tg_search_enabled else "empty")
        if self._site_scraper:
            # TV sources are commonly indexed by season premiere year, series
            # year, or no year at all. Each pass has an independent cache key.
            # Movies retain their single strict subscription-year query.
            query_years = site_years if site_years is not None else [year]
            site_keyword = site_title_keyword(keyword) or keyword
            for query_year in query_years:
                source_calls.append((
                    "site", lambda query_year=query_year: self._site_scraper.search(
                        site_keyword, year=query_year, target_season=target_season
                    )[0], self._site_scraper, query_year,
                ))
        if self._pansou_client:
            source_calls.append((
                "pansou", lambda: self._pansou_client.search(
                    keyword, year=year, media_type=media_type, season=target_season,
                    refresh=self._pansou_refresh, cloud_types=self._pansou_cloud_types,
                    request_timeout=self._pansou_timeout,
                ), self._pansou_client, year,
            ))
        if self._juying_api:
            source_calls.append((
                "juying", lambda: self._juying_api.search(keyword, year=year),
                self._juying_api, year,
            ))

        # Retain the historical tuple shape for TG while allowing site passes
        # to carry their real query year into cache and dry-run diagnostics.
        source_calls = [
            item if len(item) == 4 else (item[0], item[1], item[2], year)
            for item in source_calls
        ]

        for source, callback, client, source_year in source_calls:
            deadline_remaining = None if deadline is None else deadline - time.monotonic()
            if deadline_remaining is not None and deadline_remaining <= 0:
                if source_report:
                    source_report.mark(source, "timeout")
                logger.warning("【TG115】%s 来源未开始：本轮搜索总时限已到", source)
                break
            cache_keyword = site_keyword if source == "site" else keyword
            cache_key = source_cache_key(
                source, cache_keyword, source_year, media_type, target_season,
                ",".join(self._pansou_cloud_types) if source == "pansou" else "",
            )
            cached = self._search_cache.get(cache_key) if self._search_cache else None
            if cached is not None:
                distribution = season_distribution(cached)
                if not cache_covers_season(cached, target_season):
                    existing = ",".join(f"S{item:02d}" for item in distribution) or "无明确季号"
                    logger.info(
                        f"【TG115】{source} S{target_season:02d} 缓存仅包含 {existing}，重新搜索"
                    )
                    cached = None
            if cached is not None:
                for hit in cached:
                    try:
                        setattr(hit, "_tg115_source", source)
                    except Exception:
                        pass
                hits.extend(cached)
                if source == "site" and search_diagnostics is not None:
                    key = "无年份" if source_year is None else str(source_year)
                    search_diagnostics[key] = search_diagnostics.get(key, 0) + len(cached)
                if source_report:
                    source_report.record(source, cached, cached=True)
                if source == "pansou":
                    self._pansou_cache_hits += 1
                logger.info(
                    f"【TG115】{source} S{target_season:02d} 命中周期搜索缓存 {len(cached)} 条"
                    if target_season is not None
                    else f"【TG115】{source} 命中周期搜索缓存 {len(cached)} 条"
                )
                continue
            allowed, cooldown_remaining = self._source_breaker.allow(source) \
                if self._source_breaker else (True, 0)
            if not allowed:
                if source_report:
                    source_report.mark(source, "cooldown")
                logger.warn(f"【TG115】{source} 来源熔断中，剩余 {cooldown_remaining} 秒，本轮跳过")
                continue
            try:
                runner = self._source_runner or BoundedSourceRunner()
                call_timeout = self._source_request_timeout_seconds
                # PanSou has its own short 429/5xx retry.  Give the LAN
                # aggregator one bounded retry window instead of ending it at
                # its base HTTP timeout.
                if source == "pansou":
                    call_timeout = max(call_timeout, min(45.0, self._pansou_timeout + 25.0))
                if deadline_remaining is not None:
                    call_timeout = min(call_timeout, max(0.1, deadline_remaining))
                call_status, source_hits, elapsed, call_error = runner.run(
                    source, callback, call_timeout,
                )
                if call_status == "busy":
                    if source_report:
                        source_report.mark(source, "busy")
                    logger.warning("【TG115】%s 上一请求仍在结束中，本轮跳过避免并发", source)
                    continue
                if call_status == "timeout":
                    # TG can return completed-channel results even while a few
                    # channels are still blocked. Keep that bounded partial data.
                    source_hits = []
                    if source == "tg" and hasattr(client, "partial_result"):
                        snapshot = client.partial_result() or {}
                        source_hits = list(snapshot.get("items") or [])
                    if source_report:
                        source_report.mark(source, "timeout")
                    if self._source_health:
                        self._source_health.record(source, "timeout", elapsed, len(source_hits))
                    if self._source_breaker:
                        self._source_breaker.failure(source, "request timeout")
                    logger.warning(
                        "【TG115】%s 请求超过 %.0f 秒，已释放订阅队列%s",
                        source, call_timeout,
                        "并保留已完成频道结果" if source_hits else "",
                    )
                    for hit in source_hits:
                        try:
                            setattr(hit, "_tg115_source", source)
                        except Exception:
                            pass
                    hits.extend(source_hits)
                    continue
                if call_status == "failed":
                    raise call_error or RuntimeError("source callback failed")
                source_hits = source_hits or []
                for hit in source_hits:
                    # Preserve source identity through the common TorrentInfo
                    # conversion so automatic ordering is deterministic.
                    try:
                        setattr(hit, "_tg115_source", source)
                    except Exception:
                        pass
                    if source == "site":
                        try:
                            setattr(hit, "_tg115_site_query_year", source_year)
                        except Exception:
                            pass
                if source == "site" and search_diagnostics is not None:
                    key = "无年份" if source_year is None else str(source_year)
                    search_diagnostics[key] = search_diagnostics.get(key, 0) + len(source_hits)
                status = getattr(client, "last_error_status", None)
                source_error = str(getattr(client, "last_error", "") or "")
                if source_report:
                    source_report.record(source, source_hits)
                if status in (403, 429):
                    if self._source_health:
                        self._source_health.record(source, str(status), elapsed, len(source_hits))
                    if source_report:
                        source_report.mark(source, "error")
                    opened = self._source_breaker.failure(source, f"HTTP {status}") \
                        if self._source_breaker else False
                    if opened:
                        logger.warn(f"【TG115】{source} 连续失败达到阈值，已进入冷却")
                elif source_error and not source_hits:
                    if self._source_health:
                        self._source_health.record(source, "timeout" if "timeout" in source_error.lower() else "failed", elapsed, 0)
                    if source_report:
                        source_report.mark(source, "error")
                    opened = self._source_breaker.failure(source, source_error) \
                        if self._source_breaker else False
                    logger.warn(
                        f"【TG115】{source} 搜索失败分类={source_error}，本轮未缓存空结果"
                        f"{'，已进入冷却' if opened else ''}"
                    )
                elif self._source_breaker:
                    self._source_breaker.success(source)
                if self._source_health and not (status in (403, 429) or (source_error and not source_hits)):
                    self._source_health.record(source, "success" if source_hits else "empty", elapsed, len(source_hits))
                if self._search_cache and should_cache_source_result(status, source_error):
                    self._search_cache.set(cache_key, source_hits)
                hits.extend(source_hits)
            except Exception as exc:
                if self._source_health:
                    self._source_health.record(source, "timeout" if "timeout" in type(exc).__name__.lower() else "failed")
                if source_report:
                    source_report.mark(source, "error")
                opened = self._source_breaker.failure(source, str(exc)) \
                    if self._source_breaker else False
                logger.warn(
                    f"【TG115】{source} 搜索异常，本轮跳过"
                    f"{'并进入冷却' if opened else ''}: {exc}"
                )
        return hits

    def _save_cms_tasks(self):
        if not self._cms_tasks:
            return
        try:
            self.save_data(CMS_TASKS_KEY, self._cms_tasks.dump_records())
        except Exception as exc:
            logger.warn(f"【TG115】保存 CMS 任务账本失败: {exc}")

    def _save_magnet_queues(self):
        try:
            self.save_data(MAGNET_QUEUES_KEY, self._magnet_queues)
        except Exception as exc:
            logger.warn(f"【TG115】保存磁力候选队列失败: {exc}")

    def _complete_task_record(self, record: Dict[str, Any], confirmation_source: str) -> bool:
        current = self._cms_tasks.latest(record.get("btih")) if self._cms_tasks else None
        if not current or current.get("status") in {"failed", "timed_out"}:
            return False
        if current.get("status") == "completed" and current.get("completion_notified"):
            return False
        completed = self._cms_tasks.update(
            current["btih"],
            "completed",
            completion_notified=False,
            progress=100,
        )
        if not completed:
            return False
        sid = completed.get("subscribe_id")
        queue = self._magnet_queues.get(str(sid)) if sid else None
        if isinstance(queue, dict):
            queue["state"] = "completed"
            queue["owner"] = "none"
            queue["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            self._save_magnet_queues()
        self._save_cms_tasks()
        subscribe = SubscribeOper().get(int(sid)) if sid else None
        notification_resolved = not self._notify_success or not subscribe
        if not subscribe and self._notify_success:
            logger.warning(
                "【任务完成】任务=%s 最终状态=completed 通知状态=跳过 原因=订阅记录不存在",
                completed.get("title") or "未命名资源",
            )
        if subscribe and self._notify_success:
            try:
                self._post_search_notification_once(
                    subscribe=subscribe,
                    outcome="completed",
                    mtype=NotificationType.Subscribe,
                    title=subscription_notification_title(subscribe),
                    text=(
                        "结果：资源已完成 MoviePilot 整理。\n"
                        f"资源：{completed.get('title') or getattr(subscribe, 'name', '未命名资源')}\n"
                        "下载状态：已完成\n"
                        "整理状态：已完成\n"
                        "任务状态：已完成\n"
                        "处理方式：插件内置 115 离线下载\n"
                        f"确认来源：{confirmation_source}"
                    ),
                )
                notification_resolved = True
            except Exception as exc:
                logger.warning(
                    "【任务完成】任务=%s 最终状态=completed 通知状态=失败 动作=保留待重试 reason=%s",
                    completed.get("title") or "未命名资源",
                    type(exc).__name__,
                )
        if notification_resolved:
            self._cms_tasks.update(completed["btih"], "completed", completion_notified=True)
            self._save_cms_tasks()
        logger.info(
            "【任务完成】任务=%s btih_prefix=%s 下载状态=已完成 MP整理状态=已完成 最终状态=completed 确认来源=%s 动作=停止轮询",
            completed.get("title") or "未命名资源",
            str(completed.get("btih") or "")[:12],
            confirmation_source,
        )
        return True

    def _reconcile_cms_tasks(self, force_direct_poll: bool = False):
        if not self._reconcile_lock.acquire(blocking=False):
            return
        try:
            self._reconcile_cms_tasks_locked(force_direct_poll)
        finally:
            self._reconcile_lock.release()

    def _reconcile_cms_tasks_locked(self, force_direct_poll: bool = False):
        if not self._cms_tasks:
            return
        oper = SubscribeOper()

        def subscription_exists(sid: int) -> bool:
            return bool(oper.get(sid))

        def history_exists(record: Dict[str, Any]) -> bool:
            return bool(oper.exist_history(
                tmdbid=record.get("tmdb_id"),
                doubanid=record.get("douban_id"),
                season=record.get("season"),
            ))

        def restore_subscription(sid: int):
            subscribe = oper.get(sid)
            if subscribe and str(getattr(subscribe, "state", "") or "").upper() == "P":
                oper.update(sid, {"state": "N"})
                logger.warn(f"【TG115】CMS 任务超时，订阅 {sid} 已恢复为 state=N")

        now_monotonic = time.monotonic()
        should_poll_direct = force_direct_poll or now_monotonic - self._offline_last_poll >= self._offline_poll_seconds
        result = self._cms_tasks.reconcile(
            timeout_hours=self._cms_timeout_hours,
            subscription_exists=subscription_exists,
            history_exists=history_exists,
            restore_subscription=restore_subscription,
            direct_timeout_hours=self._direct_timeout_hours,
            unknown_timeout_minutes=(
                None if self._offline_client and should_poll_direct
                else self._magnet_rotation_unknown_timeout_minutes
            ),
        )
        if self._offline_client and should_poll_direct:
            self._offline_last_poll = now_monotonic
            for record in self._cms_tasks.dump_records():
                if record.get("source") != "115_direct" or record.get("status") not in {"submitted", "downloading", "unknown"}:
                    continue
                task_id = record.get("task_id") or record.get("btih")
                try:
                    state = self._offline_client.get_task_status(task_id)
                    status = state.get("status")
                    if status == "completed":
                        self._cms_tasks.update(
                            record["btih"], "pending_organize", progress=100,
                            task_id=task_id,
                            target_cid=state.get("target_cid") or record.get("target_cid", ""),
                            download_name=state.get("name", ""),
                        )
                    elif status in {"downloading", "submitted", "failed", "cancelled", "no_resource"}:
                        self._cms_tasks.update(record["btih"], status, progress=state.get("progress"), task_id=task_id, error_code=state.get("error_code", ""), error_message=state.get("message", ""))
                        if status in {"submitted", "downloading"}:
                            logger.info(
                                "【TG115】磁力任务有效: position=%s/%s state=%s decision=hold",
                                record.get("position", 0),
                                record.get("candidate_total", 0),
                                status,
                            )
                        else:
                            self._offline_client.forget_task(record.get("btih", ""))
                            if record.get("subscribe_id"):
                                restore_subscription(int(record["subscribe_id"]))
                                logger.info(
                                    "【TG115】磁力候选已%s: position=%s/%s btih_prefix=%s decision=switch_next",
                                    "取消" if status == "cancelled" else ("无资源" if status == "no_resource" else "失败"),
                                    record.get("position", 0),
                                    record.get("candidate_total", 0),
                                    str(record.get("btih") or "")[:12],
                                )
                                if self._coordinator and (status != "cancelled" or self._magnet_cancel_failover):
                                    self._coordinator.enqueue_subscription(int(record["subscribe_id"]), priority=0)
                except Exception as exc:
                    logger.warning("【TG115】115 任务状态查询失败 btih=%s... reason=%s", str(record.get("btih", ""))[:12], type(exc).__name__)
            unknown_result = self._cms_tasks.reconcile(
                timeout_hours=self._cms_timeout_hours,
                subscription_exists=subscription_exists,
                history_exists=history_exists,
                restore_subscription=restore_subscription,
                direct_timeout_hours=self._direct_timeout_hours,
                unknown_timeout_minutes=self._magnet_rotation_unknown_timeout_minutes,
            )
            for key in result:
                result[key] += unknown_result[key]
            self._save_cms_tasks()
            for record in self._cms_tasks.dump_records():
                subscribe_id = record.get("subscribe_id")
                queue = self._magnet_queues.get(str(subscribe_id)) if subscribe_id else None
                if not isinstance(queue, dict):
                    continue
                attempted = self._cms_tasks.attempted_by_subscription(subscribe_id)
                queue["attempted_btih"] = sorted(attempted)
                queue["current_index"] = len(attempted)
                if record.get("status") == "completed":
                    queue["state"] = "completed"
                    queue["owner"] = "none"
                elif record.get("status") in {"waiting", "submitted", "downloading", "pending_organize", "unknown"}:
                    queue["state"] = "monitoring"
                    queue["owner"] = "tg115"
                else:
                    queue["state"] = "switch_pending"
                    queue["owner"] = "tg115"
            self._save_magnet_queues()
        for record in self._cms_tasks.dump_records():
            if record.get("status") == "completed" and not record.get("completion_notified"):
                self._complete_task_record(record, "MoviePilot 整理历史")
        if result["completed"] or result["failed"] or result["timed_out"]:
            self._save_cms_tasks()
            logger.info(
                "【TG115】任务对账：完成=%s 异常=%s 超时=%s，已完成任务停止轮询",
                result["completed"], result["failed"], result["timed_out"],
            )

    def _recognize(self, subscribe, meta) -> Optional[MediaInfo]:
        try:
            def operation(chain):
                return chain.recognize_media(
                    meta=meta, mtype=meta.type,
                    tmdbid=subscribe.tmdbid, doubanid=subscribe.doubanid,
                    episode_group=subscribe.episode_group, cache=True,
                )

            mediainfo = self._run_recognition(
                factory=MediaChain,
                operation=operation,
                label="subscription",
            )
            if mediainfo:
                self._hydrate_tv_season_years(mediainfo, subscribe)
                return mediainfo
        except RecognitionUnavailable as exc:
            logger.warning(
                f"【TG115】MoviePilot 媒体识别暂不可用 reason={exc.reason}"
            )
        except Exception as exc:
            logger.warning(
                f"【TG115】MoviePilot 媒体识别异常 type={type(exc).__name__}"
            )
        try:
            media_type = to_moviepilot_media_type(subscribe.type, MediaType)
            if not media_type:
                logger.warning("【TG115】订阅媒体类型无法兼容，已安全回退默认搜索")
                return None
            mediainfo = MediaInfo(
                type=media_type, title=subscribe.name, year=subscribe.year,
                tmdb_id=subscribe.tmdbid, douban_id=subscribe.doubanid,
            )
            self._hydrate_tv_season_years(mediainfo, subscribe)
            return mediainfo
        except Exception as exc:
            logger.warning(f"【TG115】订阅媒体类型兜底失败 type={type(exc).__name__}")
            return None

    def _run_recognition(self, factory, operation, label: str):
        gate = self._recognition_gate
        if not gate:
            raise RecognitionUnavailable("媒体识别协调器未运行")

        def on_retry(stage: str, attempt: int, reason: str):
            if reason == "kill_cursor":
                message = "遇到 NoneType.kill_cursor"
            else:
                message = "返回空结果（核心异常可能已被内部捕获）"
            logger.warning(
                f"【TG115】{stage} 识别第 {attempt} 次{message}，"
                "已丢弃识别链并准备安全重试"
            )

        return gate.run(
            factory, operation, label=label, on_retry=on_retry,
            retry_none=True,
        )

    def _recognize_candidate(self, candidate_meta, episode_group=None):
        try:
            return self._run_recognition(
                factory=MediaChain,
                operation=lambda chain: chain.recognize_by_meta(
                    candidate_meta,
                    episode_group=episode_group,
                    obtain_images=False,
                ),
                label="candidate",
            )
        except RecognitionUnavailable:
            # Newer MP/PostgreSQL combinations can occasionally fail while
            # releasing MediaChain's recognition cursor. Resolve the already
            # subscribed TMDB record directly, then IdentityMatcher re-runs
            # TorrentHelper against its official aliases before accepting it.
            target_tmdb_id = getattr(candidate_meta, "_tg115_target_tmdb_id", None)
            target_type = to_moviepilot_media_type(
                getattr(candidate_meta, "_tg115_target_type", None), MediaType
            )
            if not target_tmdb_id or not target_type:
                raise
            try:
                target_tmdb_id = int(target_tmdb_id)
            except (TypeError, ValueError):
                raise
            # Do not send the exact subscribed-ID fallback through the generic
            # recognition gate. On current MoviePilot/PostgreSQL hosts that gate
            # may be recovering MediaChain's cursor lifecycle error; TmdbChain
            # is an independent, read-only native lookup and is already used by
            # the season-year hydrator.
            cache_key = (target_tmdb_id, str(getattr(target_type, "value", target_type)))
            tmdb_info = self._target_tmdb_cache.get(cache_key) if self._target_tmdb_cache else None
            if tmdb_info is None:
                try:
                    tmdb_info = TmdbChain().tmdb_info(
                        tmdbid=target_tmdb_id, mtype=target_type
                    )
                except Exception as exc:
                    logger.warning(
                        "【TG115】目标 TMDB 元数据读取失败 type=%s",
                        type(exc).__name__,
                    )
                    raise RecognitionUnavailable("目标 TMDB 媒体信息不可用") from exc
                if tmdb_info and self._target_tmdb_cache:
                    self._target_tmdb_cache.set(cache_key, tmdb_info)
            if not tmdb_info:
                raise RecognitionUnavailable("目标 TMDB 媒体信息不可用")
            candidate = MediaInfo(tmdb_info=dict(tmdb_info))
            setattr(candidate, "_tg115_target_metadata_fallback", True)
            return candidate

    def _hydrate_tv_season_years(self, mediainfo, subscribe) -> None:
        """Fill missing TV season premiere years through MP's read-only TMDB chain."""
        if not mediainfo or not is_tv_media(getattr(mediainfo, "type", None)):
            return
        try:
            target_season = int(getattr(subscribe, "season", None))
        except (TypeError, ValueError):
            return
        existing = getattr(mediainfo, "season_years", None) or {}
        if existing.get(target_season, existing.get(str(target_season))):
            return
        tmdb_id = getattr(subscribe, "tmdbid", None) or getattr(mediainfo, "tmdb_id", None)
        try:
            tmdb_id = int(tmdb_id)
        except (TypeError, ValueError):
            return
        cache_key = (tmdb_id, target_season)
        cached = self._season_year_cache.get(cache_key) if self._season_year_cache else None
        if cached is None:
            try:
                cached = season_year_map(TmdbChain().tmdb_seasons(tmdb_id))
            except Exception as exc:
                logger.warning("【TG115】TMDB 季首播年份读取失败 type=%s", type(exc).__name__)
                cached = {}
            if self._season_year_cache:
                self._season_year_cache.set(cache_key, cached)
        if cached:
            merged = dict(existing)
            merged.update(cached)
            mediainfo.season_years = merged

    @staticmethod
    def _build_keyword(subscribe) -> str:
        """构建搜索关键字：只用片名（不含年份）。

        v4.0：TG 服务端 ``?q=`` 搜索频道全部历史。TG 消息里大多不写年份，
        带年份会漏掉大量命中，故搜索词只取片名；年份 / 分辨率等精细过滤
        交给 MoviePilot 的规则引擎 ``_filter_resources`` 处理。
        """
        return str(subscribe.name or "").strip()

    @classmethod
    def _build_keywords(cls, subscribe, mediainfo, season: Optional[int]) -> List[str]:
        """Build a bounded alias-aware query list for one MoviePilot subscription row."""
        names: List[Any] = [
            getattr(subscribe, "name", ""),
            getattr(mediainfo, "title", ""),
            getattr(mediainfo, "en_title", ""),
            getattr(mediainfo, "original_title", ""),
            getattr(mediainfo, "original_name", ""),
        ]
        aliases = getattr(mediainfo, "names", None) or []
        if isinstance(aliases, (list, tuple, set)):
            names.extend(aliases)
        keywords = season_keywords(names, season, limit=6)
        return keywords or [cls._build_keyword(subscribe)]

    @staticmethod
    def _build_torrents(hits) -> List[TorrentInfo]:
        torrents: List[TorrentInfo] = []
        for h in hits:
            url = h.share_url or ""
            rc = getattr(h, "receive_code", "") or ""
            # 115 链接：若提取码未附在 URL 上，补上（share_receive 需要 receive_code）
            if url and P115Transfer._is_115_share_url(url) and rc \
                    and "password=" not in url and "receive_code=" not in url and "pwd=" not in url:
                url = url + ("&" if "?" in url else "?") + f"password={rc}"
            elif url and P115Transfer._is_115_share_url(url) and not rc \
                    and "password=" not in url and "receive_code=" not in url and "pwd=" not in url:
                logger.info(
                    "【TG115】115 分享缺少提取码：%s",
                    (h.resource_title or "")[:60],
                )
            resource_title = h.resource_title or ""
            source_title = str(getattr(h, "source_title", "") or "").strip()
            source_year = getattr(h, "year", None)
            identity_title = clean_identity_title(
                resource_title, source_title, source_year, h.text or ""
            )
            display_title = resource_title or identity_title or "未命名资源"
            parsed_meta = TgSearch115._parse_resource_meta(h.text or resource_title)
            normalized = normalize_resource_metadata({
                "share_url": url, "pan_type": getattr(h, "pan_type", "") or "",
                "resource_title": resource_title, "text": h.text or "",
                "is_complete": parsed_meta.get("is_complete"),
                "source": getattr(h, "_tg115_source", ""),
                "upstream_source": getattr(h, "upstream_source", ""),
            })
            pan_type = normalized["pan_type"]
            torrent = TorrentInfo(
                title=display_title,
                description=h.text,
                enclosure=url if pan_type == "magnet" else None,
                page_url=url,
                site_name=getattr(h, "channel_name", None) or "TG频道",
                pubdate=h.pub_date,
                size=0.0, seeders=0, peers=0,
            )
            # 身份识别只使用干净标题；质量过滤仍使用包含资源格式的完整 title。
            setattr(torrent, "_tg115_identity_title", identity_title)
            setattr(torrent, "_tg115_source_title", source_title)
            setattr(torrent, "_tg115_source_year", source_year)
            setattr(torrent, "_tg115_pan_type", pan_type)
            setattr(torrent, "_tg115_source", str(getattr(h, "_tg115_source", "") or "").lower())
            setattr(torrent, "_tg115_upstream_source", str(getattr(h, "upstream_source", "") or "").strip())
            setattr(torrent, "_tg115_is_complete", bool(parsed_meta.get("is_complete")))
            setattr(torrent, "_tg115_metadata", normalized)
            # A magnet returned by the site's detail API has a concrete resource
            # title, page title and query year. Permit it to reach the exact
            # MoviePilot ID/type recognizer even if its local alias parser is
            # incomplete. It is not a confirmation and cannot bypass that check.
            if (getattr(torrent, "_tg115_source", "") in {"site", "pansou"}
                    and pan_type == "magnet" and source_title and resource_title):
                setattr(torrent, "_tg115_metadata_verified", True)
            # 115 分享页不提供 Tracker 种子大小、做种、促销和发布时间。该标记只供
            # 插件侧兼容器使用，避免把 0/未知当成真实值交给规则组误拒绝。
            if P115Transfer._is_115_share_url(url):
                setattr(torrent, "_tg115_unavailable_rule_fields", {
                    "size", "seeders", "downloadvolumefactor", "publish_time",
                })
            logger.info(
                "【TG115】[候选] source=%s type=%s title=%s",
                str(getattr(h, "_tg115_source", "") or "unknown"),
                pan_type or "unknown",
                display_title,
            )
            torrents.append(torrent)
        return torrents

    def _submit_magnet_to_115(self, torrent: TorrentInfo, subscribe=None) -> Tuple[bool, str]:
        """Submit a confirmed magnet using the built-in 115 client only."""
        magnet = str(torrent.enclosure or torrent.page_url or "").strip()
        if not is_magnet_url(magnet):
            return False, "磁力链接无效"
        if not btih_from_magnet(magnet):
            return False, "磁力链接缺少有效 BTIH"
        btih = btih_from_magnet(magnet)
        record = None
        if self._cms_tasks and btih:
            record, created = self._cms_tasks.reserve(
                magnet=magnet,
                title=torrent.title or "未命名资源",
                subscribe=subscribe,
                status="waiting",
            )
            if not created:
                same_subscription = bool(
                    subscribe and record.get("subscribe_id") == getattr(subscribe, "id", None)
                )
                if same_subscription:
                    return True, "相同 BTIH 的 115 磁力任务已存在，已跳过重复提交"
                return False, "相同 BTIH 已由其它任务处理，本订阅继续尝试后续候选"
            record["position"] = int(getattr(torrent, "_tg115_candidate_position", 0) or 0)
            record["candidate_total"] = int(getattr(torrent, "_tg115_candidate_total", 0) or 0)
            self._save_cms_tasks()
            classification = classify_resource(torrent, identity_status="confirmed", mp_rule_status="passed")
            logger.info(
                "【TG115】磁力候选选择: position=%s/%s magnet=%s %s",
                record["position"],
                record["candidate_total"],
                magnet,
                format_resource_classification(classification),
            )
        direct_result: Dict[str, Any] = {}
        direct_target_cid = ""
        if not self._offline_client:
            return False, "115 直连未配置"
        try:
            direct_target_cid = self._resolve_offline_target_cid()
        except Exception as exc:
            return False, f"115 目标目录不可用: {exc}"
        direct_result = self._offline_client.submit_magnet(magnet, direct_target_cid)
        ok = bool(direct_result.get("success"))
        message = str(direct_result.get("message") or "115 直连提交失败")
        source = "115_direct"
        direct_status = str(direct_result.get("status") or "")
        unknown = direct_status == "unknown"
        if self._cms_tasks and record:
            self._cms_tasks.update(
                record["btih"], "unknown" if unknown else ("submitted" if ok else "failed"),
                "" if ok else message, source="115_direct" if unknown else source,
                task_id=(direct_result.get("task_id") or btih) if source == "115_direct" else "",
                target_cid=direct_target_cid if source == "115_direct" else "",
                error_code=direct_result.get("error_code", "") if not ok else "",
            )
            self._save_cms_tasks()
        if ok:
            return True, "115 直接磁力任务已提交，等待下载与 MP 整理"
        if unknown:
            logger.warning(
                "【TG115】磁力结果未知: position=%s/%s btih_prefix=%s decision=reconcile next_candidate_submitted=false",
                record.get("position", 0) if record else 0,
                record.get("candidate_total", 0) if record else 0,
                str(btih or "")[:12],
            )
            return True, "115 提交结果未知，正在按 BTIH 对账；不会提交下一个磁力"
        return False, message

    def _resolve_offline_target_cid(self) -> str:
        """Resolve the configured 115 path once; cloud download requires numeric cid."""
        target = str(self._p115_target or "0").strip()
        if target.isdigit():
            return target
        if not self._transfer:
            raise RuntimeError("115 目录模块未初始化")
        return str(self._transfer._get_or_create_cid(target))

    def _filter_resources(
            self, subscribe, mediainfo, torrents: List[TorrentInfo]
    ) -> Tuple[List[TorrentInfo], Optional[RuleCompatibilityDiagnostics]]:
        """复用 MP 内置过滤规则：先规则组，再 include/exclude/清晰度等参数。"""
        if not torrents:
            return [], None
        diagnostics = None
        if self._use_rule_groups:
            rule_groups = self._get_rule_groups(subscribe)
            if rule_groups:
                try:
                    native_matched = filter_with_offline_seed_override(
                        torrents,
                        lambda items: SubscribeChain().filter_torrents(
                            rule_groups=rule_groups,
                            torrent_list=items,
                            mediainfo=mediainfo,
                        ) or [],
                    )
                    # Only 115 shares use compatibility evaluation. Magnets keep the
                    # existing seeder override and all other native MP behavior.
                    share_candidates = [
                        item for item in torrents
                        if getattr(item, "_tg115_unavailable_rule_fields", None)
                    ]
                    compat_matched = []
                    if share_candidates:
                        snapshot = self._get_rule_engine_snapshot(rule_groups, mediainfo)
                        if snapshot:
                            groups, rules = snapshot
                            compat_matched, diagnostics = filter_offline_share_rules(
                                share_candidates, groups, rules, mediainfo
                            )
                            if diagnostics.matched_count:
                                logger.info(
                                    "【TG115】%s" % diagnostics.summary()
                                )
                        else:
                            # 规则定义读取失败时，115 分享不应被 native_matched 清空
                            logger.warn("【TG115】无法读取 MoviePilot 规则定义，115 分享跳过规则组过滤")
                            compat_matched = list(share_candidates)
                    allowed = {id(item) for item in native_matched}
                    allowed.update(id(item) for item in compat_matched)
                    torrents = [item for item in torrents if id(item) in allowed]
                except Exception as e:
                    logger.warn(f"【TG115】filter_torrents 异常，跳过规则组过滤: {e}")
        filter_params = self._get_filter_params(subscribe)
        if filter_params:
            torrents = [t for t in torrents if TorrentHelper.filter_torrent(t, filter_params)]
        return torrents, diagnostics

    def _enrich_share_metadata(self, torrents: List[TorrentInfo], max_probes: int = 10,
                               subscribe=None, mediainfo=None) -> None:
        """Append read-only 115 share names before MP rule/identity filtering."""
        if not self._transfer:
            return
        ok_ready, _ready_msg = self._transfer.is_ready()
        if not ok_ready:
            logger.info("【TG115】115 Cookie 不可用，跳过分享元数据探测")
            return
        probed = 0
        probe_candidates = order_identity_candidates(torrents, mediainfo, subscribe)
        for torrent in probe_candidates:
            if probed >= max_probes or not P115Transfer._is_115_share_url(torrent.page_url or ""):
                continue
            code, _ = P115Transfer._extract_payload(torrent.page_url or "")
            if not code:
                continue
            cached = self._share_metadata_cache.get(code) if self._share_metadata_cache else None
            if cached is None:
                if probed:
                    time.sleep(random.uniform(0.3, 0.6))
                ok, _message, names = self._transfer.inspect_share(
                    torrent.page_url or "", limit=32
                )
                probed += 1
                if ok:
                    cached = names
                else:
                    cached = []
                    logger.info(
                        "【TG115】115 分享元数据探测失败：%s",
                        _message,
                    )
                if self._share_metadata_cache:
                    self._share_metadata_cache.set(code, cached)
            if not cached:
                continue
            metadata = " ".join(str(name) for name in cached[:12])
            detected_seasons = sorted(parse_seasons(" ".join(str(name) for name in cached[:32])))
            if detected_seasons:
                metadata = "%s %s" % (
                    metadata,
                    " ".join(f"S{season:02d}" for season in detected_seasons),
                )
            torrent.description = f"{torrent.description or ''}\n{metadata}".strip()
            setattr(torrent, "_tg115_identity_title", clean_identity_title(
                metadata,
                getattr(torrent, "_tg115_source_title", ""),
                getattr(torrent, "_tg115_source_year", None),
                torrent.description or "",
            ))
            setattr(torrent, "_tg115_metadata_verified", True)
            # 检测 115 分享内是否包含中文字幕文件
            has_sub_file = has_chinese_subtitle_file(cached)
            setattr(torrent, "_tg115_has_chinese_sub_file", has_sub_file)
            logger.info(
                "【TG115】115 分享只读文件名已补充候选元数据，中文字幕文件=%s",
                "是" if has_sub_file else "未检测到",
            )

    @staticmethod
    def _get_rule_engine_snapshot(rule_groups: List[str], mediainfo) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """Read the running MP filter module without mutating its global rule set."""
        try:
            modules = SubscribeChain().modulemanager.get_running_modules("filter_torrents")
            for module in modules or []:
                helper = getattr(module, "rulehelper", None)
                definitions = getattr(module, "rule_set", None)
                if not helper or not isinstance(definitions, dict):
                    continue
                groups = helper.get_rule_group_by_media(
                    media=mediainfo, group_names=rule_groups
                )
                return list(groups or []), dict(definitions)
        except Exception as exc:
            logger.warn(f"【TG115】读取 MoviePilot 规则定义失败: {type(exc).__name__}")
        return None

    @staticmethod
    def _deduplicate_115_torrents(torrents: List[TorrentInfo]) -> List[TorrentInfo]:
        """按 115 share_code 去重，避免重复候选消耗媒体识别额度。"""
        seen = set()
        result = []
        for torrent in torrents:
            url = torrent.page_url or ""
            share_code, _ = P115Transfer._extract_payload(url)
            key = (share_code or url).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(torrent)
        return result

    @staticmethod
    def _get_rule_groups(subscribe) -> List[str]:
        if getattr(subscribe, "best_version", None):
            groups = subscribe.filter_groups or SystemConfigOper().get(
                SystemConfigKey.BestVersionFilterRuleGroups) or []
        else:
            groups = subscribe.filter_groups or SystemConfigOper().get(
                SystemConfigKey.SubscribeFilterRuleGroups) or []
        return list(groups or [])

    @staticmethod
    def _get_filter_params(subscribe) -> Dict[str, str]:
        return {k: v for k, v in {
            "include": subscribe.include, "exclude": subscribe.exclude,
            "quality": subscribe.quality, "resolution": subscribe.resolution,
            "effect": subscribe.effect,
        }.items() if v}

    @staticmethod
    def _source_notice(source_summary: str, torrent: TorrentInfo) -> str:
        summary = source_summary or "已完成来源汇总"
        return f"搜索命中：{summary}\n最终来源：{format_selected_source(torrent)}"

    def _finish_subscribe(
            self, subscribe, meta, mediainfo, torrent: TorrentInfo,
            transfer_msg: str, via_offline_magnet: bool = False,
            source_summary: str = "") -> bool:
        """转存成功后处理订阅，两种模式由 ``auto_finish`` 开关控制：

        ``auto_finish=True``（默认，不依赖 MP 整理 115）：
          - 电影：写历史 -> 删订阅 -> 发 SubscribeComplete -> 通知
          - 剧集：设 lack_episode=0 + state=P -> 发 SubscribeComplete -> 通知
          - 适合：不用 MP 整理 115 资源的用户，插件直接标记完成。

        ``auto_finish=False``（让 MP 整理 115 后自己完成）：
          - 电影/剧集统一：只设 state=P（+ 剧集 lack_episode=0），不删订阅、不写历史
          - MP 文件监控检测 115 目录新文件 -> 整理（刮削+入库）-> 写历史 -> 删订阅
          - 适合：用 MP 整理 115 资源的用户，MP 有完整整理历史。
        """
        try:
            oper = SubscribeOper()
            source_notice = self._source_notice(source_summary, torrent)
            classification = classify_resource(
                torrent,
                media_type="tv" if any(is_tv_media(value) for value in (
                    getattr(subscribe, "type", None),
                    getattr(mediainfo, "type", None),
                    getattr(meta, "type", None),
                )) else "movie",
                identity_status="confirmed",
                mp_rule_status="passed",
            )
            classification_notice = (
                f"资源类型：{classification['resource_type']}\n"
                f"分辨率：{classification['resolution']}\n"
                f"质量：{classification['quality']}\n"
                f"编码：{classification['video_codec']}\n"
                f"字幕：{classification['subtitle']}\n"
                f"动态范围：{classification['hdr']}"
            )
            logger.info("【TG115】最终资源分类: %s", format_resource_classification(classification))
            logger.info(
                "【TG115】最终资源来源: source=%s upstream_source=%s pan_type=%s title=%s",
                candidate_source(torrent), candidate_upstream_source(torrent),
                str(getattr(torrent, "_tg115_pan_type", "") or ""), torrent.title,
            )
            is_tv = any(is_tv_media(value) for value in (
                getattr(subscribe, "type", None),
                getattr(mediainfo, "type", None),
                getattr(meta, "type", None),
            ))

            if via_offline_magnet:
                oper.update(subscribe.id, {"state": "P"})
                logger.info(
                    f"【TG115】订阅 [{subscribe.name}] 已提交 115 磁力离线任务并暂停，"
                    "等待离线下载及 MoviePilot 整理"
                )
                if self._notify_success:
                    self._post_search_notification_once(
                        subscribe=subscribe,
                        outcome="submitted",
                        mtype=NotificationType.Subscribe,
                        title=subscription_notification_title(subscribe),
                        text=(
                            "结果：已通过 MoviePilot 规则与媒体 ID 确认，并提交 115 磁力下载。\n"
                            f"{source_notice}\n"
                            f"{classification_notice}\n"
                            "处理方式：插件内置 115 离线下载\n"
                            "后续：等待 115 下载和 MoviePilot 整理，当前不会标记订阅完成。\n"
                            f"资源：{torrent.title}\n{transfer_msg}"
                        ),
                    )
                return True

            # A successful 115 share receive only proves that the cloud copy
            # request completed.  It does not prove MP has seen, organized and
            # recorded the media.  Keep the subscription paused and let MP's
            # normal monitor/organizer own completion.
            if self._wait_for_mp_organize:
                oper.update(subscribe.id, {"state": "P"})
                logger.info(
                    "【TG115】订阅 [%s] 已完成 115 分享转存，等待 MoviePilot 整理确认",
                    subscribe.name,
                )
                if self._notify_success:
                    self._post_search_notification_once(
                        subscribe=subscribe,
                        outcome="pending_organize",
                        mtype=NotificationType.Subscribe,
                        title=subscription_notification_title(subscribe),
                        text=(
                            "结果：资源已通过规则与媒体身份确认，并已转存到 115。\n"
                            f"{source_notice}\n"
                            f"{classification_notice}\n"
                            "后续：等待 MoviePilot 监控、整理和订阅历史确认；当前不会标记订阅完成。"
                        ),
                    )
                return True

            raw_text = torrent.description or torrent.title or ""
            episode_info = self._parse_episode_info(raw_text) if is_tv else ""
            season_str = f"第 {subscribe.season or 1} 季" if subscribe.season else "当季"

            if self._auto_finish:
                # ===== 模式一：插件直接标记完成 =====
                if not is_tv:
                    # 电影：写历史 + 删订阅
                    oper.add_history(**subscribe.to_dict())
                    oper.delete(subscribe.id)
                    logger.info(f"【TG115】电影订阅 [{subscribe.name}] 已通过 TG+115 完成并标记完结")
                else:
                    # 剧集：设 lack_episode=0 + state=P（不删订阅）
                    try:
                        oper.update(subscribe.id, {
                            "lack_episode": 0,
                            "state": "P",
                        })
                        logger.info(f"【TG115】剧集订阅 [{subscribe.name}] {season_str} 已更新"
                                    f"（lack_episode=0, state=P）")
                    except Exception as e:
                        logger.warn(f"【TG115】更新剧集订阅失败（不影响转存）: {e}")
            else:
                # ===== 模式二：只阻断搜索，让 MP 整理后自己完成 =====
                update_payload = {"state": "P"}
                if is_tv:
                    update_payload["lack_episode"] = 0
                try:
                    oper.update(subscribe.id, update_payload)
                    logger.info(
                        f"【TG115】订阅 [{subscribe.name}] 已设 state=P 阻断搜索"
                        f"{'，lack_episode=0（剧集本季已齐）' if is_tv else '（电影）'}"
                        f"，等待 MP 整理 115 资源后自动标记完成"
                    )
                except Exception as e:
                    logger.warn(f"【TG115】更新订阅状态失败（不影响转存结果）: {e}")

            # 发送 SubscribeComplete 事件
            eventmanager.send_event(EventType.SubscribeComplete, {
                "subscribe_id": subscribe.id,
                "subscribe_info": subscribe.to_dict(),
                "mediainfo": mediainfo.to_dict() if hasattr(mediainfo, "to_dict") else {},
            })

            # 通知用户
            if self._notify_success:
                try:
                    if is_tv:
                        self._post_search_notification_once(
                            subscribe=subscribe,
                            outcome="transferred",
                            mtype=NotificationType.Subscribe,
                            title=subscription_notification_title(subscribe),
                            text=(
                                f"结果：已转存《{subscribe.name}》{season_str}资源（{episode_info}）。\n"
                                f"{source_notice}\n"
                            )
                                 + (f"资源: {torrent.title}\n{transfer_msg}" if self._auto_finish
                                    else f"已阻断 MP 搜索，等待系统整理 115 资源并刮削入库。\n"
                                         f"资源: {torrent.title}\n{transfer_msg}"),
                        )
                    else:
                        self._post_search_notification_once(
                            subscribe=subscribe,
                            outcome="transferred",
                            mtype=NotificationType.Subscribe,
                            title=subscription_notification_title(subscribe),
                            text=(
                                f"结果：已将《{subscribe.name}》转存至 115 网盘。\n"
                                f"{source_notice}\n"
                            )
                                 + (f"资源: {torrent.title}\n{transfer_msg}" if self._auto_finish
                                    else f"已阻断 MP 搜索，等待系统整理 115 资源并刮削入库。\n"
                                         f"资源: {torrent.title}\n{transfer_msg}"),
                        )
                except Exception:
                    pass

            return True

        except Exception as e:
            logger.error(f"【TG115】更新订阅状态异常（不影响 MP 默认流程）: {e}")
            return False

    @staticmethod
    def _parse_episode_info(text: str) -> str:
        """从 TG 消息文本中提取剧集集数信息。

        高兼容性正则，支持以下格式：
          - "EP01-08" / "E01-08" / "EP01~08" -> "EP01-08"
          - "更新至05集" / "更新至 5 集" -> "更新至05集"
          - "全12集" / "全 12 集" -> "全12集（完整）"
          - "第01-12集" / "第1-12集" -> "第01-12集"
          - "S01E01-E12" / "S01E01-12" -> "S01E01-E12"
          - "1-12集" / "01-12 集" -> "EP01-12"
          - 无匹配 -> "本季合集"
        """
        if not text:
            return "本季合集"

        # S01E01-E12 / S01E01-12
        m = _re.search(r'[Ss]\d{1,2}[Ee](\d{1,3})\s*[-~]\s*[Ee]?(\d{1,3})', text)
        if m:
            return f"EP{int(m.group(1)):02d}-{int(m.group(2)):02d}"

        # EP01-08 / E01-08 / EP01~08
        m = _re.search(r'[Ee][Pp]?(\d{1,3})\s*[-~]\s*(\d{1,3})', text)
        if m:
            return f"EP{int(m.group(1)):02d}-{int(m.group(2)):02d}"

        # 更新至05集 / 更新至 5 集
        m = _re.search(r'更新至\s*(\d{1,3})\s*集', text)
        if m:
            return f"更新至{int(m.group(1))}集"

        # 全12集 / 全 12 集
        m = _re.search(r'全\s*(\d{1,3})\s*集', text)
        if m:
            return f"全{int(m.group(1))}集（完整）"

        # 第01-12集 / 第1-12集
        m = _re.search(r'第\s*(\d{1,3})\s*[-~]\s*(\d{1,3})\s*集', text)
        if m:
            return f"第{int(m.group(1)):02d}-{int(m.group(2)):02d}集"

        # 1-12集 / 01-12 集
        m = _re.search(r'(?<![\d])(\d{1,3})\s*[-~]\s*(\d{1,3})\s*集', text)
        if m:
            return f"EP{int(m.group(1)):02d}-{int(m.group(2)):02d}"

        # 完结 / 全集
        if _re.search(r'完结|全集|全季', text):
            return "全集（完结）"

        return "本季合集"

    @staticmethod
    def _safe_share_label(torrent) -> str:
        """脱敏的 115 分享标签，用于日志。"""
        title = str(getattr(torrent, "title", "") or "未命名资源")
        if len(title) > 60:
            title = title[:60] + "…"
        return title

    @staticmethod
    def _parse_resource_meta(text: str) -> dict:
        """从资源标题解析展示元数据，供详情页卡片展示与排序。

        返回:
          - display_name: "片名 (年份)"（无年份则只片名）
          - meta: "完结 - S01E177  4K  WEB-DL" 风格的元信息行
          - is_complete: 是否完结（排序用）
          - episode_num: 最大集数（排序用，0 表示无集数信息）
        """
        t = (text or "").strip()
        if not t:
            return {"display_name": "", "meta": "", "is_complete": False, "episode_num": 0}

        # ---- 年份 ----
        ym = _re.search(r'[(（](\d{4})[)）]', t)
        year = ym.group(1) if ym else ""

        # ---- 名称：优先标签取值(TG消息)，否则扫描行找像片名的 ----
        qual = (r'4K|2160P|1080[PI]?|720P|480P|UHD|蓝光|原盘|REMUX|WEB-?DL|WEBRip|WEB-?Rip'
                r'|Blu-?Ray|BluRay|BD-?Rip|BR-?Rip|HDTV|PDTV|SATRip|DSR|DVD-?Rip|DVDScr'
                r'|HDCAM|\bCAM\b|HDTC|\bTC\b|HDTS|\bTS\b|H\.?26[45]|AVC|HEVC|x26[45]'
                r'|Dolby\s?Vision|DoVi|杜比|HDR10?\+?|国语|粤语|英语|日语|中字|简繁|特效|字幕'
                r'|完结|更新至|全集|全季|类型|无广告|正式版|抢先版|枪版|内封|外挂|双音')
        ep_pat = r'[Ss]\d{1,2}[Ee]\d{1,3}|[Ee][Pp]?\s?\d{1,3}\b|全\s*\d{1,3}\s*集|更新至\s*\d|第\s*\d{1,3}(?:[-~]\d{1,3})?\s*集'
        name = ""
        # 1. "名称：/资源名称：/片名：/剧名：value" 标签取值（TG 消息常见格式）
        for _lm in _re.finditer(
                r'(?:资源名称|片名|剧名|名称|电影|电视剧|动漫|动画)\s*[:：]\s*([^\n【】|]{1,60})', t):
            nv = _re.split(rf'(?:{qual})|(?:{ep_pat})', _lm.group(1), maxsplit=1)[0]
            nv = _re.sub(r'\s*[(（]\d{4}[)）]', '', nv).strip(' -–-·•|:：【】')
            if nv:
                name = nv
                break
        # 2. 启发式：扫描行，跳过头部词/纯符号/标签行；优先带标题特征(年份/集数/清晰度/【】)的行
        if not name:
            _headers = ('观影', '影视', '资源', '分享', '频道', '剧迷', '推荐', '福利',
                        '网盘', '影库', '片库', '分享群', '合集', '整理')
            _cands = []
            for _line in t.splitlines():
                ln = _re.sub(r'https?://\S+', '', _line).strip()
                if not ln or _re.fullmatch(r'[\W\s_]+', ln):
                    continue  # 空 / 纯符号(emoji 头部)
                if _re.match(r'^(?:集数|清晰度|大小|链接|提取码|状态|季数|年份|类型|格式|来源|分辨率|编码|备注)\s*[:：]', ln):
                    continue  # 其它字段标签行
                head = _re.sub(r'^[\s\W_]+', '', ln)
                _mm = _re.search(rf'(?:{qual})|【|(?:{ep_pat})', head)
                name_raw = head[:_mm.start()] if _mm else head
                name_raw = _re.sub(r'[━◀▶▉▔▂▃▅▆▇【】\[\]]', '', name_raw).strip(' -–-·•|:：')
                name_raw = _re.sub(r'\s*[(（]\d{4}[)）]', '', name_raw).strip(' -–-·•|:：')
                if not name_raw or not (_re.search(r'[一-鿿぀-ヿ]', name_raw) or _re.search(r'[A-Za-z]{3,}', name_raw)):
                    continue
                # 跳过纯头部词（如"观影""影视分享"等短头部）
                if len(name_raw) <= 8 and any(name_raw.startswith(w) for w in _headers):
                    continue
                _feat = bool(_re.search(r'[(（]\d{4}[)）]|[Ss]\d{1,2}[Ee]\d|全\s*\d{1,3}\s*集|更新至|【', ln))
                _cands.append((name_raw, _feat))
                if _feat:
                    name = name_raw
                    break
            if not name and _cands:
                name = _cands[0][0]
        # 3. 兜底：第一个【】内容
        if not name:
            bm = _re.search(r'【([^】]{1,60})】', t)
            if bm:
                name = _re.sub(r'\s*[(（]\d{4}[)）]', '', bm.group(1)).strip(' -–-·•|:：')

        # ---- 状态 + 集数（status 只标完结；ongoing 由 episode 表达，避免重复）----
        is_complete = bool(_re.search(r'完结|全集|全季', t))
        episode = ""
        episode_num = 0
        m = _re.search(r'[Ss]\d{1,2}[Ee](\d{1,3})\s*(?:[-~]\s*[Ee]?(\d{1,3}))?', t)
        if m:
            a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else a
            episode = _re.sub(r'\s+', '', m.group(0))
            episode_num = max(a, b)
        elif (m := _re.search(r'全\s*(\d{1,3})\s*集', t)):
            episode = _re.sub(r'\s+', '', m.group(0)); episode_num = int(m.group(1)); is_complete = True
        elif (m := _re.search(r'更新至\s*(\d{1,3})\s*集', t)):
            episode = _re.sub(r'\s+', '', m.group(0)); episode_num = int(m.group(1))
        elif (m := _re.search(r'(?:EP|E|第)(\d{1,3})\s*[-~]\s*(\d{1,3})', t, _re.IGNORECASE)):
            a = int(m.group(1)); b = int(m.group(2))
            episode = f"EP{a:02d}-{b:02d}"; episode_num = max(a, b)
        status = "完结" if is_complete else ""

        # ---- 清晰度（分辨率）----
        qm = _re.search(r'(4K|2160P|1080[PI]?|720P|480P|UHD)', t, _re.IGNORECASE)
        quality = qm.group(1).upper() if qm else ""
        if quality == "UHD":
            quality = "4K"

        # ---- 来源/发布类型（电影常见格式标识，全量匹配，去重）----
        source_tokens = []
        for pat, label in [
            (r'WEB-?DL', 'WEB-DL'), (r'WEBRip|WEB-?Rip', 'WEBRip'),
            (r'Blu-?Ray|BluRay|蓝光', 'BluRay'),
            (r'BD-?Rip', 'BDRip'), (r'BR-?Rip', 'BRRip'),
            (r'REMUX|原盘', 'REMUX'),
            (r'HDTV|PDTV|SATRip|DSR', 'HDTV'),
            (r'DVD-?Rip', 'DVDRip'), (r'DVDScr', 'DVDScr'),
            (r'HDCAM|\bCAM\b', 'CAM'), (r'HDTC|\bTC\b', 'TC'), (r'HDTS|\bTS\b', 'TS'),
        ]:
            if _re.search(pat, t, _re.IGNORECASE) and label not in source_tokens:
                source_tokens.append(label)
        source = " ".join(source_tokens)

        # ---- 编码 ----
        codec = ""
        cm = _re.search(r'(H\.?26[45]|x\.?26[45]|HEVC|AVC)', t, _re.IGNORECASE)
        if cm:
            c = cm.group(1).upper().replace('.', '')
            codec = {'X264': 'x264', 'X265': 'x265'}.get(c, c)

        # ---- HDR / 杜比视界 ----
        hdr = ""
        if _re.search(r'Dolby\s?Vision|DoVi|杜比视界|杜比', t, _re.IGNORECASE):
            hdr = "DV"
        elif _re.search(r'HDR10\+|HDR10', t, _re.IGNORECASE):
            hdr = "HDR10"
        elif _re.search(r'\bHDR\b', t, _re.IGNORECASE):
            hdr = "HDR"

        # ---- 组装 ----
        display_name = f"{name} ({year})" if name and year else (name or "")
        meta_head = " - ".join([p for p in [status, episode] if p])
        meta_tail = "  ".join([p for p in [quality, source, codec, hdr] if p])
        meta = "  ".join([x for x in [meta_head, meta_tail] if x])
        return {"display_name": display_name, "meta": meta,
                "is_complete": is_complete, "episode_num": episode_num}

    def _post_search_notification_once(
            self, subscribe, outcome: str, mtype, title: str, text: str) -> None:
        key = (
            str(outcome or ""),
            str(getattr(subscribe, "id", "") or ""),
            str(getattr(subscribe, "season", "") if getattr(subscribe, "season", None) is not None else ""),
        )
        if self._notification_cache and self._notification_cache.get(key):
            logger.info(
                f"【TG115】订阅 {getattr(subscribe, 'id', '')} 相同结果通知已合并"
            )
            return
        if self._notification_cache:
            self._notification_cache.set(key, True)
        self.post_message(mtype=mtype, title=title, text=text)

    def _send_fail_notify(
            self, subscribe, reason: str,
            source_report: Optional[SearchReport] = None,
            rejections: Optional[list] = None) -> None:
        if not self._notify_fail:
            return
        text_parts = [
            f"结果：未找到可安全自动处理的资源。\n",
            f"搜索命中：{source_report.text() if source_report else '已完成全部已启用来源'}\n",
            f"原因：{reason}。\n",
        ]
        if self._search_detail_notify and rejections:
            detail = format_rejection_detail(rejections)
            if detail:
                text_parts.append(f"{detail}\n")
        text_parts.append("后续：订阅已恢复，MoviePilot 可在后续订阅搜索中继续处理。")
        try:
            self._post_search_notification_once(
                subscribe=subscribe,
                outcome="missed",
                mtype=NotificationType.Subscribe,
                title=subscription_notification_title(subscribe),
                text="".join(text_parts),
            )
        except Exception:
            pass

    # ============================ REST API ============================
    def __get_config_api(self):
        """GET /config：返回当前配置（供自定义前端 Config.vue 读取）。"""
        from starlette.responses import JSONResponse
        stored = self.get_data(CONFIG_KEY) or {}
        config = {**self._default_config(), **stored} if isinstance(stored, dict) \
            else self._default_config()
        config["tg_channels"] = self._parse_channels(config.get("tg_channels"))
        for key in ("cms_url", "cms_token", "cms_timeout_hours", "magnet_download_mode"):
            config.pop(key, None)
        ck = config.get("p115_cookie", "") if isinstance(config, dict) else ""
        logger.info(f"【TG115】/config/get p115_cookie_len={len(ck or '')} valid={bool(_pick_uid_cid_seid(ck or ''))}")
        return JSONResponse(config)

    def __save_config_api(self, config: dict = Body(default=None)):
        """POST /config/save：保存配置并即时生效。

        使用 FastAPI ``Body`` 显式声明 ``config`` 取自请求体（与官方插件 agenttokens
        的 save_config_api 一致），避免 ``Any`` / ``**kwargs`` 导致 FastAPI 422。
        """
        from starlette.responses import JSONResponse
        if not isinstance(config, dict) or not config:
            return JSONResponse({"success": False, "message": "配置数据无效"}, status_code=400)
        # 兼容 {"config": {...}} 包裹
        if isinstance(config.get("config"), dict) and len(config) == 1:
            config = config["config"]
        try:
            stored = self.get_data(CONFIG_KEY) or {}
            safe_config = dict(stored) if isinstance(stored, dict) else {}
            safe_config.update(config)
            for key in ("cms_url", "cms_token", "cms_timeout_hours", "magnet_download_mode"):
                safe_config.pop(key, None)
            safe_config["magnet_download_mode"] = "direct_115"
            self.save_data(CONFIG_KEY, safe_config)
            self.init_plugin(safe_config)
            return JSONResponse({"success": True, "message": "配置已保存并生效"})
        except Exception as e:
            logger.error(f"【TG115】保存配置失败: {e}")
            return JSONResponse({"success": False, "message": f"保存失败: {e}"}, status_code=500)

    def __check_channel_api(self, index: int = -1):
        """GET /check_channel?index=N：检查指定 TG 频道连通性。"""
        from starlette.responses import JSONResponse
        try:
            index = int(index)
        except Exception:
            index = -1
        channels = self._tg_channels or []
        if index < 0 or index >= len(channels):
            return JSONResponse({"success": False, "message": "频道序号无效"})
        ch = channels[index]
        if not self._scraper:
            return JSONResponse({"success": False, "message": "未配置任何频道"})
        ok, msg = self._scraper.check_channel(ch["id"])
        return JSONResponse({"success": ok, "message": f"[{ch.get('name') or ch['id']}] {msg}"})

    def __check_all_api(self):
        """GET /check_all：检查所有 TG 频道连通性。"""
        from starlette.responses import JSONResponse
        channels = self._tg_channels or []
        if not channels:
            return JSONResponse({"success": False, "message": "未配置任何频道"})
        if not self._scraper:
            return JSONResponse({"success": False, "message": "未配置任何频道"})
        results = []
        for ch in channels:
            ok, msg = self._scraper.check_channel(ch["id"])
            results.append({
                "name": ch.get("name") or ch["id"], "id": ch["id"],
                "enabled": ch.get("enabled", True), "ok": ok, "message": msg,
            })
        ok_count = sum(1 for r in results if r["ok"])
        return JSONResponse({
            "success": True,
            "message": f"检查完成：{ok_count}/{len(results)} 个频道连通正常",
            "results": results,
        })

    # ---------------------------- 115 扫码登录 API ----------------------------
    def __qrcode_get_api(self, app: str = "web"):
        """GET /qrcode/get?app=...：获取 115 登录二维码及会话凭证。

        ``app`` 为登录端类型（web/tv/ipad/android/ios/alipaymini 等），决定最终 Cookie
        的设备归属。返回二维码图片（data URL，规避 HTTPS 混合内容）及 uid/time/sign。
        """
        from starlette.responses import JSONResponse
        try:
            token = _qr_token()
            data = token.get("data") if isinstance(token, dict) else None
            data = data or {}
            uid = str(data.get("uid", "") or "")
            if not uid:
                msg = token.get("message", "") if isinstance(token, dict) else ""
                return JSONResponse({"success": False, "message": f"115 未返回 uid: {msg}"}, status_code=502)
            return JSONResponse({
                "success": True,
                "uid": uid,
                "time": data.get("time"),
                "sign": data.get("sign"),
                "app": _qr_normalize_app(app),
                "qrcode_url": _qr_image_data_url(uid),
            })
        except Exception as e:
            logger.error(f"【TG115】获取 115 二维码失败: {e}")
            return JSONResponse({"success": False, "message": f"获取二维码失败: {e}"}, status_code=500)

    def __qrcode_status_api(self, uid: str = "", time: str = "", sign: str = "", app: str = "web"):
        """GET /qrcode/status?uid=&time=&sign=&app=：轮询扫码状态，成功则提取并保存 Cookie。

        status: 0=等待扫码 1=已扫描待确认 2=已确认登录 -1=已过期 -2=已取消 -99=异常。
        status==2 时调 ``_qr_result`` 取含 UID/CID/SEID 的 Cookie，写回配置并 ``init_plugin``
        即时生效（重建 P115Transfer）。
        """
        from starlette.responses import JSONResponse
        if not uid or not sign:
            return JSONResponse({"status": -99, "msg": "缺少 uid/sign", "login_ok": False}, status_code=400)
        _msg_map = {0: "等待扫码", 1: "已扫描，请在手机上确认", 2: "已确认登录",
                    -1: "二维码已过期", -2: "已取消", -99: "异常"}
        # 1) 先直接尝试取 Cookie。115 在用户手机端确认后，qrcode_result 即可拿到含
        #    UID/CID/SEID 的 Cookie；这样不依赖 status 响应里可能缺失的 status 字段，
        #    避免出现「已确认但前端一直等待」的问题。未确认时返回空，无副作用。
        try:
            raw, set_cookie = _qr_result(uid, app)
        except Exception as e:
            raw, set_cookie = "", ""
            logger.warn(f"【TG115】qrcode_result 请求异常: {e}")
        # Never log the QR response body or Set-Cookie values.  Only record
        # whether the expected credential fields were present.
        logger.info(
            "【TG115】qrcode_result app=%s credential_fields=%s",
            app, bool(_pick_uid_cid_seid(raw + "\n" + set_cookie)),
        )
        cookie_str = _pick_uid_cid_seid(raw + "\n" + set_cookie)
        if cookie_str:
            cfg = self.get_data(CONFIG_KEY) or self._default_config()
            cfg["p115_cookie"] = cookie_str
            cfg["p115_app"] = _qr_normalize_app(app)
            self.save_data(CONFIG_KEY, cfg)
            self.init_plugin(cfg)
            return JSONResponse({"status": 2, "msg": "扫码登录成功，Cookie 已保存并生效", "login_ok": True})
        # 注意：「老乡验证失败」(errno 40101017) 在未扫码时也会返回，故不据此中断轮询；
        # 若手机端确认后仍持续返回该错误，说明 115 异地风控拒绝下发 Cookie，需改用 Cookie
        # 登录。具体见 MP 日志里 qrcode_result 的原始响应。
        # 2) 未确认：查状态用于展示（等待/已扫描/过期）
        try:
            resp = _qr_status(uid, str(time or ""), sign)
            data = resp.get("data") if isinstance(resp, dict) else None
            data = data or {}
            status = data.get("status")
            if status is None:
                status = resp.get("status") if isinstance(resp, dict) else None
            if status is None:
                status = 0 if (isinstance(resp, dict) and resp.get("state") == 1) else -1
            status = int(status)
            msg = (data.get("msg") or (resp.get("message") if isinstance(resp, dict) else "")
                   or _msg_map.get(status, ""))
            return JSONResponse({"status": status, "msg": msg, "login_ok": False})
        except Exception:
            # 状态接口长轮询超时（无事件），视为等待
            return JSONResponse({"status": 0, "msg": "等待扫码", "login_ok": False})

    # ---------------------------- 手动转存 / 手动搜索 API ----------------------------
    def __manual_subscriptions_api(self):
        """Return only non-secret subscription labels for manual verification."""
        from starlette.responses import JSONResponse
        items = []
        for subscribe in SubscribeOper().list() or []:
            state = str(getattr(subscribe, "state", "N") or "N").upper()
            if state not in {"N", "R"}:
                continue
            season = getattr(subscribe, "season", None)
            label = str(getattr(subscribe, "name", "") or "未命名订阅")
            year = getattr(subscribe, "year", None)
            if year:
                label += f"（{year}）"
            if season is not None:
                try:
                    label += f" S{int(season):02d}"
                except (TypeError, ValueError):
                    pass
            items.append({"id": getattr(subscribe, "id", None), "label": label})
        return JSONResponse({"success": True, "items": items})

    def __manual_process_api(self, payload: dict = Body(default=None)):
        """Verify one selected result with the subscription pipeline before writes."""
        from starlette.responses import JSONResponse
        payload = payload if isinstance(payload, dict) else {}
        if payload.get("confirm") is not True:
            return JSONResponse(
                {"success": False, "message": "真实处理必须显式确认 confirm=true"},
                status_code=400,
            )
        try:
            subscribe_id = int(payload.get("subscribe_id"))
        except (TypeError, ValueError):
            return JSONResponse(
                {"success": False, "message": "请先选择用于身份确认的订阅"},
                status_code=400,
            )
        subscribe = SubscribeOper().get(subscribe_id)
        if not subscribe:
            return JSONResponse({"success": False, "message": "订阅不存在"}, status_code=404)
        state = str(getattr(subscribe, "state", "N") or "N").upper()
        if state not in {"N", "R"}:
            return JSONResponse(
                {"success": False, "message": "订阅当前状态不允许手动处理"},
                status_code=409,
            )

        candidate = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
        url = str(candidate.get("share_url") or "").strip()
        title = str(candidate.get("title") or "").strip()
        description = str(candidate.get("text") or title).strip()
        pan_type = str(candidate.get("pan_type") or "").strip().lower()
        source = str(candidate.get("source") or "manual").strip().lower()
        if not url or not title or pan_type not in {"115", "magnet"}:
            return JSONResponse(
                {"success": False, "message": "候选资源字段不完整或类型不支持"},
                status_code=400,
            )

        try:
            meta = build_subscribe_meta(subscribe)
            mediainfo = self._recognize(subscribe, meta)
            if not mediainfo:
                return JSONResponse(
                    {"success": False, "message": "MoviePilot 无法识别目标订阅"},
                    status_code=422,
                )
            hit = SiteHit(
                share_url=url,
                receive_code=str(candidate.get("receive_code") or "").strip(),
                resource_title=title,
                text=description[:1000],
                pan_type=pan_type,
                source_title=str(getattr(subscribe, "name", "") or ""),
                year=getattr(subscribe, "year", None),
                channel_name="手动搜索",
            )
            setattr(hit, "_tg115_source", source if source in {"tg", "site", "pansou", "juying"} else "manual")
            torrents = self._build_torrents([hit])
            self._enrich_share_metadata(torrents, subscribe=subscribe, mediainfo=mediainfo)
            target = getattr(subscribe, "season", None)
            if target is not None:
                torrents = [item for item in torrents if supports_target_season(item, int(target))]
            matched, diagnostics = self._filter_resources(subscribe, mediainfo, torrents)
            if not matched:
                reason = diagnostics.summary() if diagnostics else "候选未通过 MoviePilot 规则"
                return JSONResponse({"success": False, "message": reason}, status_code=422)
            torrent = matched[0]
            identity = confirm_candidate_identity(
                subscribe=subscribe,
                target_media=mediainfo,
                torrent=torrent,
                recognize_candidate=self._recognize_candidate,
            )
            if not identity.confirmed:
                return JSONResponse(
                    {"success": False, "message": identity.reason or "候选身份确认失败"},
                    status_code=422,
                )
            if is_magnet_url(torrent.page_url or ""):
                ok, message = self._submit_magnet_to_115(torrent, subscribe=subscribe)
                via_magnet = True
            else:
                ok, message, _data = self._transfer.transfer(
                    torrent.page_url or "", self._p115_target
                ) if self._transfer else (False, "115 转存模块未初始化", {})
                via_magnet = False
            if not ok:
                return JSONResponse({"success": False, "message": message}, status_code=502)
            self._finish_subscribe(
                subscribe, meta, mediainfo, torrent, message,
                via_offline_magnet=via_magnet,
                source_summary="手动搜索（已通过 MoviePilot 规则与媒体身份确认）",
            )
            logger.info(
                "【TG115】手动候选已通过验证并提交 subscribe_id=%s source=%s type=%s",
                subscribe_id, source, pan_type,
            )
            return JSONResponse({
                "success": True,
                "message": "候选已验证并提交，等待 115 与 MoviePilot 整理确认",
                "status": "pending_organize",
            })
        except Exception as exc:
            logger.warning(
                "【TG115】手动候选处理失败 subscribe_id=%s type=%s",
                subscribe_id, type(exc).__name__,
            )
            return JSONResponse(
                {"success": False, "message": "手动候选处理失败，请检查安全分类日志"},
                status_code=500,
            )

    def __transfer_api(self, share_url: str = "", target: str = ""):
        """GET /transfer?share_url=...&target=...：手动转存 115 分享链接到指定目录。

        ``target`` 留空则用配置中的默认转存目录（``p115_target``）；可填路径（如 /电影）
        或数字 cid。复用已有的 ``P115Transfer.transfer``（httpx 直连 share_receive）。
        """
        from starlette.responses import JSONResponse
        share_url = (share_url or "").strip()
        if not share_url:
            return JSONResponse({"success": False, "message": "请输入 115 分享链接"}, status_code=400)
        if not self._transfer or not self._p115_cookie:
            return JSONResponse({"success": False, "message": "未配置 115 Cookie，请先扫码登录"}, status_code=400)
        target_path = (target or "").strip() or self._p115_target
        try:
            ok, msg, data = self._transfer.transfer(share_url, target_path)
            logger.info("【TG115】手动 115 转存完成 ok=%s", ok)
            return JSONResponse({"success": ok, "message": msg})
        except Exception as e:
            logger.error("【TG115】手动转存异常 type=%s", type(e).__name__)
            return JSONResponse({"success": False, "message": "转存失败，请检查安全分类日志"}, status_code=500)

    def __magnet_offline_api(self, payload: dict = Body(default=None)):
        """Always return JSON, including unexpected direct/CMS client errors."""
        from starlette.responses import JSONResponse
        try:
            return self.__magnet_offline_api_impl(payload)
        except Exception as exc:
            logger.error(
                "【TG115】手动磁力离线异常 type=%s",
                type(exc).__name__,
            )
            return JSONResponse(
                {"success": False, "message": "离线请求处理失败，请检查插件日志"},
                status_code=500,
            )

    def __magnet_offline_api_impl(self, payload: dict = Body(default=None)):
        """POST /magnet/offline：用户手动确认后提交插件内置 115 磁力离线任务。"""
        from starlette.responses import JSONResponse
        payload = payload if isinstance(payload, dict) else {}
        magnet = str(payload.get("magnet") or payload.get("url") or "").strip()
        title = str(payload.get("title") or "未命名资源").strip()
        if not is_magnet_url(magnet):
            return JSONResponse(
                {"success": False, "message": "磁力链接无效"}, status_code=400
            )
        if not btih_from_magnet(magnet):
            return JSONResponse(
                {"success": False, "message": "磁力链接缺少有效 BTIH"}, status_code=400
            )
        if not self._offline_client:
            return JSONResponse({"success": False, "message": "未配置可用的插件内置 115 磁力离线"}, status_code=400)
        btih = btih_from_magnet(magnet)
        record = None
        if self._cms_tasks and btih:
            record, created = self._cms_tasks.reserve(
                magnet=magnet, title=title, status="waiting", source="115_direct",
            )
            if not created:
                return JSONResponse({
                    "success": True,
                    "message": "相同 BTIH 的 115 磁力任务已存在，未重复提交",
                })
        ok, message = False, "未提交"
        direct: Dict[str, Any] = {}
        target_cid = ""
        try:
            target_cid = self._resolve_offline_target_cid()
        except Exception as exc:
            direct = {"success": False, "message": f"115 目标目录不可用: {exc}"}
        else:
            direct = self._offline_client.submit_magnet(magnet, target_cid)
        ok, message = bool(direct.get("success")), str(direct.get("message") or "115 直连提交失败")
        if ok and self._cms_tasks and record:
            self._cms_tasks.update(record["btih"], "submitted", task_id=direct.get("task_id") or btih, source="115_direct", target_cid=target_cid)
        if self._cms_tasks and record:
            error_code = ""
            if not ok and direct:
                error_code = str(direct.get("error_code") or "")
            self._cms_tasks.update(
                record["btih"], "submitted" if ok else "failed",
                "" if ok else message,
                error_code=error_code,
            )
            self._save_cms_tasks()
        logger.info(f"【TG115】手动提交 115 磁力任务 [{title}]: ok={ok}")
        return JSONResponse({"success": ok, "message": message})

    def __check_115_offline_api(self):
        """GET /check_115_offline: read-only sign/task-list capability probe."""
        from starlette.responses import JSONResponse
        if not self._offline_client:
            return JSONResponse({"success": False, "message": "未配置 115 Cookie"}, status_code=400)
        return JSONResponse(self._offline_client.probe_capabilities())

    def __runtime_status_api(self):
        """GET /runtime/status: return non-secret scheduler and CMS task state."""
        from starlette.responses import JSONResponse
        self._reconcile_cms_tasks()
        scheduler = self._coordinator.status() if self._coordinator else {
            "running": False, "last_run": "", "next_run": "",
            "scanned_count": 0, "queue_size": 0, "running_subscribe_id": None,
        }
        return JSONResponse({
            "success": True,
            "scheduler": scheduler,
            "recognition": self._recognition_gate.status() if self._recognition_gate else {
                "waiting": 0, "active": 0, "max_active": 0,
                "last_wait_seconds": 0, "retries": 0,
                "identity_unavailable": 0, "stopping": True,
            },
            "sources": self._source_breaker.snapshot() if self._source_breaker else {},
            "tg": {
                "enabled": bool(self._tg_search_enabled),
                "configured_channels": len(self._tg_channels),
                "enabled_channels": sum(1 for channel in self._tg_channels if channel.get("enabled", True)),
                "status": "disabled" if not self._tg_search_enabled else "enabled" if any(channel.get("enabled", True) for channel in self._tg_channels) else "empty",
            },
            "pansou": {
                "enabled": bool(self._pansou_client),
                "last_request": getattr(self._pansou_client, "last_request_at", "") if self._pansou_client else "",
                "last_success": getattr(self._pansou_client, "last_success_at", "") if self._pansou_client else "",
                "last_error": getattr(self._pansou_client, "last_error", "") if self._pansou_client else "",
                "result_count": getattr(self._pansou_client, "last_result_count", 0) if self._pansou_client else 0,
                "type_counts": dict(getattr(self._pansou_client, "type_counts", {}) or {}) if self._pansou_client else {},
                "cache_hits": self._pansou_cache_hits,
                "deduplicated": self._pansou_dedup_count,
                "rule_passed": self._pansou_rule_passed,
                "identity_checked": self._pansou_identity_checked,
                "safe_candidates": self._pansou_safe_candidates,
            },
            "tasks": self._cms_tasks.public_records() if self._cms_tasks else [],
            "timeline": self._timeline.list(limit=10) if self._timeline else {"total": 0, "items": []},
            "source_health": self._source_health.snapshot(self._source_breaker.snapshot() if self._source_breaker else {}) if self._source_health else {},
        })

    def __timeline_api(self, status: str = "all", offset: int = 0, limit: int = 30):
        from starlette.responses import JSONResponse
        if not self._timeline:
            return JSONResponse({"success": True, "data": {"total": 0, "items": []}})
        return JSONResponse({"success": True, "data": self._timeline.list(str(status or "all"), int(offset or 0), int(limit or 30))})

    def __source_health_api(self):
        from starlette.responses import JSONResponse
        breaker = self._source_breaker.snapshot() if self._source_breaker else {}
        return JSONResponse({"success": True, "data": self._source_health.snapshot(breaker) if self._source_health else {}})

    def __clear_timeline_api(self, payload: dict = Body(default=None)):
        from starlette.responses import JSONResponse
        if not isinstance(payload, dict) or payload.get("confirm") is not True:
            return JSONResponse({"success": False, "message": "请显式确认仅清除本地终态诊断记录"}, status_code=400)
        try:
            count = self._timeline.clear_terminal() if self._timeline else 0
            self._save_diagnostics()
            return JSONResponse({"success": True, "message": f"已清除 {count} 条本地终态诊断记录"})
        except RuntimeError as exc:
            return JSONResponse({"success": False, "message": str(exc)}, status_code=409)

    def __subscription_dry_run_api(self, payload: dict = Body(default=None)):
        """POST /subscription/dry-run: execute the shared evaluator with zero writes."""
        from starlette.responses import JSONResponse
        payload = payload if isinstance(payload, dict) else {}
        try:
            subscribe_id = int(payload.get("subscribe_id"))
        except (TypeError, ValueError):
            return JSONResponse({"success": False, "message": "请输入有效的订阅 ID"}, status_code=400)
        subscribe = SubscribeOper().get(subscribe_id)
        if not subscribe:
            return JSONResponse({"success": False, "message": "订阅不存在"}, status_code=404)
        try:
            evaluation = self._evaluate_subscription_candidates(subscribe)
            return JSONResponse({
                "success": True,
                "dry_run": True,
                "message": "只读验证完成：未转存、未提交磁力、未调用 CMS、未修改订阅或任务账本",
                "result": self._dry_run_summary(subscribe, evaluation),
            })
        except Exception as exc:
            logger.warning("【TG115】订阅干跑失败 subscribe_id=%s type=%s", subscribe_id, type(exc).__name__)
            return JSONResponse({"success": False, "message": "只读验证失败，请检查安全分类日志"}, status_code=500)

    def __subscription_process_api(self, payload: dict = Body(default=None)):
        """POST /subscription/process: explicitly enqueue one real subscription workflow."""
        from starlette.responses import JSONResponse
        payload = payload if isinstance(payload, dict) else {}
        if payload.get("confirm") is not True:
            return JSONResponse(
                {"success": False, "message": "正式处理必须显式确认 confirm=true"},
                status_code=400,
            )
        try:
            subscribe_id = int(payload.get("subscribe_id"))
        except (TypeError, ValueError):
            return JSONResponse({"success": False, "message": "请输入有效的订阅 ID"}, status_code=400)
        if not self._enabled or not self._coordinator:
            return JSONResponse({"success": False, "message": "插件未启用或处理队列不可用"}, status_code=409)
        subscribe = SubscribeOper().get(subscribe_id)
        if not subscribe:
            return JSONResponse({"success": False, "message": "订阅不存在"}, status_code=404)
        original_state = str(getattr(subscribe, "state", "N") or "N").upper()
        if original_state not in {"N", "R"}:
            return JSONResponse({"success": False, "message": "订阅当前状态不允许正式处理"}, status_code=409)
        with self._lock:
            self._forced_process_states[subscribe_id] = original_state
        if not self._coordinator.enqueue_subscription(subscribe_id, priority=-5, trigger="manual"):
            with self._lock:
                self._forced_process_states.pop(subscribe_id, None)
            return JSONResponse({"success": False, "message": "订阅已在队列中或队列不可用"}, status_code=409)
        logger.info("【TG115】已确认正式处理订阅 subscribe_id=%s", subscribe_id)
        return JSONResponse({"success": True, "message": "订阅已进入正式处理队列"}, status_code=202)

    def __retry_cms_task_api(self, payload: dict = Body(default=None)):
        """POST /tasks/retry: restart direct task or restore CMS subscription."""
        from starlette.responses import JSONResponse
        payload = payload if isinstance(payload, dict) else {}
        btih = str(payload.get("btih") or "").strip().lower()
        record = self._cms_tasks.latest(btih) if self._cms_tasks else None
        if not record:
            return JSONResponse({"success": False, "message": "未找到 CMS 任务"}, status_code=404)
        if record.get("status") in ("waiting", "downloading", "pending_organize"):
            return JSONResponse({"success": False, "message": "任务仍在处理中，无需重试"}, status_code=409)
        if record.get("source") == "115_direct" and record.get("task_id") and self._offline_client:
            retry_count = self._safe_int(record.get("retry_count"), 0)
            if retry_count >= self._offline_max_retries:
                return JSONResponse({"success": False, "message": "已达到 115 任务最大重试次数"}, status_code=409)
            result = self._offline_client.retry_task(record["task_id"])
            if result.get("success"):
                self._cms_tasks.update(
                    btih, "submitted", error_message="", error_code="",
                    retry_count=retry_count + 1,
                )
                sid = record.get("subscribe_id")
                if sid and SubscribeOper().get(int(sid)):
                    SubscribeOper().update(int(sid), {"state": "P"})
                self._save_cms_tasks()
            return JSONResponse({
                "success": bool(result.get("success")),
                "message": result.get("message") or "115 任务重试失败",
            })
        sid = record.get("subscribe_id")
        if sid and SubscribeOper().get(int(sid)):
            SubscribeOper().update(int(sid), {"state": "N"})
        self._cms_tasks.update(btih, "waiting", "已恢复订阅，下一轮重新搜索候选磁力或 115 分享")
        self._save_cms_tasks()
        logger.info(f"【TG115】任务重试已恢复订阅 btih={btih[:12]}...")
        return JSONResponse({"success": True, "message": "订阅已恢复，下一轮将重新搜索并按当前离线策略提交"})

    def __clear_offline_tasks_api(self, payload: dict = Body(default=None)):
        """POST /tasks/clear: clear ledger records without losing active tracking."""
        from starlette.responses import JSONResponse
        if not has_explicit_clear_confirmation(payload):
            return JSONResponse({
                "success": False,
                "message": "请在确认对话框中明确确认后再清除任务记录",
                "cleared": 0,
            }, status_code=400)
        if not self._cms_tasks:
            return JSONResponse({"success": True, "message": "任务记录已为空", "cleared": 0})
        cleared, active = self._cms_tasks.clear_if_idle()
        if active:
            return JSONResponse({
                "success": False,
                "message": f"仍有 {active} 个任务处理中，完成或取消后才能清除记录",
                "cleared": 0,
            }, status_code=409)
        self._save_cms_tasks()
        logger.info(f"【TG115】已清除磁力下载任务账本记录 {cleared} 条")
        return JSONResponse({
            "success": True,
            "message": f"已清除 {cleared} 条磁力下载任务记录",
            "cleared": cleared,
        })

    def __cancel_offline_task_api(self, payload: dict = Body(default=None)):
        """POST /tasks/cancel: cancel a direct 115 task and restore subscription."""
        from starlette.responses import JSONResponse
        if not self._offline_allow_cancel:
            return JSONResponse({"success": False, "message": "配置未允许手动取消任务"}, status_code=403)
        payload = payload if isinstance(payload, dict) else {}
        btih = str(payload.get("btih") or "").strip().lower()
        record = self._cms_tasks.latest(btih) if self._cms_tasks else None
        if not record or record.get("source") != "115_direct":
            return JSONResponse({"success": False, "message": "未找到 115 直接任务"}, status_code=404)
        if record.get("status") not in {"submitted", "downloading", "pending_organize"}:
            return JSONResponse({"success": False, "message": "当前状态不能取消"}, status_code=409)
        if not self._offline_client:
            return JSONResponse({"success": False, "message": "115 离线客户端未初始化"}, status_code=400)
        result = self._offline_client.cancel_task(record.get("task_id") or btih)
        if result.get("success"):
            self._cms_tasks.update(btih, "cancelled", error_message="用户手动取消")
            self._offline_client.forget_task(btih)
            sid = record.get("subscribe_id")
            if sid and SubscribeOper().get(int(sid)):
                SubscribeOper().update(int(sid), {"state": "N"})
            self._save_cms_tasks()
        return JSONResponse({"success": bool(result.get("success")), "message": result.get("message") or "取消失败"})

    def __search_api(self, keyword: str = "", offset: int = 0, source: str = "all"):
        """GET /search?keyword=...&offset=N&source=all|tg|site|pansou|juying：手动搜索。

        source：all=全部 / tg=TG频道 / site=观影 / pansou=PanSou / juying=聚影。
        返回全部网盘类型（115/夸克/百度/阿里/迅雷…/磁力），前端按类型展示；
        115 分享可直接转存，磁力可通过 CMS 离线到 115。
        offset 用于观影翻页（按作品分批，每批 3 部）；TG 仅在首批(offset=0)搜索一次。
        返回 has_more 标记是否还有更多观影作品可翻页；warning 携带 app_auth 失效等提示。
        """
        from starlette.responses import JSONResponse
        from uuid import uuid4
        request_id = uuid4().hex[:12]

        def _response(success: bool, message: str, status_code: int = 200, **extra):
            """Keep the manual-search response safe and structurally stable."""
            payload = {
                "success": success,
                "message": message,
                "items": [],
                "results": [],
                "source_stats": {},
                "source_status": {},
                "request_id": request_id,
            }
            payload.update(extra)
            return JSONResponse(payload, status_code=status_code)

        keyword = (keyword or "").strip()
        if not keyword:
            return _response(False, "请输入搜索关键字", status_code=400)
        if ((not self._scraper or not self._tg_channels)
                and not self._site_scraper and not self._pansou_client and not self._juying_api):
            return _response(False, "未配置任何搜索源（TG、观影、PanSou 或聚影）", status_code=400)
        try:
            offset = int(offset or 0)
        except Exception:
            offset = 0
        # 从关键字分离年份（如"法警小队（2026）"->"法警小队"+2026）：观影按年份精确过滤，
        # 去掉年份让站点能搜到（带年份会搜不到、返回模糊匹配）
        _y = _re.search(r'[(（](\d{4})[)）]', keyword)
        manual_year = int(_y.group(1)) if _y else None
        search_kw = _re.sub(r'\s*[(（]\d{4}[)）]', '', keyword).strip() or keyword

        src = (source or "all").lower()
        if src not in {"all", "tg", "site", "pansou", "juying"}:
            return _response(False, "不支持的搜索来源", status_code=400)
        cooled_sources = []
        source_status = {}

        def _allowed(source_name: str) -> bool:
            allowed, remaining = self._source_breaker.allow(source_name) \
                if self._source_breaker else (True, 0)
            if not allowed:
                cooled_sources.append(f"{source_name} 冷却中（{remaining}秒）")
                source_status[source_name] = {"status": "cooldown", "message": f"冷却中（{remaining}秒）"}
            return allowed

        def _record_source(source_name: str, client, count: int = 0):
            status = getattr(client, "last_error_status", None)
            error = str(getattr(client, "last_error", "") or "")
            if status in (401, 403, 429) or error:
                category = f"HTTP {status}" if status else (error or "请求失败")
                source_status[source_name] = {
                    "status": "partial_success" if count else "error",
                    "message": f"已返回 {count} 条，{category}" if count else category,
                    "count": count,
                }
                if self._source_breaker:
                    self._source_breaker.failure(source_name, category)
            else:
                source_status[source_name] = {"status": "success", "message": f"返回 {count} 条", "count": count}
                if self._source_breaker:
                    self._source_breaker.success(source_name)

        def _source_error(source_name: str, exc: Exception):
            message = "请求超时" if "timeout" in type(exc).__name__.lower() else "请求失败"
            source_status[source_name] = {"status": "error", "message": message, "count": 0}
            if self._source_breaker:
                self._source_breaker.failure(source_name, message)

        def _do_search():
            hits = []
            has_more = False
            jobs = {}
            clients = {}
            if src in ("all", "tg") and self._tg_search_enabled and self._scraper and offset == 0 and _allowed("tg"):
                jobs["tg"] = lambda: (self._scraper.search(search_kw) or [], False)
                clients["tg"] = self._scraper
            elif src in ("all", "tg"):
                source_status["tg"] = {
                    "status": "disabled" if not self._tg_search_enabled else "empty",
                    "message": "TG 搜索已关闭" if not self._tg_search_enabled else "没有启用频道",
                    "count": 0,
                }
            if src in ("all", "site") and self._site_scraper and _allowed("site"):
                jobs["site"] = lambda: self._site_scraper.search(
                    search_kw, year=manual_year, offset=offset, count=3)
                clients["site"] = self._site_scraper
            if src in ("all", "pansou") and self._pansou_client and _allowed("pansou"):
                jobs["pansou"] = lambda: (
                    self._pansou_client.search(
                        search_kw, year=manual_year, refresh=self._pansou_refresh,
                        cloud_types=(), request_timeout=self._pansou_timeout,
                    ) or [], False,
                )
                clients["pansou"] = self._pansou_client
            if src in ("all", "juying") and self._juying_api and _allowed("juying"):
                jobs["juying"] = lambda: (
                    self._juying_api.search(search_kw, year=manual_year) or [], False)
                clients["juying"] = self._juying_api
            if not jobs:
                return hits, has_more
            executor = ThreadPoolExecutor(max_workers=len(jobs), thread_name_prefix="tg115-manual-source")
            futures = {executor.submit(job): source_name for source_name, job in jobs.items()}
            done, pending = wait(futures, timeout=35.0)
            source_results = {}
            for future in done:
                source_name = futures[future]
                try:
                    source_hits, source_has_more = future.result()
                    source_hits = source_hits or []
                    for hit in source_hits:
                        setattr(hit, "_tg115_source", source_name)
                    source_results[source_name] = source_hits
                    if source_name == "site":
                        has_more = bool(source_has_more)
                    _record_source(source_name, clients[source_name], len(source_hits))
                except Exception as exc:
                    _source_error(source_name, exc)
            for future in pending:
                source_name = futures[future]
                if source_name == "tg" and clients.get("tg"):
                    snapshot = clients["tg"].partial_result()
                    snapshot_hits = snapshot.get("items") or []
                    if snapshot_hits:
                        source_results[source_name] = snapshot_hits
                        for hit in snapshot_hits:
                            setattr(hit, "_tg115_source", source_name)
                        source_status[source_name] = {
                            "status": "partial_success",
                            "message": f"已返回 {len(snapshot_hits)} 条，部分频道超时",
                            "count": len(snapshot_hits),
                            "completed_channels": snapshot.get("completed_channels", 0),
                            "total_channels": snapshot.get("total_channels", 0),
                        }
                        continue
                future.cancel()
                _source_error(source_name, TimeoutError("source search exceeded 35 seconds"))
            executor.shutdown(wait=False, cancel_futures=True)
            for source_name in ("tg", "site", "pansou", "juying"):
                hits.extend(source_results.get(source_name, []))
            return hits, has_more

        try:
            if self._coordinator:
                hits, has_more = self._coordinator.submit_manual(_do_search, timeout=40)
            else:
                hits, has_more = _do_search()
            results = []
            seen_results = set()
            raw_counts = Counter()
            relevance_rejected = Counter()
            dedupe_rejected = Counter()
            returned_counts = Counter()
            for h in hits:
                title = h.resource_title or h.text or "未命名资源"
                meta = self._parse_resource_meta(h.text or title)
                # 观影资源：用 search_suggest 的作品名(source_title)+年份做标题，
                # 比 panlist 里杂乱的名称（含装饰/分类前缀/《》等）干净
                src_title = getattr(h, "source_title", "") or ""
                src_year = getattr(h, "year", None)
                if src_title:
                    display_name = f"{src_title} ({src_year})" if src_year else src_title
                else:
                    display_name = meta["display_name"] or title
                candidate_year = src_year or extract_year(h.text or display_name or title)
                hit_source = getattr(h, "_tg115_source", "") or (
                    "pansou" if getattr(h, "channel_name", "") == "PanSou" else ""
                )
                raw_counts[hit_source or "unknown"] += 1
                if not is_manual_relevant_result(
                        source=hit_source,
                        query_title=search_kw,
                        query_year=manual_year,
                        candidate_title=src_title or display_name or title,
                        candidate_year=candidate_year,
                        candidate_text=h.text or "",
                ):
                    relevance_rejected[hit_source or "unknown"] += 1
                    continue
                share_url = h.share_url or ""
                normalized = normalize_resource_metadata({
                    "share_url": share_url,
                    "pan_type": getattr(h, "pan_type", "") or "",
                    "resource_title": title,
                    "text": h.text or "",
                    "is_complete": meta["is_complete"],
                    "source": hit_source,
                    "upstream_source": getattr(h, "upstream_source", "") or "",
                })
                pt = normalized["pan_type"]
                if pt == "115":
                    share_code, _ = P115Transfer._extract_payload(share_url)
                    dedupe_key = f"115:{share_code or share_url}".lower()
                else:
                    dedupe_key = share_url.strip().lower()
                if not dedupe_key or dedupe_key in seen_results:
                    dedupe_rejected[hit_source or "unknown"] += 1
                    continue
                seen_results.add(dedupe_key)
                returned_counts[hit_source or "unknown"] += 1
                result = {
                    "title": title,
                    "display_name": display_name,
                    "meta": meta["meta"],
                    "is_complete": meta["is_complete"],
                    "episode_num": meta["episode_num"],
                    "share_url": share_url,
                    "receive_code": getattr(h, "receive_code", "") or "",
                    "channel": getattr(h, "channel_name", "") or "",
                    "source": hit_source,
                    "upstream_source": getattr(h, "upstream_source", "") or "",
                    "pan_type": pt,
                    "pub_date": h.pub_date or "",
                    "text": (h.text or "")[:500],
                }
                result.update(normalized)
                # 展示标题的站点年份比资源文件名更可靠，结构化年份优先保留它。
                result["year"] = candidate_year or result.get("year")
                results.append(result)
            # 排序：完结优先，然后按最大集数降序
            results.sort(key=lambda r: (r["is_complete"], r["episode_num"]), reverse=True)
            for source_name, state in source_status.items():
                if state.get("status") == "success":
                    count = returned_counts.get(source_name, 0)
                    state.update({"message": f"返回 {count} 条", "count": count})
            # app_auth 失效提示（观影搜不到资源时给出明确原因）
            warning = ""
            if self._site_scraper and not getattr(self._site_scraper, "app_auth_valid", True):
                warning = "观影 app_auth 已失效，请在「观影」Tab 更新 app_auth 后重试"
            elif (src in ("all", "site") and self._site_scraper
                  and getattr(self._site_scraper, "last_detail_error", "")):
                warning = f"观影详情获取失败：{self._site_scraper.last_detail_error}"
            elif self._juying_api and not getattr(self._juying_api, "app_auth_valid", True):
                warning = "聚影 AppID/API Key 无效(401)，请在「聚影」Tab 检查凭证"
            if cooled_sources:
                warning = "；".join(cooled_sources + ([warning] if warning else []))
            source_states = {
                item.get("status") for item in source_status.values()
                if isinstance(item, dict)
            }
            response_status = (
                "partial_success" if results and source_states & {"partial_success", "error", "timeout"}
                else "success" if results
                else "disabled" if source_states and source_states <= {"disabled"}
                else "error" if source_states & {"error", "timeout"}
                else "empty"
            )
            return _response(
                True,
                f"找到 {len(results)} 条资源",
                **{
                "items": results,
                "results": results,
                "total": len(results),
                "status": response_status,
                "has_more": has_more,
                "warning": warning,
                "source_status": source_status,
                "source_stats": {
                    name: {
                        "raw_count": raw_counts.get(name, 0),
                        "relevance_rejected": relevance_rejected.get(name, 0),
                        "dedupe_rejected": dedupe_rejected.get(name, 0),
                        "returned_count": returned_counts.get(name, 0),
                    }
                    for name in set(raw_counts) | set(source_status)
                },
                },
            )
        except TimeoutError:
            return _response(False, "搜索超时（连接或检索过久）", status_code=504)
        except Exception as e:
            logger.error("【TG115】手动搜索异常 type=%s request_id=%s", type(e).__name__, request_id)
            return _response(False, "搜索服务暂时不可用，请稍后重试", status_code=500)

    # ---------------------------- 115 目录查询 / 浏览 API ----------------------------
    def __dir_info_api(self, cid: str = ""):
        """GET /dir_info?cid=...：根据 cid 查询 115 目录名称，便于用户核对。"""
        from starlette.responses import JSONResponse
        cid = (cid or "").strip()
        if not cid:
            return JSONResponse({"success": False, "message": "请输入 cid"}, status_code=400)
        if not self._p115_cookie:
            return JSONResponse({"success": False, "message": "未配置 115 Cookie，请先扫码登录"}, status_code=400)
        try:
            resp = self._transfer.fs_info(cid)
            data = resp.get("data") if isinstance(resp, dict) else None
            if isinstance(data, list) and data:
                data = data[0]
            if isinstance(data, dict):
                # proapi 用 file_name/file_id，webapi 用 name/n/cid，都兼容
                name = data.get("file_name") or data.get("name") or data.get("n") or ""
                c = data.get("file_id") or data.get("cid") or cid
                return JSONResponse({"success": True, "name": name, "cid": str(c)})
            return JSONResponse({"success": False, "message": "未找到该 cid 对应的目录"})
        except Exception as e:
            logger.error(f"【TG115】查询目录信息失败: {e}")
            return JSONResponse({"success": False, "message": f"查询失败: {e}"}, status_code=500)

    def __dirs_api(self, cid: str = "0"):
        """GET /dirs?cid=...：列出某 cid 下的子目录（用于目录浏览）。cid=0 为根目录。

        通过 ``fs_files(cid)`` 拿目录内容，过滤出文件夹（文件夹无 sha1，文件有）。
        """
        from starlette.responses import JSONResponse
        cid = (cid or "0").strip() or "0"
        if not self._p115_cookie:
            return JSONResponse({"success": False, "message": "未配置 115 Cookie，请先扫码登录"}, status_code=400)
        try:
            resp = self._transfer.fs_files(cid)
            logger.info(f"【TG115】/dirs cid={cid} state={resp.get('state') if isinstance(resp, dict) else '?'} msg={(resp.get('message') or resp.get('error') or '')[:80] if isinstance(resp, dict) else ''}")
            if isinstance(resp, dict) and resp.get("state") not in (True, 1, "1"):
                err = resp.get("error") or resp.get("message") or resp.get("msg") or "获取失败"
                return JSONResponse({"success": False, "message": f"115 返回：{err}"})
            data = resp.get("data") if isinstance(resp, dict) else None
            items = data if isinstance(data, list) else (data.get("data", []) if isinstance(data, dict) else [])
            dirs = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                if it.get("sha1"):  # 文件才有 sha1，跳过
                    continue
                name = it.get("name") or it.get("n") or ""
                c = str(it.get("cid", it.get("id", "")))
                if name and c:
                    dirs.append({"cid": c, "name": name})
            return JSONResponse({"success": True, "cid": cid, "dirs": dirs})
        except Exception as e:
            logger.error(f"【TG115】获取子目录失败: {e}")
            return JSONResponse({"success": False, "message": f"获取目录失败: {e}"}, status_code=500)

    def __verify_cookie_api(self):
        """GET /verify_cookie：实测 115 Cookie 是否有效（调 fs_files(0)）。"""
        from starlette.responses import JSONResponse
        if not self._p115_cookie:
            return JSONResponse({"success": False, "valid": False, "message": "未配置 115 Cookie"})
        try:
            resp = self._transfer.fs_files(0)
            ok = isinstance(resp, dict) and resp.get("state") in (True, 1, "1")
            msg = "Cookie 有效" if ok else f"Cookie 已失效：{(resp.get('error') or resp.get('message') or '')[:80] if isinstance(resp, dict) else ''}"
            return JSONResponse({"success": True, "valid": bool(ok), "message": msg})
        except Exception as e:
            logger.error(f"【TG115】验证 Cookie 异常: {e}")
            return JSONResponse({"success": False, "valid": False, "message": f"验证失败: {e}"})

    def __check_site_api(self, app_auth: str = "", site_domain: str = ""):
        """GET /check_site?app_auth=...&site_domain=...：检查观影 PoW + app_auth 登录态。

        传 ``app_auth``/``site_domain`` 则测**当前输入**（无需先保存），否则测已保存配置。
        """
        from starlette.responses import JSONResponse
        auth = (app_auth or "").strip()
        dom = (site_domain or "").strip() or self._site_domain
        if auth:
            # 临时 scraper 测当前输入的 app_auth（不依赖保存），从配置读取 site_proxy
            _cfg = self.get_data(CONFIG_KEY) or {}
            sp = (_cfg.get("site_proxy") or "").strip()
            proxy = None if sp == 'direct' else (sp or None)
            scraper = FilejinScraper(app_auth=auth, proxy=proxy, site_base=dom)
            ok, msg = scraper.check()
            return JSONResponse({"success": ok, "message": msg})
        if not self._site_scraper:
            return JSONResponse({"success": False, "message": "观影未启用或未配置 app_auth"})
        ok, msg = self._site_scraper.check()
        return JSONResponse({"success": ok, "message": msg})

    def __check_juying_api(self, app_id: str = "", api_key: str = "", domain: str = ""):
        """GET /check_juying?app_id=...&api_key=...&domain=...：检查聚影 API 鉴权。

        传参则测当前输入（无需保存），否则测已保存配置。
        """
        from starlette.responses import JSONResponse
        aid = (app_id or "").strip()
        akey = (api_key or "").strip()
        dom = (domain or "").strip() or self._juying_domain
        if aid or akey:
            api = JuyingApi(app_id=aid, api_key=akey, domain=dom, proxy=self._juying_proxy)
            ok, msg = api.check()
            return JSONResponse({"success": ok, "message": msg})
        if not self._juying_api:
            return JSONResponse({"success": False, "message": "聚影未启用或未配置 AppID/API Key/域名"})
        ok, msg = self._juying_api.check()
        return JSONResponse({"success": ok, "message": msg})

    def __check_pansou_api(self, base_url: str = ""):
        """GET /check_pansou: read-only connectivity check without resource actions."""
        from starlette.responses import JSONResponse
        url = str(base_url or "").strip() or self._pansou_url
        client = PanSouClient(
            base_url=url, token=self._pansou_token,
            timeout=self._pansou_timeout, proxy="",
            max_results=self._pansou_max_results,
        )
        try:
            ok, message = client.health_check()
            return JSONResponse({"success": ok, "message": message})
        finally:
            client.close()

    # ============================ 依赖检查 ============================
    def _check_deps(self):
        missing = []
        try:
            import bs4  # noqa: F401
        except Exception:
            missing.append("beautifulsoup4")
        try:
            import httpx  # noqa: F401
        except Exception:
            missing.append("httpx")
        if missing:
            logger.warn(f"【TG115】缺少依赖: {', '.join(missing)}，请安装后重启 MoviePilot 生效")
        if self._p115_cookie:
            ok, msg = P115Transfer.validate_cookie(self._p115_cookie)
            if not ok:
                logger.warn(f"【TG115】115 Cookie 校验: {msg}")
        # TG 爬虫无需额外配置（只需频道列表 + 网络/代理）
        if self._tg_channels and not any(ch.get("enabled", True) for ch in self._tg_channels):
            logger.warn("【TG115】所有 TG 频道均已关闭，订阅将直接回退到默认搜索")

    # ============================ 默认配置 / 频道解析 ============================
    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """首次加载 / 无配置时返回的默认结构，供前端初始化。"""
        return {
            "enabled": False,
            "p115_cookie": "",
            "p115_app": "",
            "p115_target": "/电影",
            "use_rule_groups": True,
            "notify_success": True,
            "notify_fail": False,
            "search_detail_notify": False,
            "auto_finish": False,
            "periodic_enabled": True,
            "period_hours": 2,
            "jitter_minutes": 10,
            "source_item_delay_min": 5,
            "source_item_delay_max": 10,
            "source_request_timeout_seconds": 20,
            "auto_search_budget_seconds": 60,
            "search_cache_hours": 2,
            "source_failure_threshold": 3,
            "source_cooldown_minutes": 60,
            "tg_concurrency": 2,
            "tg_page_delay_min": 0.8,
            "tg_page_delay_max": 1.5,
            "site_detail_delay_min": 1.5,
            "site_detail_delay_max": 3,
            "magnet_download_mode": "direct_115",
            "direct_timeout_hours": 12,
            "offline_poll_seconds": 45,
            "offline_max_retries": 3,
            "offline_allow_cancel": False,
            "magnet_failover_enabled": True,
            "magnet_max_attempts": 5,
            "magnet_download_wait_minutes": 1,
            "magnet_queue_timeout_hours": 12,
            "magnet_cancel_failover": True,
            "magnet_rotation_unknown_timeout_minutes": 20,
            "magnet_fallback_enabled": True,
            "wait_for_mp_organize": True,
            "site_enabled": False,
            "site_app_auth": "",
            "site_magnet_priority": True,
            "site_proxy": "",
            "site_domain": "",
            "juying_enabled": False,
            "juying_app_id": "",
            "juying_api_key": "",
            "juying_domain": "",
            "juying_proxy": "",
            "pansou_enabled": True,
            "pansou_url": "http://192.168.1.15:8888",
            "pansou_token": "",
            "pansou_proxy": "",
            "pansou_timeout": 20,
            "pansou_refresh": False,
            "pansou_cloud_types": ["115", "magnet"],
            "pansou_max_results": 100,
            "tg_search_enabled": True,
            "tg_channels": [],
        }

    @staticmethod
    def _parse_string_list(raw: Any, default: List[str]) -> List[str]:
        if raw is None or raw == "":
            return list(default)
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                raw = parsed if isinstance(parsed, list) else raw.split(",")
            except Exception:
                raw = raw.split(",")
        if not isinstance(raw, (list, tuple, set)):
            return list(default)
        values = [str(item).strip().lower() for item in raw if str(item).strip()]
        return values or list(default)

    @staticmethod
    def _parse_channels(raw: Any) -> List[Dict[str, Any]]:
        """解析 TG 频道列表。

        兼容自定义前端直接传入的数组，以及历史 JSON 字符串：
          - list：[{"name":"..","id":"..","enabled":true}, ...] 或 ["@xxx", ...]
          - str ：JSON 字符串
        每条归一化为 {"name","id","enabled"}。
        """
        channels: List[Dict[str, Any]] = []

        def push(name: str, cid: str, enabled: bool = True):
            cid = (cid or "").strip()
            if not cid:
                return
            channels.append({
                "name": repair_mojibake((name or "").strip()) or cid,
                "id": cid,
                "enabled": bool(enabled),
            })

        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    push(
                        str(item.get("name") or ""),
                        str(item.get("id") or item.get("link") or item.get("channel") or ""),
                        item.get("enabled", True),
                    )
                elif isinstance(item, str):
                    push(item, item)
        elif isinstance(raw, str):
            text = raw.strip()
            if text:
                try:
                    data = json.loads(text)
                except Exception as e:
                    logger.warn(f"【TG115】TG 频道列表 JSON 解析失败：{e}")
                    data = None
                if isinstance(data, list):
                    return TgSearch115._parse_channels(data)
        return channels

    # ============================ 静态工具 ============================
    @staticmethod
    def _safe_int(v: Any, default: int = 0) -> int:
        try:
            return int(v)
        except Exception:
            return default

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return default

    @staticmethod
    def _to_bool(v: Any, default: bool = False) -> bool:
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("1", "true", "yes", "on")
