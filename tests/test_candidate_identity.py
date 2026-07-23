# -*- coding: utf-8 -*-
import unittest
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "candidate_identity.py"
spec = importlib.util.spec_from_file_location("tgsearch115_candidate_identity", MODULE_PATH)
candidate_identity = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = candidate_identity
spec.loader.exec_module(candidate_identity)
clean_identity_title = candidate_identity.clean_identity_title
extract_candidate_tmdb = candidate_identity.extract_candidate_tmdb
order_identity_candidates = candidate_identity.order_identity_candidates


class CandidateIdentityTest(unittest.TestCase):
    def test_obsession_identity_title_does_not_duplicate_year(self):
        title = clean_identity_title(
            "痴迷[中文字幕].Obsession.2025.1080p.WEB-DL",
            "痴迷", 2025,
            "痴迷 (2025) 痴迷[中文字幕].Obsession.2025.1080p.WEB-DL",
        )
        self.assertEqual(1, title.count("2025"))
        self.assertIn("Obsession", title)

    def test_correct_site_candidate_is_not_displaced_by_tg_noise(self):
        noise = [SimpleNamespace(
            title=f"无关 TG 资源 {index}", _tg115_source="tg",
            _tg115_source_title="", _tg115_metadata_verified=False,
        ) for index in range(10)]
        site = SimpleNamespace(
            title="铁血战士：杀戮之地.2025.1080p.中文字幕",
            _tg115_source="site", _tg115_source_title="铁血战士：杀戮之地",
            _tg115_metadata_verified=False,
        )
        target = SimpleNamespace(title="铁血战士：杀戮之地", names=["Predator: Badlands"], tmdb_id=1242898)
        subscribe = SimpleNamespace(name="铁血战士：杀戮之地", tmdbid=1242898)
        ordered = order_identity_candidates(noise + [site], target, subscribe)
        self.assertIs(site, ordered[0])

    def test_explicit_matching_tmdb_has_highest_priority(self):
        generic = SimpleNamespace(title="目标电影 2025", _tg115_source="site", _tg115_source_title="目标电影")
        exact = SimpleNamespace(title="目标电影 {tmdb-1242898}", _tg115_source="tg", _tg115_source_title="")
        target = SimpleNamespace(title="目标电影", names=[], tmdb_id=1242898)
        subscribe = SimpleNamespace(name="目标电影", tmdbid=1242898)
        self.assertIs(exact, order_identity_candidates([generic, exact], target, subscribe)[0])
        self.assertEqual("1242898", extract_candidate_tmdb(exact.title))

    def test_explicit_wrong_tmdb_is_ranked_last(self):
        wrong = SimpleNamespace(title="目标电影 {tmdb-999999}", _tg115_source="site", _tg115_source_title="目标电影")
        generic = SimpleNamespace(title="目标电影 2025", _tg115_source="tg", _tg115_source_title="")
        target = SimpleNamespace(title="目标电影", names=[], tmdb_id=1242898)
        subscribe = SimpleNamespace(name="目标电影", tmdbid=1242898)
        self.assertIs(wrong, order_identity_candidates([wrong, generic], target, subscribe)[-1])


if __name__ == "__main__":
    unittest.main()
