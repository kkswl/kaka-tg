# -*- coding: utf-8 -*-
"""115 Cookie Web cloud-download client.

The client deliberately exposes only redacted task metadata.  Network calls are
kept behind ``_request`` so all protocol and retry behavior can be tested with
synthetic responses; production uses the same httpx style as ``p115_transfer``.
"""
from __future__ import annotations

import base64
import binascii
import logging
import json
import re
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

logger = logging.getLogger("tgsearch115.p115_offline")

_HEX_BTIH = re.compile(r"^[0-9a-f]{40}$", re.I)
_BASE32_BTIH = re.compile(r"^[a-z2-7]{32}$", re.I)

# 115 lixianssp protocol constants.  The endpoint expects its JSON form body
# wrapped with the service's public-key codec; this is transport obfuscation,
# not a replacement for HTTPS.
_RSA_N = int("8686980c0f5a24c4b9d43020cd2c22703ff3f450756529058b1cf88f09b8602136477198a6e2683149659bd122c33592fdb5ad47944ad1ea4d36c6b172aad6338c3bb6ac6227502d010993ac967d1aef00f0c8e038de2e4d3bc2ec368af2e9f10a6f1eda4f7262f136420c07c331b871bf139f74f3010e3c4fe57df3afb71683", 16)
_RSA_E = 0x10001
_G_KEY_L = b"\x78\x06\xad\x4c\x33\x86\x5d\x18\x4c\x01\x3f\x46"
_RSA_KEY = b"\x8d\xa5\xa5\x8d"
_G_KTS = bytes.fromhex("f0e569aebfdcbf8a1a45e8be7da673b8de8fe7c445da86c49b648b146ab4f1aa3801359e26692c86006b4fa5363462a62a966818f24afdbd6b978f4d8f8913b76c8e93ed0e0d483ed72f88d8fefe7e8650954fd1eb832634db667b9c7e9d7a8132eab633de3aa95934663baaba816048b9d5819cf86c8477ff5478265fbee81e369f34805c452c9b76d51b8fccc3b8f5")


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(value ^ key[index % len(key)] for index, value in enumerate(data))


def _rsa_gen_key(seed: bytes, size: int = 4) -> bytes:
    result = bytearray(size); tail, index = size * (size - 1), 0
    for pos in range(size):
        result[pos] = _G_KTS[tail] ^ ((seed[pos] + _G_KTS[index]) & 0xff)
        tail -= size; index += size
    return bytes(result)


def _rsa_encrypt(data: bytes) -> str:
    body = bytes(16) + _xor(_xor(data, _RSA_KEY)[::-1], _G_KEY_L)
    encrypted = bytearray()
    for offset in range(0, len(body), 117):
        block = body[offset:offset + 117]
        padded = b"\x00\x02" + b"\x02" * (125 - len(block)) + b"\x00" + block
        encrypted.extend(pow(int.from_bytes(padded, "big"), _RSA_E, _RSA_N).to_bytes(128, "big"))
    return base64.b64encode(encrypted).decode("ascii")


def _rsa_decrypt(value: str) -> bytes:
    cipher = base64.b64decode(value); plain = bytearray()
    for offset in range(0, len(cipher), 128):
        number = pow(int.from_bytes(cipher[offset:offset + 128], "big"), _RSA_E, _RSA_N)
        block = number.to_bytes(max(1, (number.bit_length() + 7) // 8), "big")
        plain.extend(block[block.index(0) + 1:])
    seed, payload = bytes(plain[:16]), bytes(plain[16:])
    return _xor(_xor(payload, _rsa_gen_key(seed, 12))[::-1], _RSA_KEY)


class OfflineHttpError(RuntimeError):
    def __init__(self, status: int, message: str, error_code: str = "") -> None:
        super().__init__(message)
        self.status = int(status or 0)
        self.error_code = str(error_code or status or "http_error")


class _DictResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any], headers: Any = None):
        self.status_code, self._payload, self.headers = status_code, payload, headers or {}

    def json(self) -> Dict[str, Any]:
        return self._payload


def normalize_btih(value: Any) -> str:
    """Return a canonical 40-character hexadecimal BTIH or ``""``."""
    text = str(value or "").strip().lower()
    if _HEX_BTIH.fullmatch(text):
        return text
    if _BASE32_BTIH.fullmatch(text):
        try:
            return binascii.hexlify(base64.b32decode(text.upper())).decode("ascii").lower()
        except (binascii.Error, ValueError):
            return ""
    return ""


def btih_from_magnet(magnet: str) -> str:
    parsed = urlparse(str(magnet or "").strip())
    if parsed.scheme.lower() != "magnet":
        return ""
    values = parse_qs(parsed.query).get("xt", [])
    for value in values:
        match = re.search(r"urn:btih:([^&]+)", value, re.I)
        if match:
            return normalize_btih(match.group(1))
    return ""


