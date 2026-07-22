import importlib.util
import sys
import unittest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "media_types.py"
spec = importlib.util.spec_from_file_location("tgsearch115_media_types", MODULE_PATH)
media_types = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = media_types
spec.loader.exec_module(media_types)


class _MediaType(Enum):
    MOVIE = "电影"
    TV = "电视剧"


class MediaTypeCompatibilityTest(unittest.TestCase):
    def test_normalizes_legacy_and_postgresql_tv_values(self):
        self.assertTrue(media_types.is_tv_media("TV"))
        self.assertTrue(media_types.is_tv_media("电视剧"))
        self.assertTrue(media_types.is_tv_media(_MediaType.TV))
        self.assertEqual("TV", media_types.media_type_key("电视剧"))

    def test_converts_persisted_values_to_moviepilot_enum(self):
        self.assertIs(_MediaType.TV, media_types.to_moviepilot_media_type("TV", _MediaType))
        self.assertIs(_MediaType.TV, media_types.to_moviepilot_media_type("电视剧", _MediaType))
        self.assertIs(_MediaType.MOVIE, media_types.to_moviepilot_media_type("MOVIE", _MediaType))
        self.assertIsNone(media_types.to_moviepilot_media_type("unknown", _MediaType))

    def test_compares_enum_and_persisted_type(self):
        self.assertTrue(media_types.same_media_type(_MediaType.TV, "TV"))
        self.assertTrue(media_types.same_media_type(_MediaType.MOVIE, "电影"))
        self.assertFalse(media_types.same_media_type(_MediaType.TV, _MediaType.MOVIE))

    def test_notification_title_includes_year_and_tv_season(self):
        tv = SimpleNamespace(name="末日地堡", year=2023, type="电视剧", season=3)
        movie = SimpleNamespace(name="示例电影", year=2024, type="MOVIE", season=None)
        special = SimpleNamespace(name="示例剧", year=2024, type="TV", season=0)

        self.assertEqual("TG115 搜索完成：末日地堡（2023）S03", media_types.subscription_notification_title(tv))
        self.assertEqual("TG115 搜索完成：示例电影（2024）", media_types.subscription_notification_title(movie))
        self.assertEqual("TG115 搜索完成：示例剧（2024）S00", media_types.subscription_notification_title(special))
