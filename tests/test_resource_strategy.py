import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins.v2"
    / "tgsearch115"
    / "resource_strategy.py"
)
spec = importlib.util.spec_from_file_location("tgsearch115_resource_strategy", MODULE_PATH)
resource_strategy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = resource_strategy
spec.loader.exec_module(resource_strategy)


def _torrent(url, pan_type, source="site", complete=True, text="中文字幕"):
    return SimpleNamespace(
        page_url=url,
        site_name={"site": "观影", "juying": "聚影"}.get(source, "TG频道"),
        title=text,
        description=text,
        _tg115_source=source,
        _tg115_pan_type=pan_type,
        _tg115_is_complete=complete,
    )


def _is_115(url):
    return "115.com/" in url


class ResourceStrategyTest(unittest.TestCase):
    def test_magnet_seed_count_does_not_block_server_side_offline_filter(self):
        magnet = _torrent(
            "magnet:?xt=urn:btih:" + "0" * 40,
            "magnet",
            text="1080P 中文字幕",
        )
        share = _torrent("https://115.com/s/demo", "115")
        magnet.seeders = 0
        share.seeders = 0

        def mp_rules(items):
            return [item for item in items if item.seeders >= 5]

        result = resource_strategy.filter_with_offline_seed_override(
            [magnet, share], mp_rules
        )

        self.assertEqual([magnet], result)
        self.assertEqual(0, magnet.seeders)
        self.assertEqual(0, share.seeders)

    def test_resource_classification_uses_115_only_actions(self):
        magnet = _torrent(
            "magnet:?xt=urn:btih:" + "0" * 40,
            "magnet",
            text="藏海传 S01 E01-E40 2160p WEB-DL H.265 简中 HDR10",
        )
        classification = resource_strategy.classify_resource(
            magnet,
            media_type="tv",
            identity_status="confirmed",
            mp_rule_status="passed",
        )
        self.assertEqual("magnet", classification["resource_type"])
        self.assertEqual("2160p", classification["resolution"])
        self.assertEqual("WEB-DL", classification["quality"])
        self.assertEqual("H.265", classification["video_codec"])
        self.assertEqual("简中", classification["subtitle"])
        self.assertEqual("submit_115", classification["action"])
        self.assertNotIn("cms", resource_strategy.format_resource_classification(classification).lower())

    def test_orders_direct_sources_then_pansou_then_magnets_then_juying(self):
        magnet = "magnet:?xt=urn:btih:" + "a" * 40
        torrents = [
            _torrent("https://115.com/s/juying", "115", source="juying"),
            _torrent(magnet, "magnet", text="1080P 中文字幕"),
            _torrent(magnet + "&dn=duplicate", "magnet", text="1080P 中文字幕"),
            _torrent("https://115.com/s/site", "115"),
            _torrent("https://115.com/s/pansou", "115", source="pansou"),
            _torrent("magnet:?xt=urn:btih:" + "9" * 40, "magnet", source="pansou", text="1080P 中文字幕"),
            _torrent("https://115.com/s/tg", "115", source="tg", text="频道资源"),
        ]

        selected = resource_strategy.select_auto_candidates(
            torrents, True, False, _is_115
        )

        self.assertEqual([
            "https://115.com/s/tg",
            "https://115.com/s/site",
            "https://115.com/s/pansou",
            magnet,
            "magnet:?xt=urn:btih:" + "9" * 40,
            "https://115.com/s/juying",
        ], [t.page_url for t in selected])

    def test_guanying_candidates_require_chinese_subtitle_marker(self):
        # 115 分享无中字标记进入 pending 桶（延迟中字检测），磁力无中字标记被拒绝
        selected = resource_strategy.select_auto_candidates([
            _torrent("https://115.com/s/no-chs", "115", text="WEB-DL English"),
            _torrent("magnet:?xt=urn:btih:" + "f" * 40, "magnet", text="WEB-DL English"),
            _torrent("https://115.com/s/chs", "115", text="内封简繁字幕"),
        ], True, False, _is_115)
        urls = [t.page_url for t in selected]
        # 已确认中字 115 分享排第一
        self.assertEqual("https://115.com/s/chs", urls[0])
        # 待确认中字 115 分享排第二
        self.assertEqual("https://115.com/s/no-chs", urls[1])
        # 磁力候选无中字标记被拒绝
        self.assertNotIn("magnet:?xt=urn:btih:" + "f" * 40, urls)
        self.assertTrue(getattr(selected[1], "_tg115_subtitle_pending", False))

    def test_auto_magnet_requires_chinese_1080p_or_4k(self):
        selected = resource_strategy.select_auto_candidates([
            _torrent("magnet:?xt=urn:btih:" + "1" * 40, "magnet", text="720P 中文字幕"),
            _torrent("magnet:?xt=urn:btih:" + "2" * 40, "magnet", text="1080P English"),
            _torrent("magnet:?xt=urn:btih:" + "3" * 40, "magnet", text="1080P 中文字幕"),
            _torrent("magnet:?xt=urn:btih:" + "4" * 40, "magnet", text="4K 简中"),
        ], True, False, _is_115)
        self.assertEqual([
            "magnet:?xt=urn:btih:" + "3" * 40,
            "magnet:?xt=urn:btih:" + "4" * 40,
        ], [item.page_url for item in selected])

    def test_chinese_word_marker_is_accepted_for_site_magnet(self):
        selected = resource_strategy.select_auto_candidates([
            _torrent("magnet:?xt=urn:btih:" + "5" * 40, "magnet", text="S03 2026 4K 中文 完整季"),
        ], True, False, _is_115)
        self.assertEqual(1, len(selected))

    def test_cross_source_duplicate_keeps_higher_priority_tg_candidate(self):
        duplicate = "https://115.com/s/same"
        selected = resource_strategy.select_auto_candidates([
            _torrent(duplicate, "115", source="juying"),
            _torrent(duplicate, "115", source="tg", text="频道资源"),
        ], True, False, _is_115)
        self.assertEqual(1, len(selected))
        self.assertEqual("tg", selected[0]._tg115_source)

    def test_rejects_incomplete_tv_magnet(self):
        torrents = [
            _torrent("magnet:?xt=urn:btih:" + "b" * 40, "magnet", complete=False),
            _torrent("https://115.com/s/demo", "115"),
        ]

        selected = resource_strategy.select_auto_candidates(
            torrents, True, True, _is_115
        )

        self.assertEqual(["https://115.com/s/demo"], [t.page_url for t in selected])

    def test_ignores_non_guanying_magnet(self):
        selected = resource_strategy.select_auto_candidates(
            [_torrent("magnet:?xt=urn:btih:" + "c" * 40, "magnet", source="juying")],
            True,
            False,
            _is_115,
        )

        self.assertEqual([], selected)

    def test_cms_failure_continues_with_115_share(self):
        candidates = [
            _torrent("magnet:?xt=urn:btih:" + "d" * 40, "magnet"),
            _torrent("magnet:?xt=urn:btih:" + "e" * 40, "magnet"),
            _torrent("https://115.com/s/fallback", "115"),
        ]
        submitted_magnets = []
        transferred_shares = []

        result = resource_strategy.execute_auto_candidates(
            candidates=candidates,
            confirm_identity=lambda _candidate: SimpleNamespace(
                confirmed=True, recognition_attempted=True
            ),
            submit_magnet=lambda candidate: (
                submitted_magnets.append(candidate.page_url) or False,
                "CMS unavailable",
            ),
            transfer_share=lambda candidate: (
                transferred_shares.append(candidate.page_url) or True,
                "transferred",
            ),
        )

        self.assertEqual(2, len(submitted_magnets))
        self.assertEqual(["https://115.com/s/fallback"], transferred_shares)
        self.assertEqual("https://115.com/s/fallback", result.candidate.page_url)
        self.assertFalse(result.via_magnet)

    def test_first_magnet_failure_submits_second_candidate(self):
        first = _torrent("magnet:?xt=urn:btih:" + "1" * 40, "magnet")
        second = _torrent("magnet:?xt=urn:btih:" + "2" * 40, "magnet")
        submitted = []

        def submit(candidate):
            submitted.append(candidate.page_url)
            return (len(submitted) == 2, "submitted" if len(submitted) == 2 else "cancelled")

        result = resource_strategy.execute_auto_candidates(
            candidates=[first, second],
            confirm_identity=lambda _candidate: SimpleNamespace(
                confirmed=True, recognition_attempted=True
            ),
            submit_magnet=submit,
            transfer_share=lambda _candidate: (False, "unexpected"),
        )

        self.assertEqual([first.page_url, second.page_url], submitted)
        self.assertIs(second, result.candidate)
        self.assertTrue(result.via_magnet)
        self.assertEqual(2, second._tg115_candidate_position)
        self.assertEqual(2, second._tg115_candidate_total)

    def test_identity_unavailable_does_not_submit_or_transfer(self):
        candidate = _torrent("https://115.com/s/unavailable", "115")
        submitted = []
        transferred = []

        result = resource_strategy.execute_auto_candidates(
            candidates=[candidate],
            confirm_identity=lambda _candidate: SimpleNamespace(
                confirmed=False,
                recognition_attempted=True,
                reason="MoviePilot 媒体识别暂不可用",
            ),
            submit_magnet=lambda item: submitted.append(item) or (True, "unexpected"),
            transfer_share=lambda item: transferred.append(item) or (True, "unexpected"),
        )

        self.assertIsNone(result.candidate)
        self.assertEqual([], submitted)
        self.assertEqual([], transferred)

    def test_identity_rejection_is_summarized_without_candidate_title(self):
        candidate = _torrent("https://115.com/s/unavailable", "115")
        result = resource_strategy.execute_auto_candidates(
            candidates=[candidate],
            confirm_identity=lambda _candidate: SimpleNamespace(
                confirmed=False,
                recognition_attempted=True,
                match_source="rejected",
                reason="TMDB ID 不匹配: 需要 1，候选 2",
            ),
            submit_magnet=lambda _item: (True, "unexpected"),
            transfer_share=lambda _item: (True, "unexpected"),
        )

        self.assertEqual("TMDB ID 不一致", result.rejection_summary())
        self.assertNotIn("需要", result.rejection_summary())

    # ----- TV season-pack vs single-episode magnet tests -----

    def test_tv_season_pack_magnet_passes_without_complete_flag(self):
        """S05 without Exx should pass for TV even when _tg115_is_complete=False."""
        magnet = _torrent(
            "magnet:?xt=urn:btih:" + "a" * 40,
            "magnet",
            source="pansou",
            complete=False,
            text="Stranger.Things.S05.1080P.WEB-DL 中字",
        )
        rejections = []
        selected = resource_strategy.select_auto_candidates(
            [magnet], True, True, _is_115,
            rejection_collector=rejections,
        )
        self.assertEqual([magnet.page_url], [t.page_url for t in selected])
        self.assertEqual([], rejections)

    def test_tv_single_episode_magnet_is_rejected(self):
        """S05E01 should be rejected for TV."""
        magnet = _torrent(
            "magnet:?xt=urn:btih:" + "b" * 40,
            "magnet",
            source="pansou",
            complete=False,
            text="Stranger.Things.S05E01.1080P.WEB-DL 中字",
        )
        rejections = []
        selected = resource_strategy.select_auto_candidates(
            [magnet], True, True, _is_115,
            rejection_collector=rejections,
        )
        self.assertEqual([], selected)
        self.assertEqual(1, len(rejections))
        self.assertIn("单集", rejections[0]["reason"])

    def test_tv_explicit_complete_magnet_passes(self):
        """Magnets with 完结/全集/全季 should pass for TV."""
        magnet = _torrent(
            "magnet:?xt=urn:btih:" + "c" * 40,
            "magnet",
            source="pansou",
            complete=True,
            text="怪奇物语 第五季 全集 1080P 中字",
        )
        selected = resource_strategy.select_auto_candidates(
            [magnet], True, True, _is_115,
        )
        self.assertEqual([magnet.page_url], [t.page_url for t in selected])

    def test_tv_chinese_season_pack_passes(self):
        """第X季 format without Exx should pass for TV."""
        magnet = _torrent(
            "magnet:?xt=urn:btih:" + "d" * 40,
            "magnet",
            source="pansou",
            complete=False,
            text="怪奇物语.第五季.1080P.WEB-DL.中字",
        )
        selected = resource_strategy.select_auto_candidates(
            [magnet], True, True, _is_115,
        )
        self.assertEqual([magnet.page_url], [t.page_url for t in selected])

    def test_115_share_without_chinese_subtitle_marked_pending(self):
        share = _torrent(
            "https://115.com/s/test123",
            "115",
            source="pansou",
            text="Stranger.Things.S05.1080P.WEB-DL",
        )
        rejections = []
        selected = resource_strategy.select_auto_candidates(
            [share], True, True, _is_115,
            rejection_collector=rejections,
        )
        # 延迟中字检测：不立即拒绝，标记为 pending 并进入候选列表
        self.assertEqual([share.page_url], [t.page_url for t in selected])
        self.assertTrue(getattr(selected[0], "_tg115_subtitle_pending", False))
        self.assertEqual([], rejections)

    def test_115_share_with_chinese_subtitle_passes_without_resolution_check(self):
        share = _torrent(
            "https://115.com/s/test456",
            "115",
            source="pansou",
            text="怪奇物语 第五季 720P 中字",
        )
        selected = resource_strategy.select_auto_candidates(
            [share], True, True, _is_115,
        )
        self.assertEqual([share.page_url], [t.page_url for t in selected])

    def test_summarize_rejections_all_same_reason(self):
        rejections = [
            {"source": "pansou", "type": "磁力", "title": "A", "reason": "未检测到中文字幕标记"},
            {"source": "pansou", "type": "磁力", "title": "B", "reason": "未检测到中文字幕标记"},
        ]
        reason = resource_strategy.summarize_rejections(rejections)
        self.assertIn("中文字幕", reason)
        self.assertNotIn("1080P", reason)

    def test_summarize_rejections_mixed_reasons(self):
        rejections = [
            {"source": "pansou", "type": "磁力", "title": "A", "reason": "未检测到中文字幕标记"},
            {"source": "pansou", "type": "磁力", "title": "B", "reason": "单集磁力，非整季资源"},
        ]
        reason = resource_strategy.summarize_rejections(rejections)
        self.assertIn("自动策略", reason)

    def test_format_rejection_detail_truncates_to_max_items(self):
        rejections = [
            {"source": "pansou", "type": "磁力", "title": f"Title{i}", "reason": "测试"}
            for i in range(15)
        ]
        detail = resource_strategy.format_rejection_detail(rejections, max_items=3)
        self.assertIn("共 15 条", detail)
        self.assertIn("前 3 条", detail)
        self.assertIn("及其它 12 条", detail)
        self.assertNotIn("Title10", detail)

    def test_format_rejection_detail_empty(self):
        self.assertEqual("", resource_strategy.format_rejection_detail([]))

    def test_rejection_detail_does_not_leak_magnet_or_share_code(self):
        rejections = [
            {"source": "pansou", "type": "磁力", "title": "Test", "reason": "测试"},
        ]
        detail = resource_strategy.format_rejection_detail(rejections)
        self.assertNotIn("magnet:?", detail)
        self.assertNotIn("115.com", detail)

    # ----- 115 share subtitle file detection tests -----

    def test_has_chinese_subtitle_file_detects_chs_srt(self):
        self.assertTrue(resource_strategy.has_chinese_subtitle_file([
            "Movie.2023.1080p.mkv",
            "Movie.2023.chs.srt",
        ]))

    def test_has_chinese_subtitle_file_detects_chinese_ass(self):
        self.assertTrue(resource_strategy.has_chinese_subtitle_file([
            "Stranger.Things.S05.mkv",
            "简体中文.ass",
        ]))

    def test_has_chinese_subtitle_file_detects_cht_sub(self):
        self.assertTrue(resource_strategy.has_chinese_subtitle_file([
            "Movie.cht.sub",
        ]))

    def test_has_chinese_subtitle_file_rejects_english_only_srt(self):
        self.assertFalse(resource_strategy.has_chinese_subtitle_file([
            "Movie.2023.1080p.mkv",
            "Movie.2023.en.srt",
        ]))

    def test_has_chinese_subtitle_file_rejects_no_subtitle_files(self):
        self.assertFalse(resource_strategy.has_chinese_subtitle_file([
            "Movie.2023.1080p.mkv",
            "Movie.2023.1080p.nfo",
        ]))

    def test_has_chinese_subtitle_file_rejects_empty_list(self):
        self.assertFalse(resource_strategy.has_chinese_subtitle_file([]))

    def test_115_share_passes_with_subtitle_file_but_no_title_marker(self):
        """115 share without 中字 in title but with chs.srt in file list should pass."""
        share = _torrent(
            "https://115.com/s/test789",
            "115",
            source="pansou",
            text="Stranger.Things.S05.1080P.WEB-DL",
        )
        setattr(share, "_tg115_has_chinese_sub_file", True)
        selected = resource_strategy.select_auto_candidates(
            [share], True, True, _is_115,
        )
        self.assertEqual([share.page_url], [t.page_url for t in selected])

    def test_115_share_marked_pending_without_title_marker_and_without_sub_file(self):
        """115 share without 中字 in title and no sub file is marked pending."""
        share = _torrent(
            "https://115.com/s/test000",
            "115",
            source="pansou",
            text="Stranger.Things.S05.1080P.WEB-DL",
        )
        rejections = []
        selected = resource_strategy.select_auto_candidates(
            [share], True, True, _is_115,
            rejection_collector=rejections,
        )
        # 延迟中字检测：不立即拒绝，标记为 pending
        self.assertEqual([share.page_url], [t.page_url for t in selected])
        self.assertTrue(getattr(selected[0], "_tg115_subtitle_pending", False))
        self.assertEqual([], rejections)


