import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path


class _Logger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


app = sys.modules.setdefault("app", types.ModuleType("app"))
app_log = sys.modules.setdefault("app.log", types.ModuleType("app.log"))
app_log.logger = _Logger()

MODULE_PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "tg_scraper.py"
spec = importlib.util.spec_from_file_location("tgsearch115_tg_scraper", MODULE_PATH)
tg_scraper = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tg_scraper
spec.loader.exec_module(tg_scraper)


class _Response:
    def __init__(self, status_code, headers=None, text=""):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def get(self, _url):
        self.calls += 1
        return self.responses.pop(0)


class _Anchor:
    def __init__(self, href):
        self.href = href

    def get(self, key, default=""):
        return self.href if key == "href" else default


class _Text:
    def get_text(self, **_kwargs):
        return "测试影片 中文字幕"


class _Message:
    def __init__(self, href):
        self.href = href

    def get(self, key, default=""):
        return "demo/123" if key == "data-post" else default

    def find(self, name, **kwargs):
        if name == "div" and kwargs.get("class_") == "tgme_widget_message_text":
            return _Text()
        return None

    def find_all(self, name, **_kwargs):
        return [_Anchor(self.href)] if name == "a" else []


class _Soup:
    def __init__(self, message):
        self.message = message

    def find_all(self, name=None, **kwargs):
        if name == "div" and kwargs.get("class_") == "tgme_widget_message":
            return [self.message]
        return []


class TgScraperTest(unittest.TestCase):
    def test_repairs_double_utf8_latin1_channel_name(self):
        broken = "剧迷".encode("utf-8").decode("latin-1")
        broken = broken.encode("utf-8").decode("latin-1")
        self.assertEqual("剧迷", tg_scraper.repair_mojibake(broken))
        self.assertEqual("Movie Channel", tg_scraper.repair_mojibake("Movie Channel"))

    def test_extracts_links_from_message_buttons_and_wrapped_urls(self):
        direct = "https://115.com/s/demo123?password=abcd"
        wrapped = "https://t.me/iv?url=" + tg_scraper.quote("https://115.com/s/wrapped456")
        message = _Message(direct)
        message.find_all = lambda *_args, **_kwargs: [_Anchor(direct), _Anchor(wrapped)]
        self.assertEqual(
            [direct, "https://115.com/s/wrapped456"],
            tg_scraper._extract_115_links(message, "资源按钮"),
        )

    def test_parses_legacy_share_php_link(self):
        share_code, receive_code = tg_scraper._parse_payload(
            "https://115.com/share.php?share_code=legacy123&password=abcd"
        )
        self.assertEqual("legacy123", share_code)
        self.assertEqual("abcd", receive_code)

    def test_channel_search_includes_anchor_only_115_resource(self):
        html = "synthetic"
        message = _Message("https://115.com/s/anchor123?password=abcd")
        scraper = tg_scraper.TgChannelScraper(max_pages=1, page_delay=(0.2, 0.2))
        client = _Client([_Response(200, text=html)])
        original_sleep = tg_scraper.asyncio.sleep
        original_bs4 = sys.modules.get("bs4")
        fake_bs4 = types.ModuleType("bs4")
        fake_bs4.BeautifulSoup = lambda *_args, **_kwargs: _Soup(message)
        sys.modules["bs4"] = fake_bs4

        async def fake_sleep(_delay):
            return None

        tg_scraper.asyncio.sleep = fake_sleep
        try:
            hits = asyncio.run(scraper._search_one_channel(
                client, "demo", "测试频道", tg_scraper.quote("测试影片"), asyncio.Semaphore(1)
            ))
        finally:
            tg_scraper.asyncio.sleep = original_sleep
            if original_bs4 is None:
                sys.modules.pop("bs4", None)
            else:
                sys.modules["bs4"] = original_bs4
        self.assertEqual(1, len(hits))
        self.assertEqual("anchor123", hits[0].share_code)
        self.assertEqual("测试频道", hits[0].channel_name)

    def test_429_retries_and_honors_configured_retry_path(self):
        scraper = tg_scraper.TgChannelScraper(max_retries=1)
        client = _Client([
            _Response(429, {"Retry-After": "5"}),
            _Response(200),
        ])
        delays = []
        original_sleep = tg_scraper.asyncio.sleep

        async def fake_sleep(delay):
            delays.append(delay)

        tg_scraper.asyncio.sleep = fake_sleep
        try:
            response = asyncio.run(
                scraper._get_with_backoff(client, "https://example.test", "demo", 1)
            )
        finally:
            tg_scraper.asyncio.sleep = original_sleep

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, client.calls)
        self.assertGreaterEqual(delays[0], 5)
        self.assertLess(delays[0], 6)


if __name__ == "__main__":
    unittest.main()
