import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins.v2"
    / "tgsearch115"
    / "search_relevance.py"
)
spec = importlib.util.spec_from_file_location("tgsearch115_search_relevance", MODULE_PATH)
search_relevance = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = search_relevance
spec.loader.exec_module(search_relevance)


class SearchRelevanceTest(unittest.TestCase):
    def test_exact_title_and_year_match(self):
        self.assertTrue(search_relevance.is_relevant_result(
            "法警小队", 2026, "电视剧：法警小队 (2026)", 2026
        ))

    def test_season_suffix_is_ignored(self):
        self.assertTrue(search_relevance.is_relevant_result(
            "法警小队", None, "法警小队 第一季", 2026
        ))

    def test_conflicting_year_is_rejected(self):
        self.assertFalse(search_relevance.is_relevant_result(
            "同名作品", 2026, "同名作品 (2020)", 2020
        ))

    def test_fuzzy_body_hit_is_rejected(self):
        self.assertFalse(search_relevance.is_relevant_result(
            "法警小队", 2026, "双姝美探 (2026)", 2026
        ))

    def test_unrelated_title_is_rejected(self):
        self.assertFalse(search_relevance.is_relevant_result(
            "法警小队", 2026, "雪迷宫 (2024)", 2024
        ))

    def test_manual_tg_accepts_query_in_message_body(self):
        self.assertTrue(search_relevance.is_manual_relevant_result(
            "tg", "法警小队", 2026, "双姝美探", None,
            "法警小队 2026 全集 1080P 中文字幕",
        ))

    def test_manual_non_tg_keeps_strict_title_match(self):
        self.assertFalse(search_relevance.is_manual_relevant_result(
            "pansou", "法警小队", 2026, "双姝美探", None,
            "法警小队 2026 全集 1080P 中文字幕",
        ))

    def test_manual_tg_rejects_conflicting_year(self):
        self.assertFalse(search_relevance.is_manual_relevant_result(
            "tg", "同名作品", 2026, "资源合集", 2020,
            "同名作品 2026 全集",
        ))


if __name__ == "__main__":
    unittest.main()
