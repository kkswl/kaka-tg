# -*- coding: utf-8 -*-
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "resource_metadata.py"
spec = importlib.util.spec_from_file_location("tg115_resource_metadata", MODULE_PATH)
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


class ResourceMetadataTest(unittest.TestCase):
    def test_resolution_normalizes_4k_1080_and_720_without_number_prefix_false_positive(self):
        self.assertEqual("4k", metadata.normalize_resource_metadata({"title": "Movie 3840x2160 UHD"})["resolution"])
        self.assertEqual("1080p", metadata.normalize_resource_metadata({"title": "Movie 1920x1080"})["resolution"])
        self.assertEqual("720p", metadata.normalize_resource_metadata({"title": "Movie 1280x720"})["resolution"])
        self.assertEqual("unknown", metadata.normalize_resource_metadata({"title": "Movie 1720 10800"})["resolution"])

    def test_chinese_subtitles_do_not_confuse_audio_language(self):
        self.assertEqual("chs_cht", metadata.normalize_resource_metadata({"title": "Movie 简繁中文字幕"})["subtitle_type"])
        self.assertEqual("chs", metadata.normalize_resource_metadata({"title": "Movie.chs.ass"})["subtitle_type"])
        self.assertFalse(metadata.normalize_resource_metadata({"title": "Movie 国语 中文配音"})["has_chinese_subtitle"])

    def test_bluray_encode_is_not_remux(self):
        self.assertFalse(metadata.normalize_resource_metadata({"title": "Movie 1080P BluRay x265"})["is_remux"])
        self.assertTrue(metadata.normalize_resource_metadata({"title": "Movie 1080P REMUX"})["is_remux"])
        self.assertTrue(metadata.normalize_resource_metadata({"title": "Movie BDMV"})["is_remux"])

    def test_url_domain_wins_over_declared_type_and_accepts_parameters(self):
        self.assertEqual("115", metadata.normalize_pan_type("HTTPS://115.COM/s/a?x=1", "quark"))
        self.assertEqual("baidu", metadata.normalize_pan_type("https://pan.baidu.com/s/a", ""))
        self.assertEqual("magnet", metadata.normalize_pan_type("magnet:?xt=urn:btih:abc", "115"))
        self.assertEqual("other", metadata.normalize_pan_type("https://example.invalid/a", ""))

    def test_magnet_quality_class_uses_structured_subtitle_and_resolution(self):
        item = metadata.normalize_resource_metadata({"share_url": "magnet:?xt=urn:btih:abc", "title": "Movie 2160P CHS"})
        self.assertEqual("magnet", item["resource_kind"])
        self.assertEqual("chs4k", item["quality_class"])


if __name__ == "__main__":
    unittest.main()
