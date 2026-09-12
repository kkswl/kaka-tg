import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = (ROOT / "plugins.v2" / "tgsearch115" / "__init__.py").read_text(encoding="utf-8")
PAGE = (ROOT / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue").read_text(encoding="utf-8")


class TimelineClearContractTest(unittest.TestCase):
    def test_backend_registers_isolated_timeline_clear_api(self):
        self.assertIn('"path": "/runtime/timeline/clear"', BACKEND)
        self.assertIn('"methods": ["POST"]', BACKEND)
        start = BACKEND.index("def __clear_timeline_api")
        end = BACKEND.index("def __subscription_dry_run_api", start)
        handler = BACKEND[start:end]
        self.assertIn('payload.get("confirm") is not True', handler)
        for field in ("success", "message", "removed_count", "cleared_count", "active_cleared_count", "remaining_count", "active_count", "request_id"):
            self.assertIn(f'"{field}"', handler)
        self.assertIn('payload.get("force") is True', handler)
        self.assertIn('payload.get("confirmation_text") != "强制清理诊断记录"', handler)
        self.assertIn("self._timeline.clear_all()", handler)
        self.assertIn("self._save_diagnostics()", handler)
        self.assertNotIn("self._cms_tasks", handler)
        self.assertNotIn("SubscribeOper", handler)
        self.assertNotIn("_offline_client", handler)

    def test_frontend_confirms_calls_and_refreshes_timeline(self):
        self.assertIn("清理已结束的订阅诊断记录", PAGE)
        self.assertIn("仅删除本地终态诊断记录；不会删除 115 文件、不会取消下载、不会修改订阅。", PAGE)
        self.assertIn("runtime/timeline/clear`, { confirm: true }", PAGE)
        self.assertIn("没有可清理的终态诊断记录", PAGE)
        self.assertIn("await loadRuntimeStatus()", PAGE)
        self.assertIn("clearingTimeline", PAGE)
        self.assertIn("强制清理诊断记录", PAGE)
        self.assertIn("forceTimelineConfirmation", PAGE)
        self.assertIn("force: true", PAGE)
        self.assertIn("不会取消下载、删除 115 文件、清除磁力任务或修改订阅", PAGE)

    def test_magnet_task_clear_route_is_unchanged(self):
        self.assertIn('"path": "/tasks/clear"', BACKEND)
        self.assertIn("def __clear_offline_tasks_api", BACKEND)
        self.assertIn("tasks/clear`, { confirm: true }", PAGE)


if __name__ == "__main__":
    unittest.main()
