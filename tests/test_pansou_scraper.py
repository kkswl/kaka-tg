# -*- coding: utf-8 -*-
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class _Logger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class _Response:
    def __init__(self, status_code=200, data=None, text="", headers=None):
        self.status_code = status_code
        self._data = data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._data is None:
            raise ValueError("not json")
        return self._data


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def close(self):
        self.closed = True


ROOT = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115"
app = sys.modules.setdefault("app", types.ModuleType("app"))
log = sys.modules.setdefault("app.log", types.ModuleType("app.log"))
log.logger = _Logger()
app.log = log
package = sys.modules.setdefault("tgsearch115", types.ModuleType("tgsearch115"))
package.__path__ = [str(ROOT)]
for name in ("site_scraper", "pansou_scraper"):
    spec = importlib.util.spec_from_file_location(f"tgsearch115.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

pansou = sys.modules["tgsearch115.pansou_scraper"]


class PanSouScraperTest(unittest.TestCase):
    def test_health_check_reports_reachable_service(self):
        client = pansou.PanSouClient("http://example.invalid")
        client._http = _Client([_Response(200, {"code": 0})])

        ok, message = client.health_check()

        self.assertTrue(ok)
        self.assertIn("PanSou", message)
        self.assertEqual("GET", client._http.calls[0][0])

    def test_numeric_and_string_zero_are_success(self):
        self.assertTrue(pansou.PanSouClient._is_success({"code": 0, "data": {"total": 0}}))
        self.assertTrue(pansou.PanSouClient._is_success({"code": "0", "data": {}}))

    def test_normalizes_all_supported_response_containers(self):
        item1 = {"url": "https://115.com/s/a", "title": "A"}
        item2 = {"link": "magnet:?xt=urn:btih:" + "a" * 40, "name": "B"}
        payload = {
            "results": [item1],
            "merged_by_type": {"magnet": [item2]},
            "data": {"resources": [{"share_link": "https://115.com/s/c", "title": "C"}], "total": 3},
        }
        result = pansou.PanSouClient.normalize_response(payload)
        self.assertEqual(3, len(result))

    def test_normalizes_live_get_shape_and_preserves_upstream_source(self):
        payload = {
            "code": 0,
            "data": {
                "total": 1,
                "merged_by_type": {
                    "baidu": [{
                        "url": "https://pan.baidu.com/s/demo?pwd=abcd",
                        "password": "abcd",
                        "note": "捉刀人 2024",
                        "datetime": "2026-08-04T08:00:00+08:00",
                        "source": "plugin:wanou",
                    }],
                },
            },
        }
        items = pansou.PanSouClient.normalize_response(payload)
        hit = pansou.PanSouClient.normalize_item(items[0])
        self.assertEqual(1, len(items))
        self.assertEqual("baidu", hit.pan_type)
        self.assertEqual("捉刀人 2024", hit.resource_title)
        self.assertEqual("plugin:wanou", hit.upstream_source)

    def test_flattens_documented_results_links(self):
        payload = {
            "results": [{
                "title": "捉刀人",
                "channel": "tgsearchers7",
                "links": [{"type": "115", "url": "https://115.com/s/demo", "password": "x1y2"}],
            }],
        }
        items = pansou.PanSouClient.normalize_response(payload)
        hit = pansou.PanSouClient.normalize_item(items[0])
        self.assertEqual(1, len(items))
        self.assertEqual("115", hit.pan_type)
        self.assertEqual("x1y2", hit.receive_code)
        self.assertEqual("tgsearchers7", hit.upstream_source)

    def test_total_only_data_does_not_create_fake_result(self):
        self.assertEqual([], pansou.PanSouClient.normalize_response({"code": 0, "data": {"total": 0}}))

    def test_url_domain_overrides_declared_cloud_type(self):
        hit = pansou.PanSouClient.normalize_item({
            "url": "https://115.com/s/demo", "type": "quark", "title": "示例 中文字幕 1080P",
        })
        self.assertEqual("115", hit.pan_type)

    def test_non_json_is_safe_error_and_returns_no_hits(self):
        client = pansou.PanSouClient("http://example.invalid")
        client._http = _Client([_Response(data=None, text="html")])
        self.assertEqual([], client.search("示例"))
        self.assertEqual("非 JSON 响应", client.last_error)

    def test_retry_after_is_honored_for_429(self):
        client = pansou.PanSouClient("http://example.invalid")
        client._http = _Client([
            _Response(429, {}, headers={"Retry-After": "2"}),
            _Response(200, {"code": 0, "data": {"total": 0}}),
        ])
        with patch.object(pansou.time, "sleep") as sleep:
            result = client.search("示例")
        self.assertEqual([], result)
        sleep.assert_called_once_with(2.0)
        self.assertEqual(2, len(client._http.calls))

    def test_retry_after_http_date_is_supported(self):
        delay = pansou.PanSouClient._retry_delay("Wed, 21 Oct 2099 07:28:00 GMT", 0)
        self.assertEqual(30.0, delay)

    def test_empty_cloud_types_omits_manual_result_filter(self):
        client = pansou.PanSouClient("http://example.invalid")
        client._http = _Client([_Response(200, {"code": 0, "data": {"total": 0}})])
        client.search("示例", cloud_types=(), retry=False)
        self.assertNotIn("cloud_types", client._http.calls[0][2]["params"])

    def test_manual_deadline_disables_retry_and_sets_request_timeout(self):
        client = pansou.PanSouClient("http://example.invalid")
        client._http = _Client([_Response(503, {})])
        with patch.object(pansou.time, "sleep") as sleep:
            self.assertEqual([], client.search(
                "示例", retry=False, request_timeout=35.0,
            ))
        self.assertEqual(1, len(client._http.calls))
        method, url, kwargs = client._http.calls[0]
        self.assertEqual("GET", method)
        self.assertEqual("http://example.invalid/api/search", url)
        self.assertEqual("示例", kwargs["params"]["kw"])
        self.assertEqual(35.0, kwargs["timeout"])
        self.assertNotIn("json", kwargs)
        sleep.assert_not_called()

    def test_safe_http_error_categories(self):
        self.assertIn("401", pansou.PanSouClient.safe_error(401, ""))
        self.assertIn("403", pansou.PanSouClient.safe_error(403, ""))
        self.assertIn("429", pansou.PanSouClient.safe_error(429, ""))
        self.assertIn("503", pansou.PanSouClient.safe_error(503, ""))

    def test_http_failures_return_no_hits_and_keep_error_status(self):
        for status in (401, 403):
            client = pansou.PanSouClient("http://example.invalid")
            client._http = _Client([_Response(status, {"code": status})])
            self.assertEqual([], client.search("example"))
            self.assertEqual(status, client.last_error_status)
            self.assertIn(str(status), client.last_error)

        client = pansou.PanSouClient("http://example.invalid")
        client._http = _Client([_Response(503, {}), _Response(503, {}), _Response(503, {})])
        with patch.object(pansou.time, "sleep") as sleep:
            self.assertEqual([], client.search("example"))
        self.assertEqual(503, client.last_error_status)
        self.assertEqual(3, len(client._http.calls))
        self.assertEqual(2, sleep.call_count)

    def test_close_releases_http_client(self):
        client = pansou.PanSouClient("http://example.invalid")
        http = _Client([])
        http.closed = False
        client._http = http

        client.close()

        self.assertTrue(http.closed)
        self.assertIsNone(client._http)


if __name__ == "__main__":
    unittest.main()
