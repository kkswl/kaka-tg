# -*- coding: utf-8 -*-
"""Reuse MoviePilot's native media recognition to confirm transfer candidates."""
from dataclasses import dataclass
from app.chain.media import MediaChain
from app.core.metainfo import MetaInfo
from app.helper.torrent import TorrentHelper
from app.log import logger


@dataclass
class IdentityResult:
    confirmed: bool
    match_source: str = "rejected"
    candidate_media_id: str = ""
    reason: str = ""
    recognition_attempted: bool = False


def _normalize_id(value) -> str:
    return str(value or "").strip()


def confirm_candidate_identity(subscribe, target_media, torrent) -> IdentityResult:
    """Confirm one candidate without causing download or subscription side effects."""
    identity_title = str(
        getattr(torrent, "_tg115_identity_title", "") or torrent.title or ""
    ).strip()
    if not identity_title:
        return IdentityResult(False, reason="候选缺少可识别标题")

    try:
        candidate_meta = MetaInfo(
            title=identity_title,
            subtitle=str(torrent.description or ""),
        )
    except Exception as e:
        return IdentityResult(False, reason=f"MetaInfo 解析失败: {e}")

    try:
        local_match = TorrentHelper.match_torrent(
            mediainfo=target_media,
            torrent_meta=candidate_meta,
            torrent=torrent,
        )
    except Exception as e:
        return IdentityResult(False, reason=f"本地身份初筛异常: {e}")
    if not local_match:
        return IdentityResult(False, reason="标题、别名、年份或媒体类型不匹配")

    target_type = getattr(target_media, "type", None)
    if getattr(target_type, "value", target_type) in ("电视剧", "TV"):
        expected_season = getattr(subscribe, "season", None)
        if expected_season is None:
            expected_season = getattr(target_media, "season", None)
        expected_season = int(expected_season or 1)
        season_list = list(getattr(candidate_meta, "season_list", None) or [])
        if len(season_list) > 1:
            return IdentityResult(False, reason=f"候选包含多季: {season_list}")
        candidate_season = getattr(candidate_meta, "begin_season", None)
        candidate_season = int(candidate_season if candidate_season is not None else 1)
        if candidate_season != expected_season:
            return IdentityResult(
                False,
                reason=f"季号不匹配: 需要 S{expected_season:02d}，候选 S{candidate_season:02d}",
            )

    target_tmdb = _normalize_id(
        getattr(subscribe, "tmdbid", None) or getattr(target_media, "tmdb_id", None)
    )
    target_douban = _normalize_id(
        getattr(subscribe, "doubanid", None) or getattr(target_media, "douban_id", None)
    )
    if not target_tmdb and not target_douban:
        return IdentityResult(False, reason="订阅缺少 TMDB/豆瓣 ID，禁止自动转存")

    try:
        candidate_media = MediaChain().recognize_by_meta(
            candidate_meta,
            episode_group=getattr(subscribe, "episode_group", None),
            obtain_images=False,
        )
    except Exception as e:
        logger.warn(f"【TG115】MoviePilot 候选媒体识别异常: {e}")
        return IdentityResult(
            False,
            reason=f"MoviePilot 媒体识别异常: {e}",
            recognition_attempted=True,
        )
    if not candidate_media:
        return IdentityResult(
            False, reason="MoviePilot 无法识别候选媒体", recognition_attempted=True
        )

    if getattr(candidate_media, "type", None) != target_type:
        return IdentityResult(
            False, reason="候选媒体类型与订阅不一致", recognition_attempted=True
        )

    candidate_tmdb = _normalize_id(getattr(candidate_media, "tmdb_id", None))
    if target_tmdb:
        if candidate_tmdb == target_tmdb:
            return IdentityResult(
                True, "tmdb_id", candidate_tmdb, "TMDB ID 一致",
                recognition_attempted=True,
            )
        return IdentityResult(
            False,
            candidate_media_id=candidate_tmdb,
            reason=f"TMDB ID 不匹配: 需要 {target_tmdb}，候选 {candidate_tmdb or '无'}",
            recognition_attempted=True,
        )

    candidate_douban = _normalize_id(getattr(candidate_media, "douban_id", None))
    if target_douban:
        if candidate_douban == target_douban:
            return IdentityResult(
                True, "douban_id", candidate_douban, "豆瓣 ID 一致",
                recognition_attempted=True,
            )
        return IdentityResult(
            False,
            candidate_media_id=candidate_douban,
            reason=f"豆瓣 ID 不匹配: 需要 {target_douban}，候选 {candidate_douban or '无'}",
            recognition_attempted=True,
        )

    return IdentityResult(False, reason="候选缺少可比较的媒体 ID", recognition_attempted=True)
