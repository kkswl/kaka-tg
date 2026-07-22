import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


PACKAGE_DIR = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115"
package = sys.modules.setdefault("tgsearch115", types.ModuleType("tgsearch115"))
package.__path__ = [str(PACKAGE_DIR)]
media_spec = importlib.util.spec_from_file_location("tgsearch115.media_types", PACKAGE_DIR / "media_types.py")
media_types = importlib.util.module_from_spec(media_spec)
sys.modules[media_spec.name] = media_types
media_spec.loader.exec_module(media_types)
spec = importlib.util.spec_from_file_location("tgsearch115.year_policy", PACKAGE_DIR / "year_policy.py")
year_policy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = year_policy
spec.loader.exec_module(year_policy)


class YearPolicyTest(unittest.TestCase):
    def test_tv_target_season_year_is_advisory_but_visible(self):
        subscribe = SimpleNamespace(type="TV", year=2023, season=3)
        media = SimpleNamespace(type="TV", season_years={3: 2026})

        decision = year_policy.decide_year_policy(subscribe, media, "Silo.S03.2026.2160p")

        self.assertFalse(decision.hard_reject)
        self.assertEqual("tv_season_year_match", decision.policy)
        self.assertEqual(2026, decision.target_season_year)

    def test_tv_without_season_year_is_deferred_not_rejected(self):
        subscribe = SimpleNamespace(type="TV", year=2023, season=3)
        media = SimpleNamespace(type="TV", season_years={})

        decision = year_policy.decide_year_policy(subscribe, media, "Silo.S03.2026.2160p")

        self.assertFalse(decision.hard_reject)
        self.assertEqual("tv_year_deferred_to_tmdb", decision.policy)

    def test_movie_conflicting_year_is_rejected(self):
        subscribe = SimpleNamespace(type="MOVIE", year=2023, season=None)
        media = SimpleNamespace(type="MOVIE", year=2023)

        decision = year_policy.decide_year_policy(subscribe, media, "Example.2026.2160p")

        self.assertTrue(decision.hard_reject)
        self.assertEqual("year_conflict_rejected", decision.policy)


if __name__ == "__main__":
    unittest.main()
