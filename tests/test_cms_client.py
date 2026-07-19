import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins.v2"
    / "tgsearch115"
    / "cms_client.py"
)
spec = importlib.util.spec_from_file_location("tgsearch115_cms_client", MODULE_PATH)
cms_client = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cms_client
spec.loader.exec_module(cms_client)


class _Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Client:
    def __init__(self, response, calls):
        self.response = response
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url):
        self.calls.append(("GET", url, None))
        return self.response

    def post(self, url, json):
        self.calls.append(("POST", url, json))
        return self.response


def _factory(response, calls):
    def build(**kwargs):
        calls.append(("CLIENT", kwargs, None))
        return _Client(response, calls)
    return build


class Cms115ClientTest(unittest.TestCase):
    def test_submits_documented_payload_without_environment_proxy(self):
        calls = []
        client = cms_client.Cms115Client(
            "http://cms.local/",
            "secret-token",
            client_factory=_factory(_Response(payload={"code": "200", "msg": "ok"}), calls),
        )

        ok, message = client.add_magnet("magnet:?xt=urn:btih:" + "a" * 40)

        self.assertTrue(ok)
        self.assertEqual("ok", message)
        self.assertEqual(False, calls[0][1]["trust_env"])
        self.assertEqual(
            "http://cms.local/api/cloud/add_share_down_by_token", calls[1][1]
        )
        self.assertEqual("secret-token", calls[1][2]["token"])

    def test_rejects_invalid_magnet_without_request(self):
        calls = []
        client = cms_client.Cms115Client(
            "http://cms.local", "token",
            client_factory=_factory(_Response(payload={"code": 200}), calls),
        )

        ok, message = client.add_magnet("https://example.com/file")

        self.assertFalse(ok)
        self.assertIn("无效", message)
        self.assertEqual([], calls)

    def test_rejects_non_success_business_status(self):
        calls = []
        client = cms_client.Cms115Client(
            "http://cms.local", "token",
            client_factory=_factory(_Response(payload={"code": 500, "msg": "failed"}), calls),
        )

        ok, message = client.add_magnet("magnet:?xt=urn:btih:" + "b" * 40)

        self.assertFalse(ok)
        self.assertEqual("failed", message)


if __name__ == "__main__":
    unittest.main()
