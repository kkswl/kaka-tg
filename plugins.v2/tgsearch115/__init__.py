# -*- coding: utf-8 -*-
"""MoviePilot 插件：订阅新增时优先到 Telegram 频道搜索 115 资源并转存。

================================================================================
 设计总览
================================================================================
1. 触发：监听 ``EventType.SubscribeAdded`` 广播事件。该事件在订阅创建时由
   ``SubscribeChain.add`` 发出，事件数据包含 ``subscribe_id`` 与 ``mediainfo``。
   广播事件由 EventManager 的独立线程消费，且本插件在处理器内再起一个守护线程
   执行实际工作，因此**绝不会阻塞 MoviePilot 主流程**。

2. TG 搜索：用 Telethon User Session 读取目标频道历史消息，按订阅标题/年份检索，
   提取其中的 115 分享链接（见 ``tg_searcher.py``）。支持多个频道，每个频道可单独
   开关、检查连通性。

3. 规则匹配：将每条命中构造成 ``TorrentInfo``，调用 MoviePilot 内置的
   ``SubscribeChain().filter_torrents(rule_groups, torrent_list, mediainfo)``
   与 ``TorrentHelper.filter_torrent``，复用用户在 MP 中配置的过滤规则。

4. 115 转存：命中后用 ``p115client`` + 用户 Cookie 调 ``share_receive`` 转存到
   指定 115 目录（见 ``p115_transfer.py``）。

5. 完成订阅：转存成功后直接标记订阅完成（写历史 / 删订阅 / 发
   ``SubscribeComplete`` 事件 / 推送通知），镜像 ``SubscribeChain.__finish_subscribe``。

6. 回退：任何环节（未识别媒体 / TG 无命中 / 规则不匹配 / 转存失败 / 异常）都
   静默 ``return``，**不删除、不修改订阅**，MoviePilot 默认的定时站点搜索照常进行。
================================================================================
"""
import json
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.chain.subscribe import SubscribeChain, build_subscribe_meta
from app.core.context import MediaInfo, TorrentInfo
from app.core.event import Event, eventmanager
from app.db.subscribe_oper import SubscribeOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.torrent import TorrentHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType, SystemConfigKey

from .p115_transfer import P115Transfer
from .tg_searcher import TgChannelSearcher


