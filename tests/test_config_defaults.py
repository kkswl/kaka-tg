import ast
import unittest
from pathlib import Path


PLUGIN_PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "__init__.py"


class ConfigDefaultsTest(unittest.TestCase):
    def test_plugin_startup_uses_ttl_cache_public_constructor_arguments(self):
        """启动初始化不得传入不存在的 TtlCache 参数而导致插件无法加载。"""
        source = PLUGIN_PATH.read_text(encoding="utf-8")
        self.assertIn("TtlCache(ttl_seconds=6 * 3600, max_entries=256)", source)
        self.assertNotIn("TtlCache(ttl_seconds=6 * 3600, maxsize=256)", source)

    def test_v460_defaults_are_available_for_old_configs(self):
        tree = ast.parse(PLUGIN_PATH.read_text(encoding="utf-8"))
        defaults = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_default_config":
                return_node = next(
                    child for child in ast.walk(node) if isinstance(child, ast.Return)
                )
                defaults = ast.literal_eval(return_node.value)
                break

        self.assertIsNotNone(defaults)
        self.assertTrue(defaults["periodic_enabled"])
        self.assertEqual(2, defaults["period_hours"])
        self.assertEqual(10, defaults["jitter_minutes"])
        self.assertEqual(75, defaults["source_request_timeout_seconds"])
        self.assertEqual(90, defaults["auto_search_budget_seconds"])
        self.assertEqual(2, defaults["tg_concurrency"])
        self.assertNotIn("cms_url", defaults)
        self.assertNotIn("cms_token", defaults)
        self.assertNotIn("cms_timeout_hours", defaults)
        self.assertEqual("direct_115", defaults["magnet_download_mode"])
        self.assertTrue(defaults["wait_for_mp_organize"])
        self.assertFalse(defaults["auto_finish"])
        self.assertTrue(defaults["pansou_enabled"])
        self.assertTrue(defaults["tg_search_enabled"])
        self.assertEqual("http://192.168.1.15:8888", defaults["pansou_url"])
        self.assertEqual("", defaults["pansou_proxy"])
        self.assertEqual(60, defaults["pansou_timeout"])
        self.assertEqual(["115", "magnet"], defaults["pansou_cloud_types"])
        self.assertEqual(100, defaults["pansou_max_results"])
        self.assertTrue(defaults["magnet_failover_enabled"])
        self.assertEqual(5, defaults["magnet_max_attempts"])
        self.assertEqual(1, defaults["magnet_download_wait_minutes"])
        self.assertEqual(12, defaults["magnet_queue_timeout_hours"])
        self.assertTrue(defaults["magnet_cancel_failover"])
        self.assertEqual(20, defaults["magnet_rotation_unknown_timeout_minutes"])
        self.assertTrue(defaults["magnet_fallback_enabled"])
        self.assertFalse(defaults["search_detail_notify"])

    def test_timeout_migration_covers_the_replaced_defaults(self):
        source = PLUGIN_PATH.read_text(encoding="utf-8")
        init = source[source.index("def init_plugin"):source.index("def _save_diagnostics")]
        self.assertIn('"auto_search_budget_seconds": (60, 180, 300)', init)
        self.assertIn('"source_request_timeout_seconds": (20, 30, 60)', init)
        self.assertIn('"pansou_timeout": (20, 120, 300)', init)

    def test_apply_config_derives_timeouts_from_pansou_timeout(self):
        source = PLUGIN_PATH.read_text(encoding="utf-8")
        apply = source[source.index("def _apply_config"):source.index("def get_state")]
        self.assertIn("self._pansou_timeout + 15.0", apply)
        self.assertIn("self._pansou_timeout + 30.0", apply)
        self.assertNotIn('config.get("source_request_timeout_seconds")', apply)
        self.assertNotIn('config.get("auto_search_budget_seconds")', apply)

    def test_startup_persists_a_merged_config_for_legacy_users(self):
        source = PLUGIN_PATH.read_text(encoding="utf-8")
        init = source[source.index("def init_plugin"):source.index("def _save_diagnostics")]
        self.assertIn("migrated_config = self._default_config()", init)
        self.assertIn("migrated_config.update(config)", init)
        self.assertIn("config = migrated_config", init)

    def test_share_transfer_waits_for_mp_before_subscribe_complete(self):
        source = PLUGIN_PATH.read_text(encoding="utf-8")
        finish = source[source.index("    def _finish_subscribe("):source.index("    @staticmethod\n    def _parse_episode_info")]
        wait_branch = finish.index("if self._wait_for_mp_organize:")
        complete_event = finish.index("eventmanager.send_event(EventType.SubscribeComplete")
        self.assertLess(wait_branch, complete_event)
        self.assertIn("return True", finish[wait_branch:complete_event])


if __name__ == "__main__":
    unittest.main()
