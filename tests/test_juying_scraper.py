import importlib.util
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins.v2" / "tgsearch115"


class _Logger:
    def __init__(self):
        self.entries = []

    def __getattr__(self, name):
        return lambda *args, **_kwargs: self.entries.append((name, args))


@dataclass
class _SiteHit:
    share_url: str = ""
    receive_code: str = ""
    resource_title: str = ""
    text: str = ""
    pan_type: str = ""
    pan_label: str = ""
    source_title: str = ""
    channel_name: str = ""
    pub_date: str | None = None
    year: int | None = None


class _Response:
    def __init__(self, status_code=200, data=None, headers=None):
        self.status_code = status_code
        self._data = data
        self.headers = headers or {}

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)

    def close(self):
        self.closed = True


LOGGER = _Logger()
app = sys.modules.setdefault("app", types.ModuleType("app"))
log = types.ModuleType("app.log")
log.logger = LOGGER
sys.modules["app.log"] = log
app.log = log

package_name = "tgsearch115_juying_test"
package = types.ModuleType(package_name)
package.__path__ = [str(PLUGIN)]
sys.modules[package_name] = package

media_spec = importlib.util.spec_from_file_location(
    f"{package_name}.media_types", PLUGIN / "media_types.py"
)
media_types = importlib.util.module_from_spec(media_spec)
sys.modules[media_spec.name] = media_types
media_spec.loader.exec_module(media_types)

site_module = types.ModuleType(f"{package_name}.site_scraper")
site_module.SiteHit = _SiteHit
site_module._classify_pan = lambda url: "115" if "115" in url else "other"
sys.modules[site_module.__name__] = site_module

juying_spec = importlib.util.spec_from_file_location(
    f"{package_name}.juying_scraper", PLUGIN / "juying_scraper.py"
)
juying = importlib.util.module_from_spec(juying_spec)
sys.modules[juying_spec.name] = juying
juying_spec.loader.exec_module(juying)


