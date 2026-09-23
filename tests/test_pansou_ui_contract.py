import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PanSouUiContractTest(unittest.TestCase):
    def test_config_and_manual_search_expose_pansou_without_token_in_search_url(self):
        config = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Config.vue").read_text(encoding="utf-8")
        manual = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        self.assertIn('value="pansou"', config)
        self.assertIn('config.pansou_url', config)
        self.assertIn('config.pansou_token', config)
        self.assertIn('config.pansou_proxy', config)
        self.assertIn("{ title: 'PanSou', value: 'pansou' }", manual)
        check_body = config[config.index("async function checkPanSou"):config.index("async function doSearch")]
        self.assertNotIn("pansou_token", check_body)
        self.assertNotIn("token=", check_body)

    def test_detail_page_shows_bounded_pansou_diagnostics(self):
        page = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        for field in ("deduplicated", "rule_passed", "safe_candidates", "cache_hits"):
            self.assertIn(f"runtime.pansou.{field}", page)

    def test_manual_search_deeply_unwraps_host_response_before_counting(self):
        manual = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        unwrap = manual[manual.index("function unwrapApiResponse"):manual.index("const MANUAL_CACHE_KEY")]
        self.assertIn("for (let depth", unwrap)
        self.assertIn("value = value.data", unwrap)
        self.assertIn("manualResults.value.length", manual)

    def test_manual_search_keeps_a_single_source_selection(self):
        manual = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        self.assertIn("搜索范围", manual)
        self.assertLess(manual.index("搜索范围"), manual.index("manual-search-toolbar"))
        self.assertNotIn("结果来源", manual)
        self.assertNotIn("resultSource", manual)
        self.assertIn("upstream_source", manual)

    def test_manual_search_uses_bounded_session_cache_without_process_state(self):
        manual = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        cache = manual[manual.index("const MANUAL_CACHE_KEY"):manual.index("function closePage")]
        persisted = cache[cache.index("function persistManualSession"):cache.index("function restoreManualSession")]
        self.assertIn("TgSearch115:manual-search:v2", cache)
        self.assertIn("window.sessionStorage", cache)
        self.assertIn("slice(0, 500)", cache)
        self.assertIn("function manualSessionStore", cache)
        self.assertNotIn("manualSubscribeId", persisted)
        self.assertNotIn("manualSelectedResult", persisted)
        self.assertNotIn("manualTransferring", persisted)

    def test_manual_search_survives_storage_and_result_shape_failures(self):
        page = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        self.assertIn("normalizeManualResult", page)
        self.assertIn("sourceItems.map(normalizeManualResult)", page)
        self.assertIn('data-testid="manual-search-root"', page)
        self.assertIn('data-testid="manual-search-input"', page)
        self.assertIn('data-testid="manual-search-button"', page)
        self.assertNotIn("import ManualSearch", page)
        self.assertNotIn("<ManualSearch", page)
        self.assertNotIn("v-progress-circular", page)
        self.assertIn('class="manual-loading"', page)
        self.assertIn('@media (max-width: 600px)', page)
        self.assertIn('grid-template-columns:minmax(0, 1fr)', page)
        search = page[page.index("async function runManualSearch"):page.index("function manualSourceLabel")]
        self.assertIn("finally", search)
        self.assertIn("manualSearching.value = false", search)

    def test_page_has_one_search_state_owner_and_build_marker(self):
        page = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        self.assertEqual(0, page.count("<ManualSearch"))
        self.assertEqual(1, page.count('data-testid="manual-search-root"'))
        self.assertNotIn('v-if="false"', page)
        self.assertIn("FRONTEND_VERSION = '4.8.26'", page)
        self.assertIn("frontendBuildId", page)
        self.assertIn("versionMismatch", page)
        self.assertIn("manual-search-body", page)

    def test_page_exposes_sanitized_organize_wait_diagnostics(self):
        page = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        for field in ("organize_wait_reason", "last_reconcile_at", "btih_prefix", "formatWaitDuration"):
            self.assertIn(field, page)

    def test_manual_search_backend_has_stable_safe_error_shape(self):
        backend = (ROOT / "plugins.v2" / "tgsearch115" / "__init__.py").read_text(encoding="utf-8")
        start = backend.index("    def __search_api")
        end = backend.index("    # ---------------------------- 115 目录查询", start)
        body = backend[start:end]
        for field in ('"success"', '"message"', '"items"', '"source_stats"', '"request_id"'):
            self.assertIn(field, body)
        self.assertNotIn('f"搜索失败: {e}"', body)


if __name__ == "__main__":
    unittest.main()
