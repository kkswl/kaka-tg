"""资源展示与筛选共用的无副作用元数据归一化。

这里的结果只用于展示、排序和筛选；正式转存仍须经过 MoviePilot 规则和身份复核。
"""
from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import urlparse


_PAN_DOMAINS = {
    "115": ("115.com", "115cdn.com"),
    "baidu": ("pan.baidu.com",),
    "quark": ("quark.cn",),
    "aliyun": ("aliyundrive.com", "alipan.com"),
    "xunlei": ("pan.xunlei.com",),
    "cloud189": ("cloud.189.cn",),
    "uc": ("uc.cn",),
    "123": ("123pan.com",),
}


def _text(value: Any) -> str:
    return str(value or "").translate(str.maketrans({"　": " ", "－": "-", "—": "-", "．": "."}))


def _match(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def normalize_pan_type(url: Any = "", declared: Any = "", text: Any = "") -> str:
    """按 URL 优先识别网盘类型，未知时才使用上游声明及文本。"""
    raw_url = _text(url).strip()
    lower_url = raw_url.lower()
    if lower_url.startswith(("magnet:?", "ed2k://")):
        return "magnet"
    host = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}").hostname or ""
    host = host.lower()
    for kind, domains in _PAN_DOMAINS.items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return kind
    declared_value = _text(declared).strip().lower()
    aliases = {"115网盘": "115", "ali": "aliyun", "alipan": "aliyun", "天翼": "cloud189", "迅雷": "xunlei"}
    if declared_value in set(_PAN_DOMAINS) | {"magnet"}:
        return declared_value
    if declared_value in aliases:
        return aliases[declared_value]
    fallback = (raw_url + " " + _text(text)).lower()
    for kind, domains in _PAN_DOMAINS.items():
        if any(domain in fallback for domain in domains):
            return kind
    return "other"


def _resolution(text: str) -> str:
    # 4K first: 1080 must not win when a title contains both technical variants.
    if _match(text, r"(?<![\w\d])(?:4\s*k|2160[pi]?|3840\s*[x×]\s*2160|uhd)(?![\w\d])"):
        return "4k"
    if _match(text, r"(?<![\w\d])(?:1080[pi]?|1920\s*[x×]\s*1080)(?![\w\d])"):
        return "1080p"
    if _match(text, r"(?<![\w\d])(?:720[pi]?|1280\s*[x×]\s*720)(?![\w\d])"):
        return "720p"
    return "unknown"


def _subtitle_type(text: str) -> str:
    normalized = text.lower()
    # Audio language must never be treated as subtitles.
    if _match(normalized, r"国语|中文配音|普通话配音") and not _match(normalized, r"字幕|中字|(?:chs|cht)(?:\.|\s|_|-)*(?:srt|ass|sub)|简体|繁体"):
        return "none"
    chs = _match(normalized, r"中文字幕|中字|简体中文|简中|内封简体|内封中字|\bchs\b|\.chs\.(?:srt|ass|sub)|chinese\s+subtitles?")
    cht = _match(normalized, r"繁体中文|繁中|内封繁体|\bcht\b|\.cht\.(?:srt|ass|sub)")
    both = _match(normalized, r"简繁(?:中文|字幕)?|简体.*繁体|繁体.*简体")
    if both or (chs and cht):
        return "chs_cht"
    if chs:
        return "chs"
    if cht:
        return "cht"
    return "none"


def _season(text: str) -> int | None:
    match = re.search(r"(?:\bS|第\s*)(\d{1,2})(?:\s*季|\b)", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _year(text: str) -> int | None:
    matches = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
    return int(matches[0]) if matches else None


def normalize_resource_metadata(item: Mapping[str, Any] | Any) -> dict:
    """返回 API/自动链路可复用的结构化资源字段。"""
    get = item.get if isinstance(item, Mapping) else lambda name, default="": getattr(item, name, default)
    url = get("share_url", "") or get("url", "") or get("magnet", "")
    title = get("resource_title", "") or get("title", "") or get("display_name", "")
    body = get("text", "") or ""
    content = " ".join(_text(part) for part in (title, body, get("meta", "")))
    pan_type = normalize_pan_type(url, get("pan_type", ""), content)
    resolution = _resolution(content)
    subtitle_type = _subtitle_type(content)
    is_remux = _match(content, r"(?<![\w])(?:remux|原盘|bdmv|blu[\s-]?ray\s+iso|uhd\s+blu[\s-]?ray\s+原盘)(?![\w])")
    is_complete = bool(get("is_complete", False)) or _match(content, r"完结|全集|全季|全\s*\d+\s*集")
    if pan_type == "magnet":
        quality = "remux" if is_remux else (
            "chs4k" if resolution == "4k" and subtitle_type != "none" else
            "chs1080p" if resolution == "1080p" and subtitle_type != "none" else resolution
        )
    else:
        quality = "unknown"
    return {
        "resource_kind": "magnet" if pan_type == "magnet" else "pan",
        "pan_type": pan_type,
        "resolution": resolution,
        "quality_class": quality,
        "has_chinese_subtitle": subtitle_type != "none",
        "subtitle_type": subtitle_type,
        "is_remux": is_remux,
        "is_complete": is_complete,
        "season": _season(content),
        "year": _year(content),
        "source": get("source", "") or get("_tg115_source", ""),
        "upstream_source": get("upstream_source", ""),
    }