class JuyingApiTest(unittest.TestCase):
    def _api(self, response):
        api = juying.JuyingApi("app-secret", "key-secret", "https://www.jying.top/path")
        api._http = _Client([response])
        return api

    @staticmethod
    def _success_payload():
        return {
            "status": "success",
            "cache_hit": True,
            "source_status": {"juying": "ok", "pansou": "skipped"},
            "summary": {"movies": 1, "resources": 3, "juying_resources": 2},
            "movies": [
                {"id": 7, "title": "示例电视剧", "release_year": 2024}
            ],
            "resources": [
                {
                    "provider": "juying",
                    "movie_id": 7,
                    "resource_type": "115",
                    "share_link": "https://115.example/s/demo?password=abcd",
                    "description": "S01 4K 中文字幕",
                    "added_at": "2026-09-01T12:00:00+08:00",
                },
                {
                    "provider": "juying",
                    "movie_id": 7,
                    "resource_type": "115",
                    "share_link": "https://115.example/s/demo?password=abcd",
                },
                {
                    "provider": "pansou",
                    "resource_type": "quark",
                    "share_link": "https://pan.example/s/duplicate-source",
                },
            ],
        }

    def test_search_uses_fuzzy_local_source_type_and_header_credentials(self):
        api = self._api(_Response(200, self._success_payload()))

        hits = api.search("示例电视剧", year=2024, media_type="TV")

        self.assertEqual(1, len(hits))
        url, kwargs = api._http.calls[0]
        query = parse_qs(urlparse(url).query)
        self.assertEqual(["true"], query["fuzzy"])
        self.assertEqual(["juying"], query["source"])
        self.assertEqual(["tv"], query["type"])
        self.assertEqual(["2024"], query["year"])
        self.assertNotIn("app-secret", url)
        self.assertNotIn("key-secret", url)
        self.assertEqual("app-secret", kwargs["headers"]["X-App-Id"])
        self.assertEqual("key-secret", kwargs["headers"]["X-App-Key"])

    def test_maps_movie_metadata_code_and_filters_duplicate_or_pansou_items(self):
        api = self._api(_Response(200, self._success_payload()))

        hits = api.search("示例电视剧", year=2023)

        self.assertEqual(1, len(hits))
        self.assertEqual("示例电视剧", hits[0].source_title)
        self.assertEqual(2024, hits[0].year)
        self.assertEqual("abcd", hits[0].receive_code)
        self.assertEqual("115", hits[0].pan_type)
        self.assertEqual("2026-09-01T12:00:00+08:00", hits[0].pub_date)
        self.assertTrue(api.last_cache_hit)
        self.assertEqual("ok", api.last_source_status["juying"])
        self.assertEqual(1, api.last_result_count)

    def test_accepts_documented_nested_data_container(self):
        payload = self._success_payload()
        nested = {"status": "success", "data": {"movies": payload["movies"], "resources": payload["resources"]}}
        api = self._api(_Response(200, nested))

        self.assertEqual(1, len(api.search("示例电视剧")))

    def test_429_exposes_retry_after_without_retrying_or_leaking_response(self):
        api = self._api(_Response(429, {"message": "secret body"}, {"Retry-After": "45"}))

        self.assertEqual([], api.search("示例电影"))
        self.assertEqual(429, api.last_error_status)
        self.assertEqual(45, api.last_retry_after)
        self.assertIn("45", api.last_error)
        self.assertEqual(1, len(api._http.calls))
        rendered_logs = repr(LOGGER.entries)
        self.assertNotIn("secret body", rendered_logs)
        self.assertNotIn("key-secret", rendered_logs)

    def test_auth_and_server_errors_are_classified(self):
        auth = self._api(_Response(401, {"message": "do not log"}))
        server = self._api(_Response(503, {"message": "do not log"}))

        self.assertEqual([], auth.search("示例电影"))
        self.assertFalse(auth.app_auth_valid)
        self.assertEqual(401, auth.last_error_status)
        self.assertEqual([], server.search("示例电影"))
        self.assertEqual(503, server.last_error_status)

    def test_documented_unavailable_source_is_not_misreported_as_empty(self):
        api = self._api(
            _Response(
                200,
                {
                    "status": "success",
                    "source_status": {"juying": "unavailable", "pansou": "skipped"},
                    "resources": [],
                },
            )
        )

        self.assertEqual([], api.search("示例电影"))
        self.assertIn("暂时不可用", api.last_error)

    def test_check_is_read_only_exact_and_local_only(self):
        api = self._api(_Response(200, {"status": "success", "source_status": {"juying": "ok"}}))

        ok, message = api.check()

        self.assertTrue(ok)
        self.assertIn("鉴权有效", message)
        query = parse_qs(urlparse(api._http.calls[0][0]).query)
        self.assertEqual(["false"], query["fuzzy"])
        self.assertEqual(["juying"], query["source"])

    def test_invalid_domain_and_short_query_never_request(self):
        api = juying.JuyingApi("app", "key", "file:///tmp/not-http")
        self.assertFalse(api.is_ready())
        api = juying.JuyingApi("app", "key", "https://www.jying.top")
        api._http = _Client([])
        self.assertEqual([], api.search("一"))
        self.assertEqual([], api._http.calls)

    def test_close_releases_http_client(self):
        api = self._api(_Response(200, self._success_payload()))
        client = api._http
        api.close()
        self.assertTrue(client.closed)
        self.assertIsNone(api._http)


class JuyingIntegrationContractTest(unittest.TestCase):
    def test_frontend_posts_credentials_and_backend_route_is_post_only(self):
        frontend = (PLUGIN / "frontend" / "src" / "components" / "Config.vue").read_text(encoding="utf-8")
        backend = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        check_ui = frontend[frontend.index("async function checkJuying"):frontend.index("async function checkPanSou")]
        route = backend[backend.index('"path": "/check_juying"'):backend.index('"path": "/check_pansou"')]
        self.assertIn("apiPost('/check_juying'", check_ui)
        self.assertNotIn("api_key=", check_ui)
        self.assertIn('"methods": ["POST"]', route)

    def test_auto_search_passes_media_type_and_stop_closes_client(self):
        backend = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("keyword, year=year, media_type=media_type", backend)
        self.assertIn("juying_api.close()", backend)


if __name__ == "__main__":
    unittest.main()
