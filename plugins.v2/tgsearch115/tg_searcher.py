# -*- coding: utf-8 -*-
"""Telegram 频道历史消息搜索 + 115 分享链接提取（Telethon User Session）。

支持同时检索多个 TG 频道。频道列表在插件配置里以 JSON 提供：
    [{"name": "频道1", "id": "@username或邀请链接或数字ID"}, {"name": "频道2", "id": "..."}]

为什么用 Telethon User Session 而不是 Bot API：
- 读取非公开频道的历史消息并按关键字检索，Bot API 无法可靠完成（Bot 只能收到
  被加入后的新消息，且无法翻历史）。
- Telethon 以用户身份登录，可读取已加入频道的全部历史并支持 ``search`` 检索。
- Docker 环境下用 **Session String**（一次本地生成）即可，无需运行时交互登录。
"""
import asyncio
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlparse

from app.log import logger


# 115 分享链接正则：匹配 115.com / anxia.com / 115cdn.com 的 /s/ 链接
_115_LINK_RE = re.compile(
    r"https?://(?:[\w-]+\.)*(?:115\.com|anxia\.com|115cdn\.com)/(?:s/|share\.php\?)[^\s<>\"'）)]*",
    re.IGNORECASE,
)


@dataclass
class TgHit:
    """一条命中的 115 资源。"""
    msg_id: int
    text: str
    share_url: str
    share_code: str
    receive_code: str
    resource_title: str
    channel_name: str = ""
    pub_date: Optional[str] = None


class TgChannelSearcher:
    """基于 Telethon User Session 的多频道历史消息搜索器。"""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_string: str,
        channels: Optional[List[Dict[str, str]]] = None,
        max_messages: int = 200,
        proxy: Optional[str] = None,
    ) -> None:
        self.api_id = api_id
        self.api_hash = api_hash or ""
        self.session_string = session_string or ""
        # channels: [{"name": "频道名", "id": "@username/链接/数字ID"}, ...]
        self.channels = channels or []
        self.max_messages = int(max_messages or 200)
        self.proxy = (proxy or "").strip() or None

    def is_ready(self) -> bool:
        return bool(
            self.api_id and self.api_hash and self.session_string and self.channels
        )

    def search(self, keyword: str, limit: Optional[int] = None) -> List[TgHit]:
        """同步入口：依次搜索所有频道历史消息，聚合返回含 115 分享链接的命中列表。"""
        if not self.is_ready():
            logger.warn("【TG115】TG 搜索器配置不完整（需要 api_id/api_hash/session/频道列表）")
            return []
        try:
            # 事件处理器运行在独立线程，可安全创建新事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._async_search(keyword, limit))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"【TG115】TG 频道搜索失败: {e}")
            return []

    # ============================ 异步实现 ============================
    async def _async_search(self, keyword: str, limit: Optional[int]) -> List[TgHit]:
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        proxy = self._parse_proxy(self.proxy)
        client = TelegramClient(
            StringSession(self.session_string),
            self.api_id,
            self.api_hash,
            proxy=proxy,
            connection_retries=3,
            retry_delay=2,
            request_retries=3,
        )
        all_hits: List[TgHit] = []
        await client.connect()
        try:
            if not await client.is_user_authorized():
                logger.error("【TG115】TG Session 未授权或已失效，请重新生成 session string")
                return []
            kw = (keyword or "").strip()
            per_channel_limit = int(limit or self.max_messages)
            for ch in self.channels:
                cid = (ch.get("id") or "").strip()
                cname = (ch.get("name") or "").strip() or cid
                if not cid:
                    continue
                try:
                    entity = await client.get_entity(cid)
                except Exception as e:
                    logger.error(f"【TG115】解析频道 [{cname}] ({cid}) 失败: {e}")
                    continue
                ch_hits: List[TgHit] = []
                try:
                    async for msg in client.iter_messages(
                        entity, search=kw or None, limit=per_channel_limit
                    ):
                        text = getattr(msg, "message", None) or ""
                        if not text:
                            continue
                        ch_hits.extend(self._extract_hits(msg.id, text, msg, cname))
                        if len(ch_hits) >= per_channel_limit:
                            break
                except Exception as e:
                    logger.error(f"【TG115】检索频道 [{cname}] 出错: {e}")
                    continue
                logger.info(
                    f"【TG115】频道 [{cname}] 检索 '{kw}' 命中 {len(ch_hits)} 条 115 资源"
                )
                all_hits.extend(ch_hits)
            logger.info(
                f"【TG115】共检索 {len(self.channels)} 个频道，合计命中 {len(all_hits)} 条 115 资源"
            )
            return all_hits
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    # ============================ 解析工具 ============================
    def _extract_hits(self, msg_id: int, text: str, msg, channel_name: str) -> List[TgHit]:
        hits: List[TgHit] = []
        for url in _115_LINK_RE.findall(text):
            share_code, receive_code = self._parse_payload(url)
            if not share_code:
                continue
            hits.append(TgHit(
                msg_id=msg_id,
                text=text,
                share_url=url,
                share_code=share_code,
                receive_code=receive_code,
                resource_title=self._guess_title(text, url),
                channel_name=channel_name,
                pub_date=self._fmt_date(getattr(msg, "date", None)),
            ))
        return hits

    @staticmethod
    def _parse_payload(url: str) -> Tuple[str, str]:
        parsed = urlparse(url)
        share_code = ""
        m = re.search(r"/s/([^/?#]+)", parsed.path or "")
        if m:
            share_code = m.group(1).strip()
        q = dict(parse_qsl(parsed.query, keep_blank_values=True))
        receive_code = str(
            q.get("password") or q.get("receive_code") or q.get("pwd") or ""
        ).strip()
        return share_code, receive_code

    @staticmethod
    def _guess_title(text: str, url: str) -> str:
        """从消息文本里猜测资源发布名（供 MP 识别/过滤）。"""
        # 去掉所有链接
        cleaned = re.sub(r"https?://\S+", "", text)
        # 取第一个非空、非纯符号行
        for line in cleaned.splitlines():
            line = line.strip(" \t-–-·•|·:：")
            if line:
                return line[:200]
        return cleaned.strip()[:200]

    @staticmethod
    def _fmt_date(d) -> Optional[str]:
        if not d:
            return None
        try:
            return d.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(d)

    @staticmethod
    def _parse_proxy(proxy: Optional[str]):
        """解析代理字符串为 Telethon 可接受的 proxy 参数。

        支持 ``socks5://host:port`` / ``socks4://host:port`` / ``http://host:port``。
        SOCKS 代理需要安装 ``python-socks``（即 ``telethon[socks]``）。
        """
        if not proxy:
            return None
        try:
            p = urlparse(proxy)
            scheme = (p.scheme or "").lower()
            host, port = p.hostname, p.port
            if not host or not port:
                logger.warn(f"【TG115】代理格式无法解析: {proxy}")
                return None
            if scheme.startswith("socks"):
                stype = "socks5" if "5" in scheme else "socks4"
                return (stype, host, port)
            if scheme in ("http", "https"):
                return (host, port)
            logger.warn(f"【TG115】不支持的代理协议: {scheme}")
        except Exception as e:
            logger.warn(f"【TG115】解析代理失败，将不使用代理: {e}")
        return None
