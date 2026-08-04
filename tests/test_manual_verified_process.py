# -*- coding: utf-8 -*-
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins.v2" / "tgsearch115" / "__init__.py"
MANUAL = ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "ManualSearch.vue"


class ManualVerifiedProcessContractTest(unittest.TestCase):
    def test_frontend_requires_subscription_and_uses_verified_endpoint(self):
        source = MANUAL.read_text(encoding="utf-8")
        self.assertIn("subscribeId", source)
        self.assertIn("/manual/subscriptions", source)
        self.assertIn("/manual/process", source)
        transfer = source[source.index("async function transfer"):source.index("async function loadSubscriptions")]
        self.assertIn("confirm: true", transfer)
        self.assertNotIn("/magnet/offline", transfer)
        self.assertNotIn("/transfer?", transfer)

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
        self.assertIn("wait(futures, timeout=35.0)", method)
        self.assertIn("executor.shutdown(wait=False, cancel_futures=True)", method)
        self.assertIn("is_manual_relevant_result(", method)
        self.assertIn("returned_counts", method)
        self.assertIn('"source_stats"', method)
        self.assertIn('src not in {"all", "tg", "site", "pansou", "juying"}', method)


if __name__ == "__main__":
    unittest.main()