class TgSearch115(_PluginBase):
    """订阅新增 -> TG 频道搜索 115 -> 转存 -> 完成订阅；失败平滑回退。"""

    # 插件元信息
    plugin_name = "拦截mp订阅"
    plugin_desc = (
        "订阅新增时优先到指定 Telegram 频道搜索 115 资源，命中并转存成功后自动完成订阅；"
        "未命中或转存失败则平滑回退到 MoviePilot 默认站点搜索。"
    )
    plugin_version = "1.0.4"
    plugin_author = "MoviePilot User"
    plugin_icon = "T"
    plugin_config_prefix = "plugin.tgsearch115"
    author_url = ""
    plugin_url = ""

    # 运行态
    _enabled = False
    _lock = threading.Lock()
    _running_ids: set = set()
    _searcher: Optional[TgChannelSearcher] = None
    _transfer: Optional[P115Transfer] = None

    # 配置项
    _tg_api_id = 0
    _tg_api_hash = ""
    _tg_session = ""
    _tg_channels = []
    _tg_max_messages = 200
    _tg_proxy = ""
    _p115_cookie = ""
    _p115_target = "/"
    _use_rule_groups = True
    _delay_seconds = 3
    _notify_success = True
    _notify_fail = False

    # ============================ 生命周期 ============================
    def init_plugin(self, config: dict = None):
        if not config:
            return
        self._enabled = self._to_bool(config.get("enabled"), False)
        self._tg_api_id = self._safe_int(config.get("tg_api_id"), 0)
        self._tg_api_hash = config.get("tg_api_hash") or ""
        self._tg_session = config.get("tg_session") or ""
        self._tg_max_messages = self._safe_int(config.get("tg_max_messages"), 200)
        self._tg_proxy = config.get("tg_proxy") or ""
        self._p115_cookie = config.get("p115_cookie") or ""
        self._p115_target = config.get("p115_target") or "/"
        self._use_rule_groups = self._to_bool(config.get("use_rule_groups"), True)
        self._delay_seconds = self._safe_int(config.get("delay_seconds"), 3)
        self._notify_success = self._to_bool(config.get("notify_success"), True)
        self._notify_fail = self._to_bool(config.get("notify_fail"), False)

        # 重建频道列表：从卡片 ch_{i}_* 字段 + 新增 + 批量导入
        channels: List[Dict[str, Any]] = []
        i = 0
        while f"ch_{i}_id" in config or f"ch_{i}_name" in config:
            cid = str(config.get(f"ch_{i}_id") or "").strip()
            cname = str(config.get(f"ch_{i}_name") or "").strip() or cid
            enabled = self._to_bool(config.get(f"ch_{i}_enabled"), True)
            delete = self._to_bool(config.get(f"ch_{i}_delete"), False)
            if cid and not delete:
                channels.append({"name": cname, "id": cid, "enabled": enabled})
            i += 1
        # 新增频道
        new_id = str(config.get("new_ch_id") or "").strip()
        new_name = str(config.get("new_ch_name") or "").strip()
        if new_id:
            channels.append({"name": new_name or new_id, "id": new_id, "enabled": True})
        # 批量导入
        imp = str(config.get("import_json") or "").strip()
        if imp:
            for ch in self._parse_channels(imp):
                ch.setdefault("enabled", True)
                channels.append(ch)
        self._tg_channels = channels

        # 搜索器只接收「已启用」的频道
        enabled_channels = [ch for ch in channels if ch.get("enabled", True)]
        self._searcher = TgChannelSearcher(
            api_id=self._tg_api_id,
            api_hash=self._tg_api_hash,
            session_string=self._tg_session,
            channels=enabled_channels,
            max_messages=self._tg_max_messages,
            proxy=self._tg_proxy,
        )
        self._transfer = P115Transfer(
            cookie=self._p115_cookie, default_target_path=self._p115_target
        )

        # 持久化干净配置：去掉临时字段 ch_*/new_*/import_json，保留 tg_channels(JSON)
        try:
            clean = {
                "enabled": self._enabled,
                "tg_api_id": self._tg_api_id,
                "tg_api_hash": self._tg_api_hash,
                "tg_session": self._tg_session,
                "tg_max_messages": self._tg_max_messages,
                "tg_proxy": self._tg_proxy,
                "p115_cookie": self._p115_cookie,
                "p115_target": self._p115_target,
                "use_rule_groups": self._use_rule_groups,
                "delay_seconds": self._delay_seconds,
                "notify_success": self._notify_success,
                "notify_fail": self._notify_fail,
                "tg_channels": json.dumps(channels, ensure_ascii=False),
            }
            self.update_config(clean)
        except Exception as e:
            logger.warn(f"【TG115】保存清理后的配置失败: {e}")

        if self._enabled:
            logger.info("【TG115】插件已启用")
            self._check_deps()

    # ============================ 事件入口 ============================
    @eventmanager.register(EventType.SubscribeAdded)
    def on_subscribe_added(self, event: Event):
        """订阅新增事件：异步触发 TG+115 优先处理。"""
        if not self._enabled:
            return
        data = getattr(event, "event_data", None) or {}
        subscribe_id = data.get("subscribe_id")
        if not subscribe_id:
            return
        threading.Thread(
            target=self._handle_subscribe,
            args=(int(subscribe_id),),
            name="tg115-subscribe",
            daemon=True,
        ).start()

    # ============================ 核心流程 ============================
    def _handle_subscribe(self, subscribe_id: int):
        """单订阅的 TG 搜索 -> 匹配 -> 转存 -> 完成流程；任何失败均平滑回退。"""
        try:
            with self._lock:
                if subscribe_id in self._running_ids:
                    return
                self._running_ids.add(subscribe_id)

            if self._delay_seconds and self._delay_seconds > 0:
                time.sleep(min(self._delay_seconds, 300))

            subscribe = SubscribeOper().get(subscribe_id)
            if not subscribe:
                return

            try:
                meta = build_subscribe_meta(subscribe)
            except Exception as e:
                logger.warn(f"【TG115】构造订阅 meta 失败，回退: {e}")
                return
            mediainfo = self._recognize(subscribe, meta)
            if not mediainfo:
                logger.warn(f"【TG115】订阅 {subscribe.name} 未识别到媒体信息，回退到默认搜索")
                return

            keyword = self._build_keyword(subscribe)
            logger.info(f"【TG115】订阅 [{subscribe.name}] 开始搜索 TG 频道，关键字: {keyword}")
            hits = self._searcher.search(keyword) if self._searcher else []
            if not hits:
                logger.info(f"【TG115】订阅 [{subscribe.name}] TG 频道未找到 115 资源，回退到默认搜索")
                self._notify_fail(subscribe, "TG 频道未找到 115 资源")
                return

            torrents = self._build_torrents(hits)
            matched = self._filter_resources(subscribe, mediainfo, torrents)
            if not matched:
                logger.info(f"【TG115】订阅 [{subscribe.name}] TG 资源均不符合 MP 过滤规则，回退到默认搜索")
                self._notify_fail(subscribe, "TG 资源不符合过滤规则")
                return

            best = matched[0]
            share_url = best.page_url or ""
            logger.info(f"【TG115】订阅 [{subscribe.name}] 命中: {best.title} -> {share_url}")

            ok, msg, _data = self._transfer.transfer(share_url, self._p115_target) \
                if self._transfer else (False, "转存模块未初始化", {})
            if not ok:
                logger.warn(f"【TG115】订阅 [{subscribe.name}] 115 转存失败: {msg}，回退到默认搜索")
                self._notify_fail(subscribe, f"115 转存失败: {msg}")
                return

            self._finish_subscribe(subscribe, meta, mediainfo, best, msg)
        except Exception as e:
            logger.error(f"【TG115】处理订阅 {subscribe_id} 异常，回退到默认搜索: {e}")
        finally:
            with self._lock:
                self._running_ids.discard(subscribe_id)

    # ============================ 辅助方法 ============================
    def _recognize(self, subscribe, meta) -> Optional[MediaInfo]:
        try:
            mediainfo = SubscribeChain().recognize_media(
                meta=meta, mtype=meta.type,
                tmdbid=subscribe.tmdbid, doubanid=subscribe.doubanid,
                episode_group=subscribe.episode_group, cache=False,
            )
            if mediainfo:
                return mediainfo
        except Exception as e:
            logger.warn(f"【TG115】recognize_media 异常: {e}")
        try:
            return MediaInfo(
                type=subscribe.type, title=subscribe.name, year=subscribe.year,
                tmdb_id=subscribe.tmdbid, douban_id=subscribe.doubanid,
            )
        except Exception:
            return None

    @staticmethod
    def _build_keyword(subscribe) -> str:
        parts = [p for p in [subscribe.name, subscribe.year] if p]
        return " ".join(parts)

    @staticmethod
    def _build_torrents(hits) -> List[TorrentInfo]:
        torrents: List[TorrentInfo] = []
        for h in hits:
            torrents.append(TorrentInfo(
                title=h.resource_title or "未命名资源",
                description=h.text,
                page_url=h.share_url,
                site_name="TG频道",
                pubdate=h.pub_date,
                size=0.0, seeders=0, peers=0,
            ))
        return torrents

    def _filter_resources(self, subscribe, mediainfo, torrents: List[TorrentInfo]) -> List[TorrentInfo]:
        if not torrents:
            return []
        if self._use_rule_groups:
            rule_groups = self._get_rule_groups(subscribe)
            if rule_groups:
                try:
                    torrents = SubscribeChain().filter_torrents(
                        rule_groups=rule_groups, torrent_list=torrents, mediainfo=mediainfo,
                    ) or []
                except Exception as e:
                    logger.warn(f"【TG115】filter_torrents 异常，跳过规则组过滤: {e}")
        filter_params = self._get_filter_params(subscribe)
        if filter_params:
            torrents = [t for t in torrents if TorrentHelper.filter_torrent(t, filter_params)]
        return torrents

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

    def _finish_subscribe(self, subscribe, meta, mediainfo, torrent: TorrentInfo, transfer_msg: str):
        try:
            oper = SubscribeOper()
            oper.add_history(**subscribe.to_dict())
            oper.delete(subscribe.id)
            eventmanager.send_event(EventType.SubscribeComplete, {
                "subscribe_id": subscribe.id,
                "subscribe_info": subscribe.to_dict(),
                "mediainfo": mediainfo.to_dict() if hasattr(mediainfo, "to_dict") else {},
            })
            logger.info(f"【TG115】订阅 [{subscribe.name}] 已通过 TG+115 完成并标记完结")
            if self._notify_success:
                try:
                    self.post_message(
                        mtype=NotificationType.Subscribe,
                        title=f"订阅完成 {subscribe.name}",
                        text=f"已通过 TG 频道找到 115 资源并转存完成。\n资源: {torrent.title}\n{transfer_msg}",
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"【TG115】标记订阅完成异常（不影响 MP 默认流程）: {e}")

    def _notify_fail(self, subscribe, reason: str):
        if not self._notify_fail:
            return
        try:
            self.post_message(
                mtype=NotificationType.Subscribe,
                title=f"TG115 未命中 {subscribe.name}",
                text=f"原因: {reason}，将使用 MoviePilot 默认搜索。",
            )
        except Exception:
            pass

    # ============================ 频道检查 API ============================
    def __check_channel_api(self, index: int = -1):
        """API：检查指定 TG 频道连通性"""
        from starlette.responses import JSONResponse
        try:
            index = int(index)
        except Exception:
            index = -1
        channels = self._tg_channels or []
        if index < 0 or index >= len(channels):
            return JSONResponse({"success": False, "message": "频道序号无效"})
        ch = channels[index]
        if not self._searcher or not (
            self._searcher.api_id and self._searcher.api_hash and self._searcher.session_string
        ):
            return JSONResponse({"success": False, "message": "TG 配置不完整（api_id/api_hash/session）"})
        ok, msg = self._searcher.check_channel(ch["id"])
        return JSONResponse({"success": ok, "message": f"[{ch.get('name') or ch['id']}] {msg}"})

    def __check_all_api(self):
        """API：检查所有 TG 频道连通性"""
        from starlette.responses import JSONResponse
        channels = self._tg_channels or []
        if not channels:
            return JSONResponse({"success": False, "message": "未配置任何频道"})
        if not self._searcher or not (
            self._searcher.api_id and self._searcher.api_hash and self._searcher.session_string
        ):
            return JSONResponse({"success": False, "message": "TG 配置不完整（api_id/api_hash/session）"})
        results = []
        for ch in channels:
            ok, msg = self._searcher.check_channel(ch["id"])
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

    # ============================ 依赖检查 ============================
    def _check_deps(self):
        missing = []
        try:
            import telethon  # noqa: F401
        except Exception:
            missing.append("telethon")
        try:
            import p115client  # noqa: F401
        except Exception:
            missing.append("p115client")
        if missing:
            logger.warn(f"【TG115】缺少依赖: {', '.join(missing)}，请安装后重启 MoviePilot 生效")
        if self._p115_cookie:
            ok, msg = P115Transfer.validate_cookie(self._p115_cookie)
            if not ok:
                logger.warn(f"【TG115】115 Cookie 校验: {msg}")
        if not (self._tg_api_id and self._tg_api_hash and self._tg_session):
            logger.warn("【TG115】TG 搜索配置不完整（需要 api_id/api_hash/session）")
        if self._tg_channels and not any(ch.get("enabled", True) for ch in self._tg_channels):
            logger.warn("【TG115】所有 TG 频道均已关闭，订阅将直接回退到默认搜索")

    # ============================ 静态工具 ============================
    @staticmethod
    def _safe_int(v: Any, default: int = 0) -> int:
        try:
            return int(v)
        except Exception:
            return default

    @staticmethod
    def _to_bool(v: Any, default: bool = False) -> bool:
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("1", "true", "yes", "on")

    @staticmethod
    def _parse_channels(raw: Any, legacy_single: Any = None) -> List[Dict[str, Any]]:
        """解析 TG 频道列表 JSON。保留 enabled 字段；兼容旧单频道。"""
        channels: List[Dict[str, Any]] = []
        text = (str(raw) if raw is not None else "").strip()
        if text:
            try:
                data = json.loads(text)
            except Exception as e:
                logger.warn(f"【TG115】TG 频道列表 JSON 解析失败：{e}")
                data = None
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        cid = str(item.get("id") or item.get("channel") or "").strip()
                        cname = str(item.get("name") or "").strip() or cid
                        if cid:
                            channels.append({
                                "name": cname, "id": cid,
                                "enabled": bool(item.get("enabled", True)),
                            })
                    elif isinstance(item, str):
                        s = item.strip()
                        if s:
                            channels.append({"name": s, "id": s, "enabled": True})
        if not channels and legacy_single:
            ls = str(legacy_single).strip()
            if ls:
                channels.append({"name": ls, "id": ls, "enabled": True})
        return channels

    # ============================ 插件接口 ============================
    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/check_channel",
                "endpoint": self.__check_channel_api,
                "methods": ["GET"],
                "summary": "检查指定 TG 频道连通性",
            },
            {
                "path": "/check_all",
                "endpoint": self.__check_all_api,
                "methods": ["GET"],
                "summary": "检查所有 TG 频道连通性",
            },
        ]

    @staticmethod
    def get_page() -> Optional[List[dict]]:
        return None

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        plugin_id = self.__class__.__name__
        saved = self.get_config() or {}
        channels = self._parse_channels(saved.get("tg_channels"))
        for ch in channels:
            ch.setdefault("enabled", True)

        content: List[dict] = [
            # 启用开关
            {"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                    {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件", "color": "primary"}}
                ]},
                {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                    {"component": "VSwitch", "props": {"model": "use_rule_groups", "label": "使用 MP 过滤规则组二次匹配", "color": "primary"}}
                ]},
            ]},
            # 说明
            {"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12}, "content": [
                    {"component": "VAlert", "props": {
                        "type": "info", "variant": "tonal",
                        "text": "订阅新增时优先到 TG 频道搜索 115 资源；未命中或转存失败将自动回退到 MoviePilot 默认搜索。"
                    }}
                ]}
            ]},
        ]

        # ===== TG 频道管理板块（独立板块：卡片 + 开关 + 检查 + 删除）=====
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VAlert", "props": {
                    "type": "warning", "variant": "tonal",
                    "text": "【TG 频道管理】每个频道一张卡片，可单独开启/关闭、检查连通性、勾选「删除」后保存即移除；新增或批量导入后点「保存」生效。"
                }}
            ]}
        ]})
        # 一键检查所有
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VBtn", "props": {
                    "color": "primary", "variant": "tonal", "size": "small", "class": "mb-2",
                    "prepend-icon": "mdi-connection"
                }, "text": "一键检查所有频道连通性", "events": {
                    "click": {
                        "api": f"plugin/{plugin_id}/check_all?apikey={settings.API_TOKEN}",
                        "method": "get"
                    }
                }}
            ]}
        ]})
        # 每个频道一张卡片
        for i, ch in enumerate(channels):
            content.append({"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12}, "content": [
                    {"component": "VCard", "props": {"variant": "outlined", "class": "mb-2"}, "content": [
                        {"component": "VCardText", "content": [
                            {"component": "VRow", "content": [
                                {"component": "VCol", "props": {"cols": 12, "md": 5}, "content": [
                                    {"component": "VTextField", "props": {"model": f"ch_{i}_name", "label": "频道名称", "density": "compact", "hide-details": True}}
                                ]},
                                {"component": "VCol", "props": {"cols": 12, "md": 5}, "content": [
                                    {"component": "VTextField", "props": {"model": f"ch_{i}_id", "label": "频道 ID（@用户名/邀请链接/数字ID）", "density": "compact", "hide-details": True}}
                                ]},
                                {"component": "VCol", "props": {"cols": 6, "md": 1}, "content": [
                                    {"component": "VSwitch", "props": {"model": f"ch_{i}_enabled", "label": "启用", "color": "primary", "density": "compact", "hide-details": True, "inline": True}}
                                ]},
                                {"component": "VCol", "props": {"cols": 6, "md": 1}, "content": [
                                    {"component": "VSwitch", "props": {"model": f"ch_{i}_delete", "label": "删除", "color": "error", "density": "compact", "hide-details": True, "inline": True}}
                                ]},
                            ]},
                            {"component": "VRow", "content": [
                                {"component": "VCol", "props": {"cols": 12}, "content": [
                                    {"component": "VBtn", "props": {
                                        "color": "primary", "size": "small", "variant": "tonal",
                                        "prepend-icon": "mdi-link-variant"
                                    }, "text": "检查连通性", "events": {
                                        "click": {
                                            "api": f"plugin/{plugin_id}/check_channel?apikey={settings.API_TOKEN}",
                                            "method": "get",
                                            "params": {"index": i}
                                        }
                                    }}
                                ]}
                            ]}
                        ]}
                    ]}
                ]}
            ]})
        # 添加新频道
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VCard", "props": {"variant": "tonal", "color": "success", "class": "mb-2"}, "content": [
                    {"component": "VCardText", "content": [
                        {"component": "div", "props": {"class": "text-subtitle-2 mb-2"}, "text": "➕ 添加新频道（填写后点「保存」即可加入列表）"},
                        {"component": "VRow", "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 5}, "content": [
                                {"component": "VTextField", "props": {"model": "new_ch_name", "label": "频道名称"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 7}, "content": [
                                {"component": "VTextField", "props": {"model": "new_ch_id", "label": "频道 ID（@用户名/邀请链接/数字ID）"}}
                            ]},
                        ]}
                    ]}
                ]}
            ]}
        ]})
        # 批量导入
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VTextarea", "props": {
                    "model": "import_json",
                    "label": "批量导入（JSON，填写后点「保存」追加到列表）",
                    "hint": "格式：[{\"name\": \"频道1\", \"id\": \"@xxx\", \"enabled\": true}, {\"name\": \"频道2\", \"id\": \"...\"}]",
                    "persistent-hint": True, "rows": 3
                }}
            ]}
        ]})

        # ===== Telegram 连接配置 =====
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                {"component": "VTextField", "props": {"model": "tg_api_id", "label": "TG API ID", "hint": "在 https://my.telegram.org 申请的 API ID（数字）", "persistent-hint": True}}
            ]},
            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                {"component": "VTextField", "props": {"model": "tg_api_hash", "label": "TG API Hash", "hint": "在 https://my.telegram.org 申请的 API Hash", "persistent-hint": True}}
            ]},
        ]})
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VTextarea", "props": {
                    "model": "tg_session", "label": "TG Session String",
                    "hint": "用 gen_tg_session.py 在本地电脑生成后粘贴（容器内无法交互登录）",
                    "persistent-hint": True, "rows": 2
                }}
            ]}
        ]})
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                {"component": "VTextField", "props": {"model": "tg_max_messages", "label": "最大检索消息数", "placeholder": "200", "hint": "每个频道最多检索的历史消息条数", "persistent-hint": True}}
            ]},
            {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                {"component": "VTextField", "props": {"model": "tg_proxy", "label": "TG 代理", "placeholder": "socks5://host:port", "hint": "可选；SOCKS 需另装 telethon[socks]", "persistent-hint": True}}
            ]},
            {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                {"component": "VTextField", "props": {"model": "delay_seconds", "label": "触发延迟（秒）", "placeholder": "3", "hint": "订阅创建后等待多少秒再触发", "persistent-hint": True}}
            ]},
        ]})

        # ===== 115 配置 =====
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VTextarea", "props": {
                    "model": "p115_cookie", "label": "115 Cookie",
                    "hint": "用 115 客户端扫码登录后抓取，需含 UID/CID/SEID；网页版 Cookie 无法转存",
                    "persistent-hint": True, "rows": 2
                }}
            ]}
        ]})
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                {"component": "VTextField", "props": {"model": "p115_target", "label": "115 转存目标目录", "placeholder": "/电影", "hint": "如 /电影；不存在会自动创建；也可填数字 cid", "persistent-hint": True}}
            ]},
        ]})

        # ===== 通知 =====
        content.append({"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                {"component": "VSwitch", "props": {"model": "notify_success", "label": "转存成功通知", "color": "primary"}}
            ]},
            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                {"component": "VSwitch", "props": {"model": "notify_fail", "label": "未命中/失败通知", "color": "primary"}}
            ]},
        ]})

        # 默认值
        defaults: Dict[str, Any] = {
            "enabled": False, "tg_api_id": "", "tg_api_hash": "", "tg_session": "",
            "tg_max_messages": 200, "tg_proxy": "", "p115_cookie": "", "p115_target": "/电影",
            "use_rule_groups": True, "delay_seconds": 3, "notify_success": True, "notify_fail": False,
            "new_ch_name": "", "new_ch_id": "", "import_json": "",
        }
        for i, ch in enumerate(channels):
            defaults[f"ch_{i}_name"] = ch["name"]
            defaults[f"ch_{i}_id"] = ch["id"]
            defaults[f"ch_{i}_enabled"] = ch.get("enabled", True)
            defaults[f"ch_{i}_delete"] = False

        return [{"component": "VForm", "content": content}], defaults

    def stop_service(self):
        """停止插件：清理运行态。守护线程为 daemon，随主进程退出。"""
        with self._lock:
            self._running_ids.clear()