class P115OfflineClient:
    """Cookie-authenticated 115 Web cloud-download API.

    ``request`` may be injected as ``request(method, url, **kwargs)`` for tests.
    The default implementation uses httpx and never inherits process proxies.
    """

    SIGN_URL = "https://115.com/?ct=clouddownload&ac=space"
    TASK_URL = "https://clouddownload.115.com/web/"
    SSP_URL = "https://clouddownload.115.com/lixianssp/"

    def __init__(self, cookie: str = "", target_cid: Any = 0,
                 request: Optional[Callable[..., Any]] = None,
                 sleep: Callable[[float], None] = time.sleep,
                 max_retries: int = 3, backoff_base: float = 1.0) -> None:
        self.cookie = str(cookie or "").strip()
        self.target_cid = str(target_cid or 0)
        self._request_impl = request
        self._sleep = sleep
        self.max_retries = max(0, int(max_retries))
        self.backoff_base = max(0.1, float(backoff_base))
        self._locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._submitted: Dict[str, Dict[str, Any]] = {}
        self.last_http_status = 0

    @staticmethod
    def _valid_magnet(magnet: str) -> bool:
        return bool(btih_from_magnet(magnet))

    def submit_magnet(self, magnet: str, target_cid: Any = None) -> Dict[str, Any]:
        btih = btih_from_magnet(magnet)
        if not btih:
            return self._result(False, "", "", "invalid_btih", "磁力链接缺少有效 BTIH")
        lock = self._lock_for(btih)
        with lock:
            try:
                cached = self._submitted.get(btih)
                if cached:
                    state = self.get_task_status(cached.get("task_id") or btih)
                    if state.get("status") not in {"failed", "cancelled"} and state.get("task_id"):
                        duplicate = dict(cached)
                        duplicate.update({"status": state.get("status") or duplicate.get("status"), "progress": state.get("progress"), "message": "相同 BTIH 的 115 任务已存在"})
                        return duplicate
                    self._submitted.pop(btih, None)
                existing = self._find_existing(btih)
                if existing:
                    return self._result(True, existing.get("task_id", btih), btih,
                                        "already_exists", "相同 BTIH 的 115 任务已存在",
                                        status=existing.get("status", "submitted"),
                                        progress=existing.get("progress"))
                sign = self._get_sign()
                payload = {"url": str(magnet), "wp_path_id": str(target_cid if target_cid is not None else self.target_cid),
                           "sign": sign["sign"], "time": sign["time"]}
                response = self._call("POST", self.SSP_URL, params={"ac": "add_task_url"}, data=payload)
                task_id = self._task_id(response) or btih
                ok = self._response_success(response)
                result = self._result(ok, task_id, btih, "" if ok else self._error_code(response),
                                    "115 磁力任务已提交" if ok else self._message(response),
                                    status="submitted" if ok else "failed")
                if ok:
                    self._submitted[btih] = dict(result)
                return result
            except OfflineHttpError as exc:
                return self._result(False, "", btih, exc.error_code, str(exc), status="failed")
            except Exception as exc:
                logger.warning("115 offline request failed status=%s error=%s", self.last_http_status, type(exc).__name__)
                return self._result(False, "", btih, "network_error", "115 网络请求失败", status="failed")

    def list_tasks(self, page: int = 1, page_size: int = 30,
                   stat: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"ac": "task_lists", "page": int(page), "page_size": int(page_size)}
        if stat is not None:
            params["stat"] = int(stat)
        response = self._call("GET", self.TASK_URL, params=params)
        raw = response.get("tasks") if isinstance(response, dict) else None
        if raw is None and isinstance(response, dict):
            data = response.get("data")
            raw = data.get("tasks") if isinstance(data, dict) else data
        if not isinstance(raw, list):
            raw = []
        return [self._normalize_task(item) for item in raw if isinstance(item, dict)]

    def probe_capabilities(self) -> Dict[str, Any]:
        """Read-only auth/capability probe with no task metadata disclosure."""
        try:
            sign = self._get_sign()
            tasks = self.list_tasks(page=1, page_size=30)
            present = set()
            for task in tasks:
                for key in ("task_id", "btih", "status", "progress", "error_code"):
                    if task.get(key) not in (None, ""):
                        present.add(key)
            return {"success": True, "authenticated": True, "has_sign": bool(sign.get("sign") and sign.get("time")), "task_count": len(tasks), "task_fields": sorted(present), "http_status": self.last_http_status, "message": "115 云下载只读接口可用"}
        except OfflineHttpError as exc:
            return {"success": False, "authenticated": exc.status not in (401, 403), "has_sign": False, "task_count": 0, "task_fields": [], "http_status": exc.status, "message": str(exc)}
        except Exception:
            return {"success": False, "authenticated": False, "has_sign": False, "task_count": 0, "task_fields": [], "http_status": self.last_http_status, "message": "115 云下载只读探测失败"}

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        key = str(task_id or "").strip()
        if not key:
            return self._result(False, "", "", "invalid_task_id", "任务 ID 无效", status="failed")
        response = self._call("GET", self.TASK_URL, params={"ac": "get_user_task", "info_hash": key})
        task = response.get("task") if isinstance(response, dict) else None
        if not isinstance(task, dict):
            data = response.get("data") if isinstance(response, dict) else None
            task = data if isinstance(data, dict) else response
        normalized = self._normalize_task(task if isinstance(task, dict) else {})
        # get_user_task can keep reporting a running status after 115 has
        # already moved the files into the cloud drive.  task_lists(stat=11)
        # is the service's authoritative completed bucket.
        if normalized.get("status") not in {"completed", "failed", "cancelled"}:
            completed = self._find_in_task_bucket(key, stat=11)
            if completed:
                completed["status"] = "completed"
                if completed.get("progress") is None:
                    completed["progress"] = 100.0
                return completed
        return normalized

    def _find_in_task_bucket(self, task_id: str, stat: int) -> Optional[Dict[str, Any]]:
        key = normalize_btih(task_id) or str(task_id or "").strip().lower()
        for task in self.list_tasks(page=1, page_size=30, stat=stat):
            if key in {
                str(task.get("task_id") or "").strip().lower(),
                str(task.get("btih") or "").strip().lower(),
            }:
                return task
        return None

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        return self._mutate_task("task_del", task_id, "cancelled")

    def retry_task(self, task_id: str) -> Dict[str, Any]:
        return self._mutate_task("restart", task_id, "submitted")

    def forget_task(self, btih: str) -> None:
        """Forget only the process-local success cache after terminal failure."""
        self._submitted.pop(normalize_btih(btih), None)

    @classmethod
    def normalize_status(cls, payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {"status": "failed", "progress": None, "error_code": "invalid_response", "message": "115 返回格式无效", "task_id": "", "btih": ""}
        raw = payload.get("status", payload.get("stat", payload.get("state", payload.get("status_code"))))
        if isinstance(raw, str):
            value = raw.strip().lower()
            if value.lstrip("-").isdigit():
                status = {-1: "failed", 0: "cancelled", 1: "downloading", 2: "completed", 9: "failed", 11: "completed", 12: "downloading"}.get(int(value), "submitted")
            else:
                status = {"success": "completed", "completed": "completed", "done": "completed", "running": "downloading", "downloading": "downloading", "stopped": "cancelled", "cancelled": "cancelled", "failed": "failed", "error": "failed"}.get(value, "submitted")
        else:
            status = {-1: "failed", 0: "cancelled", 1: "downloading", 2: "completed", 9: "failed", 11: "completed", 12: "downloading"}.get(int(raw) if str(raw).lstrip("-").isdigit() else -999, "submitted")
        progress = payload.get("percent", payload.get("progress", payload.get("completed_percent")))
        try:
            progress = float(progress) if progress is not None else None
        except (TypeError, ValueError):
            progress = None
        return {"status": status, "progress": progress, "error_code": str(payload.get("error_code", payload.get("errno", "")) or ""), "message": str(payload.get("error", payload.get("message", payload.get("msg", ""))) or "")[:300], "task_id": str(payload.get("task_id", payload.get("info_hash", payload.get("hash", ""))) or ""), "btih": normalize_btih(payload.get("btih", payload.get("info_hash", ""))), "target_cid": str(payload.get("wp_path_id", payload.get("save_path_id", "")) or ""), "name": str(payload.get("name", payload.get("file_name", payload.get("savepath", ""))) or "")[:240]}

    def _mutate_task(self, action: str, task_id: str, status: str) -> Dict[str, Any]:
        key = str(task_id or "").strip()
        if not key:
            return self._result(False, "", "", "invalid_task_id", "任务 ID 无效", status="failed")
        try:
            data = {"hash[0]": key} if action == "task_del" else {"info_hash": key}
            response = self._call("POST", self.TASK_URL, params={"ac": action}, data=data)
            ok = self._response_success(response)
            return self._result(ok, key, normalize_btih(key), "" if ok else self._error_code(response), "操作成功" if ok else self._message(response), status=status if ok else "failed")
        except OfflineHttpError as exc:
            return self._result(False, key, normalize_btih(key), exc.error_code, str(exc), status="failed")

    def _get_sign(self) -> Dict[str, str]:
        response = self._call("GET", self.SIGN_URL)
        data = response.get("data") if isinstance(response, dict) else None
        source = data if isinstance(data, dict) else response
        sign, stamp = str(source.get("sign", "") or ""), str(source.get("time", source.get("timestamp", "")) or "")
        if not sign or not stamp:
            raise OfflineHttpError(self.last_http_status, "115 未返回离线签名", "missing_sign")
        return {"sign": sign, "time": stamp}

    def _call(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._request(method, url, **kwargs)
                status = int(getattr(response, "status_code", 200) or 200)
                self.last_http_status = status
                if status in (401, 403):
                    raise OfflineHttpError(status, "115 鉴权失败", str(status))
                if status == 429 or status >= 500:
                    if attempt < self.max_retries:
                        self._sleep(self._retry_delay(response, attempt)); continue
                    raise OfflineHttpError(status, "115 服务暂时不可用", str(status))
                if isinstance(response, dict):
                    return response
                try:
                    return response.json()
                except Exception as exc:
                    raise OfflineHttpError(status, "115 返回非 JSON", "invalid_json") from exc
            except OfflineHttpError:
                raise
            except Exception as exc:
                if attempt < self.max_retries:
                    self._sleep(self.backoff_base * (2 ** attempt)); continue
                raise OfflineHttpError(self.last_http_status, "115 网络请求失败", "network_error") from exc
        raise OfflineHttpError(self.last_http_status, "115 请求失败", "request_failed")

    def _request(self, method: str, url: str, **kwargs) -> Any:
        if self._request_impl:
            return self._request_impl(method, url, **kwargs)
        import httpx
        headers = {"User-Agent": "Mozilla/5.0 (MoviePilot-TgSearch115)", "Accept": "application/json, text/plain, */*", "Cookie": self.cookie}
        if method.upper() == "POST" and url.rstrip("/") == self.SSP_URL.rstrip("/"):
            payload = dict(kwargs.pop("data", {}) or {})
            payload.update(kwargs.get("params", {}) or {})
            kwargs.pop("params", None)
            payload.setdefault("app_ver", "36.2.28")
            headers["User-Agent"] = "Mozilla/5.0 115disk/36.2.28 115Browser/36.2.28 115wangpan_android/36.2.28"
            kwargs["data"] = {"data": _rsa_encrypt(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))}
        with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True, trust_env=False) as client:
            response = client.request(method, url, **kwargs)
            if method.upper() == "POST" and url.rstrip("/") == self.SSP_URL.rstrip("/"):
                try:
                    parsed = response.json()
                    if isinstance(parsed, dict) and isinstance(parsed.get("data"), str):
                        parsed["data"] = json.loads(_rsa_decrypt(parsed["data"]).decode("utf-8"))
                    return _DictResponse(response.status_code, parsed, response.headers)
                except Exception:
                    return response
            return response

    def _find_existing(self, btih: str) -> Optional[Dict[str, Any]]:
        for task in self.list_tasks():
            if task.get("btih") == btih or task.get("task_id") == btih:
                return task
        return None

    def _lock_for(self, btih: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(btih, threading.Lock())

    @classmethod
    def _normalize_task(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized = cls.normalize_status(payload)
        task_id = normalized["task_id"] or str(payload.get("id", "") or "")
        normalized.update({"task_id": task_id, "btih": normalized["btih"] or normalize_btih(payload.get("hash", ""))})
        return normalized

    @staticmethod
    def _response_success(response: Any) -> bool:
        if not isinstance(response, dict): return False
        if response.get("state") in (False, 0, "0"):
            return False
        code = response.get("code", response.get("errno"))
        return response.get("state") in (True, 1, "1") or code in (0, "0", 200, "200")

    @staticmethod
    def _task_id(response: Any) -> str:
        if not isinstance(response, dict): return ""
        data = response.get("data") if isinstance(response.get("data"), dict) else response
        return str(data.get("info_hash", data.get("task_id", data.get("id", ""))) or "")

    @staticmethod
    def _error_code(response: Any) -> str:
        return str(response.get("code", response.get("errno", "task_failed")) if isinstance(response, dict) else "task_failed")

    @staticmethod
    def _message(response: Any) -> str:
        return str(response.get("message", response.get("msg", response.get("error", "115 任务失败"))) if isinstance(response, dict) else "115 任务失败")[:300]

    def _result(self, success: bool, task_id: str, btih: str, error_code: str, message: str, status: str = "waiting", progress: Any = None) -> Dict[str, Any]:
        return {"success": bool(success), "task_id": str(task_id or ""), "btih": normalize_btih(btih) or str(btih or ""), "status": status, "message": str(message or "")[:300], "error_code": str(error_code or ""), "progress": progress}

    def _retry_delay(self, response: Any, attempt: int) -> float:
        headers = getattr(response, "headers", {}) or {}
        value = headers.get("Retry-After") if hasattr(headers, "get") else None
        try: return max(0.0, float(value))
        except (TypeError, ValueError): return self.backoff_base * (2 ** attempt)
