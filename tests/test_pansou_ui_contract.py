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

    def test_manual_search_keeps_a_single_source_selection(self):
        manual = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "ManualSearch.vue").read_text(encoding="utf-8")
        self.assertIn("搜索范围", manual)
        self.assertLess(manual.index("搜索范围"), manual.index("search-toolbar"))
        self.assertNotIn("结果来源", manual)
        self.assertNotIn("resultSource", manual)
        self.assertIn("upstream_source", manual)

    def test_detail_page_places_manual_search_before_diagnostics_and_task_history(self):
        page = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        self.assertIn("手动搜索（固定置顶）", page)
        self.assertLess(page.index("手动搜索（固定置顶）"), page.index("订阅处理诊断"))
        self.assertLess(page.index("手动搜索（固定置顶）"), page.index("磁力下载任务"))

    def test_manual_search_uses_bounded_session_cache_without_process_state(self):
        manual = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "ManualSearch.vue").read_text(encoding="utf-8")
        cache = manual[manual.index("const CACHE_KEY"):manual.index("function unwrap")]
        persisted = manual[manual.index("store.setItem(CACHE_KEY"):manual.index("function restoreSession")]
        self.assertIn("TgSearch115:manual-search:v1", cache)
        self.assertIn("window.sessionStorage", cache)
        self.assertIn("MAX_CACHED_RESULTS = 500", cache)
        self.assertIn("slice(0, MAX_CACHED_RESULTS).map(safeResult)", cache)
        self.assertIn("sessionStore()?.removeItem(CACHE_KEY)", cache)
        self.assertNotIn("subscribeId", persisted)
        self.assertNotIn("selectedResult", persisted)
        self.assertNotIn("transferring", persisted)

    def test_manual_search_keeps_visible_recovery_actions_when_api_or_request_fails(self):
        manual = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "ManualSearch.vue").read_text(encoding="utf-8")
        self.assertIn("apiReady", manual)
        self.assertIn("手动搜索服务尚未就绪", manual)
        self.assertIn("重新加载插件页面", manual)
        self.assertIn('@click="search">重试', manual)

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
