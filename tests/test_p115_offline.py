import importlib.util
import threading
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "p115_offline.py"
spec = importlib.util.spec_from_file_location("tgsearch115_p115_offline", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def magnet(char="a"):
    return "magnet:?xt=urn:btih:" + char * 40 + "&dn=synthetic"


class Response:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self.payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self.payload


class P115OfflineTest(unittest.TestCase):
    def test_lixianssp_request_codec_is_base64_rsa_blocks(self):
        payload = b'{"url":"synthetic","wp_path_id":"0"}'
        encoded = module._rsa_encrypt(payload)
        decoded = module.base64.b64decode(encoded)
        self.assertEqual(0, len(decoded) % 128)
        self.assertNotIn(payload, decoded)

    def test_invalid_btih_is_rejected_without_request(self):
        calls = []
        client = module.P115OfflineClient("UID=x", request=lambda *a, **k: calls.append((a, k)))
        result = client.submit_magnet("magnet:?xt=urn:btih:not-valid")
        self.assertFalse(result["success"])
        self.assertEqual("invalid_btih", result["error_code"])
        self.assertEqual([], calls)

    def test_submit_reads_sign_and_accepts_numeric_or_string_code(self):
        calls = []

        def request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if "space" in url:
                return Response(payload={"state": True, "data": {"sign": "redacted-sign", "time": "1"}})
            return Response(payload={"code": "0", "data": {"info_hash": "a" * 40}})

        client = module.P115OfflineClient("UID=x", request=request)
        result = client.submit_magnet(magnet())
        self.assertTrue(result["success"])
        self.assertEqual("a" * 40, result["btih"])
        self.assertEqual("submitted", result["status"])
        self.assertEqual(3, len(calls))  # task list, sign, create
        self.assertNotIn("magnet", str(result).lower())

    def test_retry_after_and_exponential_backoff(self):
        waits, attempts = [], [0]

        def request(method, url, **kwargs):
            attempts[0] += 1
            if attempts[0] == 1:
                return Response(429, {"code": 429}, {"Retry-After": "3"})
            if attempts[0] == 2:
                return Response(503, {"code": 503})
            return Response(payload={"state": True, "data": {"sign": "s", "time": "1"}})

        client = module.P115OfflineClient("UID=x", request=request, sleep=waits.append, max_retries=2)
        self.assertEqual({"sign": "s", "time": "1"}, client._get_sign())
        self.assertEqual([3.0, 2.0], waits)

    def test_status_mapping_and_no_completion_on_running(self):
        self.assertEqual("downloading", module.P115OfflineClient.normalize_status({"code": "0", "status": "1"})["status"])
        self.assertEqual("completed", module.P115OfflineClient.normalize_status({"status": 2, "percent": "100"})["status"])

    def test_completed_bucket_overrides_stale_running_status_and_keeps_path_hint(self):
        calls = []

        def request(method, url, **kwargs):
            params = kwargs.get("params") or {}
            calls.append(dict(params))
            if params.get("ac") == "get_user_task":
                return Response(payload={"state": True, "task": {
                    "info_hash": "a" * 40, "status": 1, "percent": 100,
                }})
            self.assertEqual(11, params.get("stat"))
            return Response(payload={"state": True, "tasks": [{
                "info_hash": "a" * 40, "status": 1, "percent": 100,
                "wp_path_id": "12345", "name": "示例资源",
            }]})

        client = module.P115OfflineClient("UID=x", request=request)
        result = client.get_task_status("a" * 40)

        self.assertEqual("completed", result["status"])
        self.assertEqual("12345", result["target_cid"])
        self.assertEqual("示例资源", result["name"])
        self.assertEqual(["get_user_task", "task_lists"], [item["ac"] for item in calls])

    def test_running_task_is_not_completed_when_absent_from_completed_bucket(self):
        def request(method, url, **kwargs):
            params = kwargs.get("params") or {}
            if params.get("ac") == "get_user_task":
                return Response(payload={"state": True, "task": {
                    "info_hash": "a" * 40, "status": 1, "percent": 75,
                }})
            return Response(payload={"state": True, "tasks": []})

        result = module.P115OfflineClient("UID=x", request=request).get_task_status("a" * 40)
        self.assertEqual("downloading", result["status"])
        self.assertEqual(75.0, result["progress"])

    def test_auth_errors_are_not_retried_or_marked_complete(self):
        attempts = []
        client = module.P115OfflineClient("UID=x", request=lambda *a, **k: (attempts.append(1) or Response(401, {"code": 401})))
        with self.assertRaises(module.OfflineHttpError) as ctx:
            client._get_sign()
        self.assertEqual(401, ctx.exception.status)
        self.assertEqual(1, len(attempts))

    def test_task_list_failure_prevents_submit(self):
        calls = []
        client = module.P115OfflineClient("UID=x", request=lambda *a, **k: (calls.append(k.get("params", {}).get("ac")) or Response(503, {"code": 503})), sleep=lambda _v: None, max_retries=0)
        result = client.submit_magnet(magnet())
        self.assertFalse(result["success"])
        self.assertEqual("503", result["error_code"])
        self.assertEqual(["task_lists"], calls)

    def test_retry_uses_info_hash_payload(self):
        captured = {}
        def request(method, url, **kwargs):
            captured.update(kwargs.get("data") or {})
            return Response(payload={"state": True})
        client = module.P115OfflineClient("UID=x", request=request)
        result = client.retry_task("a" * 40)
        self.assertTrue(result["success"])
        self.assertEqual("a" * 40, captured.get("info_hash"))
        self.assertNotIn("hash[0]", captured)

    def test_explicit_false_state_is_not_success_even_with_zero_code(self):
        self.assertFalse(module.P115OfflineClient._response_success({"state": False, "code": 0}))

    def test_same_btih_is_serialized(self):
        calls = []

        def request(method, url, **kwargs):
            calls.append(kwargs.get("params", {}).get("ac", "sign"))
            if "space" in url:
                return Response(payload={"state": True, "sign": "s", "time": "1"})
            return Response(payload={"state": True, "data": {"info_hash": "a" * 40}})

        client = module.P115OfflineClient("UID=x", request=request)
        results = []
        threads = [threading.Thread(target=lambda: results.append(client.submit_magnet(magnet()))) for _ in range(4)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(1, calls.count("add_task_url"))
        self.assertEqual(4, len(results))
        self.assertTrue(all(item["success"] for item in results))


if __name__ == "__main__":
    unittest.main()
