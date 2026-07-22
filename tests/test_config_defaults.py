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
        self.assertEqual(2, defaults["tg_concurrency"])
        self.assertEqual(12, defaults["cms_timeout_hours"])
        self.assertEqual("direct_then_cms", defaults["magnet_download_mode"])
        self.assertTrue(defaults["wait_for_mp_organize"])


if __name__ == "__main__":
    unittest.main()
