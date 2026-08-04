import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PanSouUiContractTest(unittest.TestCase):
    def test_config_and_manual_search_expose_pansou_without_token_in_search_url(self):
        config = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Config.vue").read_text(encoding="utf-8")
        manual = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "ManualSearch.vue").read_text(encoding="utf-8")
        self.assertIn('value="pansou"', config)
        self.assertIn('config.pansou_url', config)
        self.assertIn('config.pansou_token', config)
        self.assertIn('config.pansou_proxy', config)
        self.assertIn('value="pansou"', manual)
        check_body = config[config.index("async function checkPanSou"):config.index("async function doSearch")]
        self.assertNotIn("pansou_token", check_body)
        self.assertNotIn("token=", check_body)

    def test_detail_page_shows_bounded_pansou_diagnostics(self):
        page = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        for field in ("deduplicated", "rule_passed", "safe_candidates", "cache_hits"):
            self.assertIn(f"runtime.pansou.{field}", page)

    def test_manual_search_deeply_unwraps_host_response_before_counting(self):
        manual = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "ManualSearch.vue").read_text(encoding="utf-8")
        unwrap = manual[manual.index("function unwrap"):manual.index("function notify")]
        self.assertIn("while (value", unwrap)
        self.assertIn("value = value.data", unwrap)
        self.assertIn("results.value.length", manual)


if __name__ == "__main__":
    unittest.main()
