import importlib.util
import sys
import types
import unittest
from pathlib import Path


logger = types.SimpleNamespace(info=lambda *_a, **_k: None, warn=lambda *_a, **_k: None)
sys.modules.setdefault("app", types.ModuleType("app"))
log_module = sys.modules.setdefault("app.log", types.ModuleType("app.log"))
log_module.logger = logger
PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "p115_transfer.py"
spec = importlib.util.spec_from_file_location("tgsearch115_p115_transfer", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ShareInspectionTest(unittest.TestCase):
    def test_inspection_reads_names_without_share_receive(self):
        client = module.P115Transfer("UID=x; CID=y; SEID=z")
        calls = []
        client._api_get = lambda path, params: calls.append((path, params)) or {
            "state": True, "data": {"list": [{"n": "Silo.S02.2024.1080p.CHINESE"}]}
        }
        client._api_post = lambda *_args, **_kwargs: self.fail("inspection must not post")

        ok, _message, names = client.inspect_share("https://115.com/s/demo?password=abcd")

        self.assertTrue(ok)
        self.assertEqual(["Silo.S02.2024.1080p.CHINESE"], names)
        self.assertEqual("/share/snap", calls[0][0])

    def test_inspection_requires_receive_code(self):
        client = module.P115Transfer("UID=x; CID=y; SEID=z")
        ok, _message, names = client.inspect_share("https://115.com/s/demo")
        self.assertFalse(ok)
        self.assertEqual([], names)

    def test_already_received_response_is_idempotent_success(self):
        client = module.P115Transfer(
            "UID=123_abc; CID=y; SEID=z", default_target_path="/target"
        )
        client.is_ready = lambda: (True, "")
        client._get_or_create_cid = lambda _path: "456"
        client._api_get = lambda *_args, **_kwargs: {
            "state": True, "data": {"list": [{"fid": "789"}]}
        }
        client._api_post = lambda *_args, **_kwargs: {
            "state": False, "error": "文件已接收，无需重复接收！"
        }

        ok, message, _data = client.transfer(
            "https://115.com/s/demo?password=abcd"
        )

        self.assertTrue(ok)
        self.assertIn("已存在", message)

    def test_numeric_default_target_remains_a_cid_for_manual_transfer(self):
        cid = "3469789358402308035"
        client = module.P115Transfer(
            "UID=123_abc; CID=y; SEID=z", default_target_path=cid
        )
        self.assertEqual(cid, client.default_target_path)
        client.is_ready = lambda: (True, "")
        client._get_or_create_cid = lambda _path: self.fail("numeric cid must not become a path")
        client._api_get = lambda *_args, **_kwargs: {
            "state": True, "data": {"list": [{"fid": "789"}]}
        }
        received = []
        client._api_post = lambda _path, payload, **_kwargs: received.append(payload) or {"state": True}

        ok, message, _data = client.transfer("https://115.com/s/demo?password=abcd")

        self.assertTrue(ok)
        self.assertEqual("115 转存成功", message)
        self.assertEqual(cid, received[-1]["cid"])

    def test_root_target_cid_zero_is_sent_without_directory_lookup(self):
        client = module.P115Transfer("UID=123_abc; CID=y; SEID=z", default_target_path="0")
        client.is_ready = lambda: (True, "")
        client._get_or_create_cid = lambda _path: self.fail("root cid must not become a path")
        client._api_get = lambda *_args, **_kwargs: {
            "state": True, "data": {"list": [{"fid": "789"}]}
        }
        received = []
        client._api_post = lambda _path, payload, **_kwargs: received.append(payload) or {"state": True}

        ok, _message, _data = client.transfer("https://115.com/s/demo?password=abcd")

        self.assertTrue(ok)
        self.assertEqual("0", received[-1]["cid"])

    def test_directory_share_uses_real_cid_as_receive_file_id(self):
        client = module.P115Transfer("UID=123_abc; CID=y; SEID=z", default_target_path="456")
        client.is_ready = lambda: (True, "")
        client._api_get = lambda *_args, **_kwargs: {
            "state": True, "data": {"list": [{"cid": "789", "n": "folder"}]}
        }
        received = []
        client._api_post = lambda _path, payload, **_kwargs: received.append(payload) or {"state": True}

        ok, _message, _data = client.transfer("https://115.com/s/demo?password=abcd")

        self.assertTrue(ok)
        self.assertEqual("789", received[-1]["file_id"])
        self.assertEqual("456", received[-1]["cid"])
        self.assertEqual({"share_code", "receive_code", "file_id", "cid"}, set(received[-1]))

    def test_share_snap_failure_never_submits_share_receive(self):
        client = module.P115Transfer("UID=123_abc; CID=y; SEID=z", default_target_path="456")
        client.is_ready = lambda: (True, "")
        client._api_get = lambda *_args, **_kwargs: {"state": False, "error": "bad params"}
        client._api_post = lambda *_args, **_kwargs: self.fail("share_receive must not run")

        ok, message, data = client.transfer("https://115.com/s/demo?password=abcd")

        self.assertFalse(ok)
        self.assertEqual("115 返回参数错误", message)
        self.assertEqual("share_snap", data["diagnostic"]["stage"])

    def test_missing_share_item_id_never_submits_share_receive(self):
        client = module.P115Transfer("UID=123_abc; CID=y; SEID=z", default_target_path="456")
        client.is_ready = lambda: (True, "")
        client._api_get = lambda *_args, **_kwargs: {"state": True, "data": {"list": [{"n": "unknown"}]}}
        client._api_post = lambda *_args, **_kwargs: self.fail("share_receive must not run")

        ok, _message, data = client.transfer("https://115.com/s/demo?password=abcd")

        self.assertFalse(ok)
        self.assertEqual("file_id", data["diagnostic"]["stage"])

    def test_share_receive_parameter_error_has_safe_stage_diagnostic(self):
        client = module.P115Transfer("UID=123_abc; CID=y; SEID=z", default_target_path="456")
        client.is_ready = lambda: (True, "")
        client._api_get = lambda *_args, **_kwargs: {
            "state": True, "data": {"list": [{"fid": "789"}]}
        }
        client._api_post = lambda *_args, **_kwargs: {"state": False, "code": "400", "error": "参数错误"}

        ok, message, data = client.transfer("https://115.com/s/demo?password=abcd")

        self.assertFalse(ok)
        self.assertEqual("115 返回参数错误", message)
        self.assertEqual("share_receive", data["diagnostic"]["stage"])
        self.assertEqual("400", data["diagnostic"]["error_code"])

    def test_transfer_source_does_not_log_sensitive_payloads(self):
        source = PATH.read_text(encoding="utf-8")
        self.assertNotIn("手动转存 share_url=", source)
        self.assertNotIn("转存 payload=", source)
        self.assertNotIn("share_snap 响应:", source)
        self.assertNotIn("share_receive 响应:", source)


if __name__ == "__main__":
    unittest.main()
