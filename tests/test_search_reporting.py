import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "search_reporting.py"
spec = importlib.util.spec_from_file_location("tgsearch115_search_reporting", PATH)
reporting = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reporting
spec.loader.exec_module(reporting)


class SearchReportTest(unittest.TestCase):
    def test_summary_merges_sources_and_deduplicates_alias_hits(self):
        report = reporting.SearchReport({"tg": True, "site": True, "juying": False})
        same = SimpleNamespace(share_url="https://example.invalid/a", resource_title="示例")
        duplicate = SimpleNamespace(share_url="https://example.invalid/A", resource_title="别名")
        report.record("tg", [same], cached=True)
        report.record("tg", [duplicate])
        report.record("site", [])

        text = report.text()

        self.assertIn("TG 频道 1 条（含缓存）", text)
        self.assertIn("观影 0 条", text)
        self.assertIn("聚影 未启用", text)

    def test_summary_reports_cooldown_without_error_details(self):
        report = reporting.SearchReport({"tg": True, "site": True, "juying": True})
        report.mark("site", "cooldown")
        report.mark("juying", "error")

        self.assertIn("观影 冷却中", report.text())
        self.assertIn("聚影 请求失败", report.text())


if __name__ == "__main__":
    unittest.main()