class PendingSubtitleExecutionTest(unittest.TestCase):
    """回归测试：115 分享延迟中字检测与执行路径。"""

    def _share(self, url, text="Stranger.Things.S05.1080P.WEB-DL", pending=False):
        t = _torrent(url, "115", source="pansou", text=text)
        if pending:
            setattr(t, "_tg115_subtitle_pending", True)
        return t

    def _confirmed_identity(self, _candidate):
        return SimpleNamespace(confirmed=True, recognition_attempted=True)

    # 测试 1：115 分享标题含中字标记 → 进入 pansou_share 桶
    def test_share_with_chinese_subtitle_marker_enters_share_bucket(self):
        share = self._share("https://115.com/s/chs-marker", text="怪奇物语 第五季 中字")
        selected = resource_strategy.select_auto_candidates([share], True, True, _is_115)
        self.assertEqual([share.page_url], [t.page_url for t in selected])
        self.assertFalse(getattr(selected[0], "_tg115_subtitle_pending", False))

    # 测试 2：115 分享标题无中字标记但 _tg115_has_chinese_sub_file=True → 进入 pansou_share 桶
    def test_share_with_sub_file_enters_share_bucket(self):
        share = self._share("https://115.com/s/sub-file", text="Stranger.Things.S05.1080P")
        setattr(share, "_tg115_has_chinese_sub_file", True)
        selected = resource_strategy.select_auto_candidates([share], True, True, _is_115)
        self.assertEqual([share.page_url], [t.page_url for t in selected])
        self.assertFalse(getattr(selected[0], "_tg115_subtitle_pending", False))

    # 测试 3：115 分享标题无中字标记且未探测 → 标记 _tg115_subtitle_pending
    def test_share_without_marker_marked_pending(self):
        share = self._share("https://115.com/s/pending")
        selected = resource_strategy.select_auto_candidates([share], True, True, _is_115)
        self.assertEqual([share.page_url], [t.page_url for t in selected])
        self.assertTrue(getattr(selected[0], "_tg115_subtitle_pending", False))

    # 测试 4：_tg115_subtitle_pending 候选排在已确认中字候选之后
    def test_pending_share_ranks_after_confirmed_share(self):
        confirmed = self._share("https://115.com/s/confirmed", text="怪奇物语 中字")
        pending = self._share("https://115.com/s/pending")
        selected = resource_strategy.select_auto_candidates(
            [pending, confirmed], True, True, _is_115
        )
        urls = [t.page_url for t in selected]
        self.assertEqual(["https://115.com/s/confirmed", "https://115.com/s/pending"], urls)

    # 测试 5：execute_auto_candidates 中已确认中字候选优先转存
    def test_confirmed_share_transferred_first(self):
        confirmed = self._share("https://115.com/s/confirmed", text="怪奇物语 中字")
        pending = self._share("https://115.com/s/pending")
        transferred = []
        inspect_calls = []

        def transfer_share(candidate):
            transferred.append(candidate.page_url)
            return (True, "transferred")

        def inspect_share(candidate):
            inspect_calls.append(candidate.page_url)
            return (True, "ok", ["Movie.chs.srt"])

        result = resource_strategy.execute_auto_candidates(
            candidates=[confirmed, pending],
            confirm_identity=self._confirmed_identity,
            submit_magnet=lambda _c: (True, "unexpected"),
            transfer_share=transfer_share,
            inspect_share=inspect_share,
        )
        self.assertEqual(["https://115.com/s/confirmed"], transferred)
        # 已确认中字候选成功，不调用 inspect_share
        self.assertEqual([], inspect_calls)
        self.assertEqual("https://115.com/s/confirmed", result.candidate.page_url)

    # 测试 6：已确认中字全部失败后才尝试 _tg115_subtitle_pending 候选
    def test_pending_share_attempted_after_confirmed_failure(self):
        confirmed = self._share("https://115.com/s/confirmed", text="怪奇物语 中字")
        pending = self._share("https://115.com/s/pending", pending=True)
        transfer_order = []

        def transfer_share(candidate):
            transfer_order.append(candidate.page_url)
            if candidate.page_url == "https://115.com/s/confirmed":
                return (False, "分享不可用")
            return (True, "transferred")

        def inspect_share(candidate):
            return (True, "ok", ["Movie.chs.srt"])

        result = resource_strategy.execute_auto_candidates(
            candidates=[confirmed, pending],
            confirm_identity=self._confirmed_identity,
            submit_magnet=lambda _c: (True, "unexpected"),
            transfer_share=transfer_share,
            inspect_share=inspect_share,
        )
        # 已确认先尝试失败，再尝试 pending
        self.assertEqual(
            ["https://115.com/s/confirmed", "https://115.com/s/pending"], transfer_order
        )
        self.assertEqual("https://115.com/s/pending", result.candidate.page_url)

    # 测试 7：_tg115_subtitle_pending 候选在 inspect_share 探测到中字文件后正常转存
    def test_pending_share_transferred_after_inspect_detects_sub_file(self):
        pending = self._share("https://115.com/s/pending", pending=True)
        inspect_calls = []
        transferred = []

        def transfer_share(candidate):
            transferred.append(candidate.page_url)
            return (True, "transferred")

        def inspect_share(candidate):
            inspect_calls.append(candidate.page_url)
            return (True, "ok", ["Stranger.Things.S05.mkv", "Stranger.Things.S05.chs.srt"])

        result = resource_strategy.execute_auto_candidates(
            candidates=[pending],
            confirm_identity=self._confirmed_identity,
            submit_magnet=lambda _c: (True, "unexpected"),
            transfer_share=transfer_share,
            inspect_share=inspect_share,
        )
        self.assertEqual(["https://115.com/s/pending"], inspect_calls)
        self.assertEqual(["https://115.com/s/pending"], transferred)
        self.assertEqual("https://115.com/s/pending", result.candidate.page_url)

    # 测试 8：_tg115_subtitle_pending 候选在 inspect_share 未检测到中字文件后跳过
    def test_pending_share_skipped_when_no_sub_file_detected(self):
        pending = self._share("https://115.com/s/pending", pending=True)
        transferred = []

        def transfer_share(candidate):
            transferred.append(candidate.page_url)
            return (True, "unexpected")

        def inspect_share(candidate):
            return (True, "ok", ["Stranger.Things.S05.mkv", "Stranger.Things.S05.en.srt"])

        result = resource_strategy.execute_auto_candidates(
            candidates=[pending],
            confirm_identity=self._confirmed_identity,
            submit_magnet=lambda _c: (False, "no magnet"),
            transfer_share=transfer_share,
            inspect_share=inspect_share,
        )
        # 未检测到中字文件，跳过，不转存
        self.assertEqual([], transferred)
        self.assertIsNone(result.candidate)

    # 测试 9：inspect_share 失败时不当作转存失败
    def test_inspect_share_failure_does_not_count_as_transfer_failure(self):
        pending = self._share("https://115.com/s/pending", pending=True)
        transferred = []
        transfer_failures = []

        def transfer_share(candidate):
            transferred.append(candidate.page_url)
            return (True, "unexpected")

        def inspect_share(candidate):
            return (False, "Cookie 失效", [])

        result = resource_strategy.execute_auto_candidates(
            candidates=[pending],
            confirm_identity=self._confirmed_identity,
            submit_magnet=lambda _c: (False, "no magnet"),
            transfer_share=transfer_share,
            inspect_share=inspect_share,
        )
        # inspect_share 失败，跳过候选，不调用 transfer_share，不计入 errors
        self.assertEqual([], transferred)
        self.assertIsNone(result.candidate)
        # inspect_share 失败不应产生 115 转存失败错误
        self.assertFalse(any("115 转存失败" in e for e in result.errors))

    # 测试 10：115 分享缺少提取码时记录明确日志（通过转存失败原因体现）
    def test_share_missing_receive_code_logs_failure_reason(self):
        share = self._share("https://115.com/s/no-code", text="怪奇物语 中字")
        transfer_calls = []

        def transfer_share(candidate):
            transfer_calls.append(candidate.page_url)
            return (False, "解析 115 分享链接失败，缺少分享码或提取码")

        result = resource_strategy.execute_auto_candidates(
            candidates=[share],
            confirm_identity=self._confirmed_identity,
            submit_magnet=lambda _c: (True, "unexpected"),
            transfer_share=transfer_share,
            inspect_share=lambda _c: (True, "ok", []),
        )
        self.assertEqual(["https://115.com/s/no-code"], transfer_calls)
        # 失败原因应被记录到 errors
        self.assertTrue(any("缺少分享码或提取码" in e for e in result.errors))
        self.assertIsNone(result.candidate)

    # 测试 11：max_probes 提升后更多 115 分享被探测（验证默认值 >= 10）
    def test_max_probes_default_is_at_least_10(self):
        # 读取 __init__.py 源码，验证 _enrich_share_metadata 的 max_probes 默认值
        init_path = (
            Path(__file__).resolve().parents[1]
            / "plugins.v2"
            / "tgsearch115"
            / "__init__.py"
        )
        source = init_path.read_text(encoding="utf-8")
        import re as _re
        match = _re.search(r"def _enrich_share_metadata\(.*?max_probes:\s*int\s*=\s*(\d+)", source)
        self.assertIsNotNone(match, "_enrich_share_metadata 必须定义 max_probes 参数")
        self.assertGreaterEqual(int(match.group(1)), 10,
                                "max_probes 默认值必须 >= 10 以覆盖更多 115 分享")

    # 测试 12：115 分享全部失败后回退到磁力候选
    def test_falls_back_to_magnet_after_all_shares_fail(self):
        share = self._share("https://115.com/s/fail", text="怪奇物语 中字")
        magnet = _torrent(
            "magnet:?xt=urn:btih:" + "a" * 40, "magnet", text="1080P 中文字幕"
        )
        submitted_magnets = []

        def transfer_share(_candidate):
            return (False, "分享不可用")

        def submit_magnet(candidate):
            submitted_magnets.append(candidate.page_url)
            return (True, "115 磁力任务已提交")

        result = resource_strategy.execute_auto_candidates(
            candidates=[share, magnet],
            confirm_identity=self._confirmed_identity,
            submit_magnet=submit_magnet,
            transfer_share=transfer_share,
            inspect_share=lambda _c: (True, "ok", ["x.chs.srt"]),
        )
        self.assertEqual([magnet.page_url], submitted_magnets)
        self.assertEqual(magnet.page_url, result.candidate.page_url)
        self.assertTrue(result.via_magnet)

    # 测试 13：日志包含 115 分享转存诊断信息（通过 errors 和 result 验证）
    def test_diagnostic_info_available_in_result(self):
        confirmed = self._share("https://115.com/s/confirmed", text="怪奇物语 中字")
        pending = self._share("https://115.com/s/pending", pending=True)
        # 已确认失败，pending 探测失败，最终回退磁力
        magnet = _torrent(
            "magnet:?xt=urn:btih:" + "b" * 40, "magnet", text="1080P 中文字幕"
        )

        def transfer_share(_candidate):
            return (False, "分享不可用")

        def inspect_share(_candidate):
            return (False, "Cookie 失效", [])

        result = resource_strategy.execute_auto_candidates(
            candidates=[confirmed, pending, magnet],
            confirm_identity=self._confirmed_identity,
            submit_magnet=lambda _c: (True, "115 磁力任务已提交"),
            transfer_share=transfer_share,
            inspect_share=inspect_share,
        )
        # 已确认中字失败 → errors 包含转存失败
        self.assertTrue(any("115 转存失败" in e for e in result.errors))
        # pending 探测失败不计入 errors，最终磁力成功
        self.assertEqual(magnet.page_url, result.candidate.page_url)
        self.assertTrue(result.via_magnet)


if __name__ == "__main__":
    unittest.main()
