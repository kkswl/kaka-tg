# -*- coding: utf-8 -*-
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins.v2" / "tgsearch115" / "__init__.py"
MANUAL = ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue"
CONFIG = ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Config.vue"
PAGE = ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue"


class ManualVerifiedProcessContractTest(unittest.TestCase):
    def test_115_manual_transfer_uses_default_or_selected_directory_without_subscription(self):
        source = MANUAL.read_text(encoding="utf-8")
        self.assertIn("item.pan_type === '115' ? openManualTransferDialog(item) : openManualProcessDialog(item)", source)
        self.assertIn("绑定的默认目录", source)
        self.assertIn("转存到默认目录", source)
        self.assertIn("选择其他目录", source)
        self.assertIn("转存到此目录", source)
        transfer = source[source.index("async function submitManualTransfer"):source.index("async function loadManualSubscriptions")]
        self.assertIn("/manual/transfer", transfer)
        self.assertIn("buildManualTransferPayload(", transfer)
        self.assertIn("shareUrl,", transfer)
        self.assertNotIn("subscribe_id", transfer)
        self.assertNotIn("manualSubscribeId", transfer)

    def test_subscription_verified_flow_is_preserved_for_magnet_action(self):
        source = MANUAL.read_text(encoding="utf-8")
        self.assertIn("manualSubscribeId", source)
        self.assertIn("/manual/subscriptions", source)
        self.assertIn("/manual/process", source)
        transfer = source[source.index("async function submitManualResult"):source.index("watch([manualSource")]
        self.assertIn("confirm: true", transfer)
        self.assertNotIn("/magnet/offline", transfer)
        self.assertNotIn("/transfer?", transfer)

    def test_manual_transfer_backend_is_post_only_and_subscription_independent(self):
        source = PLUGIN.read_text(encoding="utf-8")
        self.assertIn('"path": "/manual/transfer"', source)
        route_start = source.index('"path": "/manual/transfer"')
        route_end = source.index("},", route_start)
        self.assertIn('"methods": ["POST"]', source[route_start:route_end])
        start = source.index("    def __manual_transfer_api")
        end = source.index("    def __manual_subscriptions_api", start)
        method = source[start:end]
        self.assertIn('payload.get("confirm") is not True', method)
        self.assertIn('payload.get("share_url")', method)
        self.assertIn('payload.get("target")', method)
        self.assertIn("self._transfer.transfer(share_url, target)", method)
        self.assertNotIn("请选择 115 目标目录", method)
        for forbidden in (
            "SubscribeOper", "subscribe_id", "_finish_subscribe", "_cms_tasks",
            "_magnet_queues", "_submit_magnet_to_115",
        ):
            self.assertNotIn(forbidden, method)

    def test_copy_link_has_clipboard_fallback_and_validates_complete_url(self):
        source = MANUAL.read_text(encoding="utf-8")
        self.assertIn("copyTextWithFallback", source)
        self.assertIn("isCopyableResourceUrl", source)
        copy = source[source.index("async function copyManualResult"):source.index("async function loadManualTransferDirectories")]
        self.assertIn("manualFullUrl(item).trim()", copy)
        self.assertIn("链接已复制", copy)
        self.assertIn("复制失败，请手动复制", copy)
        self.assertIn("该资源没有有效链接", copy)

    def test_backend_rechecks_rules_and_media_identity_before_side_effects(self):
        source = PLUGIN.read_text(encoding="utf-8")
        start = source.index("    def __manual_process_api")
        end = source.index("    def __transfer_api", start)
        method = source[start:end]
        for required in (
            'payload.get("confirm") is not True',
            "build_subscribe_meta(subscribe)",
            "self._filter_resources(subscribe, mediainfo, torrents)",
            "confirm_candidate_identity(",
            "if not identity.confirmed",
        ):
            self.assertIn(required, method)
        verify_at = method.index("if not identity.confirmed")
        transfer_at = method.index("self._transfer.transfer(")
        self.assertLess(verify_at, transfer_at)

    def test_magnet_configuration_lives_in_settings_tab(self):
        source = CONFIG.read_text(encoding="utf-8")
        settings = source[source.index('v-window-item value="settings"'):source.index('v-window-item value="site"')]
        site = source[source.index('v-window-item value="site"'):source.index('v-window-item value="pansou"')]
        for field in (
            "site_magnet_priority",
            "direct_timeout_hours",
            "offline_poll_seconds",
            "offline_max_retries",
            "magnet_failover_enabled",
            "magnet_max_attempts",
            "magnet_queue_timeout_hours",
            "magnet_download_wait_minutes",
            "magnet_rotation_unknown_timeout_minutes",
            "magnet_cancel_failover",
            "magnet_fallback_enabled",
            "wait_for_mp_organize",
            "offline_allow_cancel",
        ):
            self.assertIn(f"config.{field}", settings)
            self.assertNotIn(f"config.{field}", site)

    def test_page_has_safe_close_button(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn('aria-label="关闭"', source)
        self.assertIn("mdi-close", source)
        self.assertIn("window.history.back()", source)
        close_method = source[source.index("function closePage"):source.index("const PID")]
        self.assertIn("onClose", close_method)
        self.assertIn("onBack", close_method)
        self.assertIn("return", close_method)

    def test_transfer_complete_and_polling_terminal_contract(self):
        source = PLUGIN.read_text(encoding="utf-8")
        self.assertIn("@eventmanager.register(EventType.TransferComplete)", source)
        self.assertIn('self._complete_task_record(record, "MoviePilot 整理事件")', source)
        self.assertIn('self._complete_task_record(record, "MoviePilot 整理历史")', source)
        poll_filter = source[source.index('record.get("source") != "115_direct"'):source.index("task_id = record.get", source.index('record.get("source") != "115_direct"'))]
        self.assertNotIn("pending_organize", poll_filter)
        self.assertIn('queue["state"] = "completed"', source)
        self.assertIn("diagnose_transfer_complete", source)
        self.assertIn("_sync_task_timeline(completed, \"completed\"", source)
        self.assertIn("mp_history_match_status", source)
        self.assertIn('queue["owner"] = "none"', source)

    def test_settings_section_order(self):
        source = CONFIG.read_text(encoding="utf-8")
        settings = source[source.index('v-window-item value="settings"'):source.index('v-window-item value="site"')]
        positions = [settings.index(title) for title in (
            "插件基础设置",
            "115 基础配置",
            "115 磁力离线配置",
            "磁力候选轮换配置",
            "搜索与来源设置",
        )]
        self.assertEqual(sorted(positions), positions)

    def test_search_detail_notify_exists_in_settings_and_defaults(self):
        source = CONFIG.read_text(encoding="utf-8")
        settings = source[source.index('v-window-item value="settings"'):source.index('v-window-item value="site"')]
        self.assertIn("search_detail_notify", settings)
        self.assertIn("详细资源搜索通知", settings)
        defaults = source[source.index("const DEFAULTS"):]
        self.assertIn("search_detail_notify: false", defaults)

    def test_pansou_auto_search_uses_bounded_timeout(self):
        source = PLUGIN.read_text(encoding="utf-8")
        pansou_call = source[source.index('"pansou", lambda: self._pansou_client.search('):source.index(", self._pansou_client, year,")]
        self.assertIn("request_timeout=self._pansou_timeout", pansou_call)
        self.assertNotIn("request_timeout=25.0", pansou_call)
        self.assertNotIn("retry=False", pansou_call)

    def test_select_auto_candidates_has_rejection_collector(self):
        source = PLUGIN.read_text(encoding="utf-8")
        self.assertIn("rejection_collector=auto_rejections", source)
        self.assertIn("summarize_rejections(auto_rejections)", source)
        self.assertIn("format_rejection_detail(rejections)", source)

    def test_manual_transfer_logs_do_not_include_resource_url(self):
        source = PLUGIN.read_text(encoding="utf-8")
        start = source.index("    def __transfer_api")
        end = source.index("    def __magnet_offline_api", start)
        method = source[start:end]
        self.assertNotIn("{share_url}", method)
        self.assertNotIn("{target_path}", method)

    def test_manual_sources_run_in_parallel_with_bounded_collection(self):
        source = PLUGIN.read_text(encoding="utf-8")
        start = source.index("    def __search_api")
        end = source.index("    def __dir_info_api", start)
        method = source[start:end]
        self.assertIn("ThreadPoolExecutor", method)
        self.assertIn('"items": results', method)
        self.assertIn('"status": "partial_success"', method)
        self.assertIn("partial_result", method)
        self.assertIn("tg_search_enabled", method)
        self.assertIn("wait(futures, timeout=35.0)", method)
        self.assertIn("executor.shutdown(wait=False, cancel_futures=True)", method)
        self.assertIn("is_manual_relevant_result(", method)
        self.assertIn("returned_counts", method)
        self.assertIn('"source_stats"', method)
        self.assertIn('src not in {"all", "tg", "site", "pansou", "juying"}', method)


if __name__ == "__main__":
    unittest.main()
