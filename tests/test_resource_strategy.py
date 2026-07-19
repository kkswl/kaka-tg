import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins.v2"
    / "tgsearch115"
    / "resource_strategy.py"
)
spec = importlib.util.spec_from_file_location("tgsearch115_resource_strategy", MODULE_PATH)
resource_strategy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = resource_strategy
spec.loader.exec_module(resource_strategy)


def _torrent(url, pan_type, site="观影", complete=True):
    return SimpleNamespace(
        page_url=url,
        site_name=site,
        _tg115_pan_type=pan_type,
        _tg115_is_complete=complete,
    )


def _is_115(url):
    return "115.com/" in url


class ResourceStrategyTest(unittest.TestCase):
    def test_prefers_unique_guanying_magnet_before_115(self):
        magnet = "magnet:?xt=urn:btih:" + "a" * 40
        torrents = [
            _torrent("https://115.com/s/demo", "115"),
            _torrent(magnet, "magnet"),
            _torrent(magnet + "&dn=duplicate", "magnet"),
        ]

        selected = resource_strategy.select_auto_candidates(
            torrents, True, False, _is_115
        )

        self.assertEqual([magnet, "https://115.com/s/demo"], [t.page_url for t in selected])

    def test_rejects_incomplete_tv_magnet(self):
        torrents = [
            _torrent("magnet:?xt=urn:btih:" + "b" * 40, "magnet", complete=False),
            _torrent("https://115.com/s/demo", "115"),
        ]

        selected = resource_strategy.select_auto_candidates(
            torrents, True, True, _is_115
        )

        self.assertEqual(["https://115.com/s/demo"], [t.page_url for t in selected])

    def test_ignores_non_guanying_magnet(self):
        selected = resource_strategy.select_auto_candidates(
            [_torrent("magnet:?xt=urn:btih:" + "c" * 40, "magnet", site="聚影")],
            True,
            False,
            _is_115,
        )

        self.assertEqual([], selected)


if __name__ == "__main__":
    unittest.main()
