# -*- coding: utf-8 -*-
"""115 网盘分享链接转存 + 目录操作（httpx + Cookie，无 p115client 依赖）。

背景：MoviePilot 内置的 ``U115Pan`` 是 OAuth 存储模块，不含分享链接转存接口。
115 转存属于 Cookie 鉴权的 Web API。早期版本用 ``p115client``，但它依赖很重
（拖一堆传递依赖），在 Docker 内 ``pip install`` 很慢、拖慢插件加载。本模块改用
``httpx``（tg_scraper/site_scraper 已依赖，轻量）直连 115 Web API，零额外依赖。

调用端点（Cookie 鉴权；转存/列目录用 webapi.115.com，目录名/建目录用 proapi 开放 API，
均与 p115client 内部端点逐一核对一致）：
  - 转存：GET  webapi /share/snap?share_code=&receive_code=&cid=0  -> 取真实 fid/cid
         POST webapi /share/receive  (form: share_code,receive_code,file_id,cid)
  - 列目录/验证 Cookie：GET webapi /files?cid={cid}&limit=50  (返回 cid/n/sha1)
  - 目录名：GET proapi /open/folder/get_info?file_id={cid}
  - 建目录：POST proapi /open/folder/add  (form: file_name, pid)
"""
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlparse

from app.log import logger


class P115Transfer:
    """115 分享链接转存 + 目录操作执行器（httpx + Cookie，无 p115client）。"""

    CLIENT_COOKIE_REQUIRED_KEYS = {"UID", "CID", "SEID"}
    _API = "https://webapi.115.com"
    _PROAPI = "https://proapi.115.com"  # 开放 API（与 p115client 的 fs_info/fs_mkdir 一致）

    def __init__(self, cookie: str = "", default_target_path: str = "/") -> None:
        self.cookie = self._normalize(cookie)
        # Config.vue can save a directory browser result as a numeric cid.  It
        # must remain a cid here: turning ``123`` into ``/123`` makes the
        # default-transfer path try to create a directory literally named 123.
        configured_target = self._normalize(default_target_path)
        self.default_target_path = (
            configured_target if configured_target.isdigit()
            else self._normalize_path(configured_target) or "/"
        )
        self._http = None  # 懒加载 httpx.Client

    # ============================ 公共方法 ============================
    def is_ready(self) -> Tuple[bool, str]:
        """检查 Cookie 是否可用。"""
        if not self.cookie:
            return False, "未配置 115 Cookie"
        ok, msg = self.validate_cookie(self.cookie)
        if not ok:
            return False, msg
        return True, ""

    @classmethod
    def validate_cookie(cls, cookie: str) -> Tuple[bool, str]:
        if not cls._normalize(cookie):
            return False, "115 Cookie 为空"
        pairs = cls._parse_cookie_pairs(cookie)
        missing = sorted(cls.CLIENT_COOKIE_REQUIRED_KEYS - set(pairs))
        if missing:
            return False, (
                f"115 Cookie 缺少 {'/'.join(missing)}，请使用 115 客户端扫码登录得到的 "
                f"Cookie（网页版 Cookie 无法转存）"
            )
        return True, ""

    def transfer(self, share_url: str, target_path: str = "") -> Tuple[bool, str, Dict[str, Any]]:
        """转存分享链接到目标目录。

        :param share_url: 115 分享链接（含提取码），如 ``https://115.com/s/xxxxxxxx?password=yyyy``
        :param target_path: 115 目标目录路径（如 ``/电影``）或数字 cid。留空用默认目录。
        :return: (ok, message, data)
        """
        share_url = self._normalize(share_url)
        effective = self._normalize(target_path) or self.default_target_path
        # Keep return diagnostics safe: callers may expose this structure in a
        # plugin API response, so it must never contain a share URL or code.
        result: Dict[str, Any] = {"diagnostic": {"stage": "input"}}

        if not share_url or not self._is_115_share_url(share_url):
            return self._transfer_failure(result, "share_url", "不是有效的 115 分享链接")

        ok, msg = self.is_ready()
        if not ok:
            return self._transfer_failure(result, "cookie", msg)

        share_code, receive_code = self._extract_payload(share_url)
        if not share_code or not receive_code:
            return self._transfer_failure(result, "share_url", "解析 115 分享链接失败，缺少分享码或提取码")

        logger.info("【TG115】115 分享转存请求已接收")
        # 目标目录：纯数字视为 cid 直接用；否则按路径查找/创建
        try:
            if effective.isdigit():
                parent_id = effective
            else:
                parent_id = self._get_or_create_cid(effective)
        except Exception as e:
            return self._transfer_failure(
                result, "target_cid", f"定位 115 目标目录失败（{type(e).__name__}）"
            )
        parent_id = str(parent_id or "").strip()
        if not parent_id.isdigit():
            return self._transfer_failure(result, "target_cid", "115 目标目录不是有效 CID")

        # 1. share_snap 获取分享根目录的真实可接收项。115 的 share_receive
        # 需要分享空间内的 fid/cid；绝不能在读取失败后伪造 file_id=0。
        try:
            snap = self._api_get("/share/snap", {
                "share_code": share_code, "receive_code": receive_code,
                "cid": 0, "limit": 32, "offset": 0,
            })
        except Exception as e:
            logger.warning("【TG115】share_snap 异常 type=%s", type(e).__name__)
            return self._transfer_failure(result, "share_snap", "无法读取 115 分享元数据")
        if not self._response_ok(snap):
            return self._transfer_failure(
                result, "share_snap", self._safe_115_message(snap, "115 拒绝读取分享元数据")
            )
        file_ids, item_count = self._share_receive_file_ids(snap)
        logger.info(
            "【TG115】share_snap 已读取 items=%s has_file_id=%s target_cid_numeric=%s",
            item_count, bool(file_ids), parent_id.isdigit(),
        )
        if not file_ids:
            return self._transfer_failure(
                result, "file_id", "分享元数据未提供可接收的文件或目录 ID，未提交转存"
            )

        # 2. share_receive only accepts the documented share identifiers.
        # The local p115client reference does not send user_id; an extra field
        # can be rejected by stricter 115 deployments.
        payload = {
            "share_code": share_code,
            "receive_code": receive_code,
            "file_id": file_ids,
            "cid": parent_id,
        }
        try:
            resp = self._api_post("/share/receive", payload)
            logger.info(
                "【TG115】share_receive 完成 ok=%s file_id_present=%s cid_numeric=%s",
                bool(self._response_ok(resp)), bool(file_ids), parent_id.isdigit(),
            )
        except Exception as e:
            logger.error("【TG115】share_receive 异常 type=%s", type(e).__name__)
            return self._transfer_failure(result, "share_receive", "调用 115 接收接口失败")

        if not self._response_ok(resp):
            # Idempotency must inspect the original response before mapping it
            # to a safe public error category, otherwise wording such as
            # “文件已接收” would be lost.
            if self._is_already_saved(self._response_error(resp)):  # 已转存视为成功（幂等）
                result["diagnostic"] = {"stage": "share_receive", "status": "already_saved"}
                return True, "115 转存已存在（之前已转存）", result
            err = self._safe_115_message(resp, "115 接收失败")
            return self._transfer_failure(result, "share_receive", err, self._response_code(resp))

        result["diagnostic"] = {"stage": "share_receive", "status": "accepted"}
        return True, "115 转存成功", result

    @staticmethod
    def _share_receive_file_ids(snap: Any) -> Tuple[str, int]:
        """Return documented share-space IDs for share_receive, never a fake 0."""
        data = snap.get("data") if isinstance(snap, dict) else None
        items = (data.get("list") or data.get("filelist") or []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            return "", 0
        ids = []
        for item in items:
            if not isinstance(item, dict):
                continue
            # Files use fid/file_id. Directories use their cid; share_receive
            # accepts either as file_id according to the 115 client reference.
            value = item.get("fid") or item.get("file_id") or item.get("cid")
            value = str(value or "").strip()
            if value.isdigit() and value != "0" and value not in ids:
                ids.append(value)
        return ",".join(ids), len(items)

    def _snap_names(self, share_code: str, receive_code: str, cid: Any = 0,
                    limit: int = 32) -> Tuple[bool, list]:
        """请求 share/snap 返回 (ok, items)。items 为 list[dict]，不含敏感信息。"""
        try:
            response = self._api_get("/share/snap", {
                "share_code": share_code, "receive_code": receive_code,
                "cid": cid, "limit": max(1, min(int(limit), 32)), "offset": 0,
            })
        except Exception:
            return False, []
        if not self._response_ok(response):
            return False, []
        data = response.get("data") if isinstance(response, dict) else None
        items = (data.get("list") or data.get("filelist") or []) \
            if isinstance(data, dict) else []
        return True, items if isinstance(items, list) else []

    def inspect_share(self, share_url: str, limit: int = 12) -> Tuple[bool, str, list[str]]:
        """Read share names only. This never calls share_receive or modifies 115.

        对目录分享会递归向下查最多 2 层，收集真实文件名用于中字检测。
        例如 ``根目录 → 季目录 → 剧集文件/字幕文件`` 这种结构，递归后能拿到
        ``.ass``/``.srt`` 字幕文件名，使 ``has_chinese_subtitle_file`` 能正确识别。
        """
        share_code, receive_code = self._extract_payload(share_url)
        if not share_code or not receive_code:
            return False, "分享缺少提取码，无法只读识别", []
        ok, message = self.is_ready()
        if not ok:
            return False, message, []

        root_limit = max(1, min(int(limit), 32))
        max_names = 60          # 收集名称上限，足够中字检测
        max_subdirs = 8         # 每层最多递归的子目录数

        names: list[str] = []

        def collect(items: list) -> list:
            """从 items 收集文件名，返回其中的目录 cid 列表（sha1 为空=目录）。"""
            sub_dirs: list[str] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("n") or item.get("name") or item.get("file_name") or "").strip()
                if name and name not in names:
                    names.append(name[:300])
                if not item.get("sha1"):
                    cid_val = item.get("cid")
                    if cid_val:
                        sub_dirs.append(str(cid_val))
            return sub_dirs

        # 第 0 层：分享根（cid=0）
        ok0, items0 = self._snap_names(share_code, receive_code, cid=0, limit=root_limit)
        if not ok0:
            return False, "115 分享不可读取", []
        root_dirs = collect(items0)

        # 第 1 层：递归根目录
        for cid in root_dirs[:max_subdirs]:
            if len(names) >= max_names:
                break
            ok1, items1 = self._snap_names(share_code, receive_code, cid=cid, limit=32)
            if not ok1:
                continue
            sub_dirs = collect(items1)
            # 第 2 层：再递归一层（针对 季→剧集目录→文件 这种结构）
            for sub_cid in sub_dirs[:max_subdirs]:
                if len(names) >= max_names:
                    break
                ok2, items2 = self._snap_names(share_code, receive_code, cid=sub_cid, limit=32)
                if not ok2:
                    continue
                collect(items2)

        return (True, "115 分享文件名已读取", names) if names else (False, "115 分享没有可识别文件名", [])

    # ============================ 目录操作（供 __init__ 的浏览/验证 API 用）============================
    def fs_files(self, cid: Any = 0) -> Dict[str, Any]:
        """列某 cid 下的内容（GET /files）。cid=0 为根目录。返回 115 原始 JSON dict。"""
        return self._api_get("/files", {"cid": str(cid or 0), "limit": 50, "offset": 0})

    def fs_info(self, cid: Any) -> Dict[str, Any]:
        """查某 cid 的信息（GET proapi /open/folder/get_info?file_id=，与 p115client 一致）。
        返回 115 原始 JSON dict。"""
        return self._api_get("/open/folder/get_info", {"file_id": str(cid)}, base=self._PROAPI)

    # ============================ 内部工具 ============================
    def _get_or_create_cid(self, path: str) -> str:
        """根据路径获取目录 cid，不存在则创建。根目录返回 '0'。

        逐段导航：从根 cid=0 开始，对路径每一段在当前目录下查找同名子目录；
        找不到则 POST /files/add 创建。返回最终 cid（字符串）。
        """
        target = self._normalize_path(path) or "/"
        if target == "/":
            return "0"
        pid = "0"
        for seg in target.strip("/").split("/"):
            seg = seg.strip()
            if not seg:
                continue
            # 在 pid 下找同名目录
            cid = self._find_subdir(pid, seg)
            if cid:
                pid = cid
                continue
            # 不存在则创建
            cid = self._mkdir(pid, seg)
            if not cid:
                raise RuntimeError(f"无法创建 115 目录: {seg}（请手动创建 {target} 后重试）")
            pid = cid
        return pid

    def _find_subdir(self, parent_cid: str, name: str) -> str:
        """在 parent_cid 下查找名为 name 的子目录 cid，找不到返回 ''。"""
        try:
            resp = self.fs_files(parent_cid)
        except Exception:
            return ""
        if not isinstance(resp, dict) or resp.get("state") not in (True, 1, "1"):
            return ""
        data = resp.get("data")
        items = data if isinstance(data, list) else (data.get("data", []) if isinstance(data, dict) else [])
        for it in items:
            if not isinstance(it, dict):
                continue
            if it.get("sha1"):  # 文件才有 sha1，跳过
                continue
            n = it.get("name") or it.get("n") or ""
            if n == name:
                return str(it.get("cid", it.get("id", "")))
        return ""

    def _mkdir(self, parent_cid: str, name: str) -> str:
        """在 parent_cid 下创建子目录 name（POST proapi /open/folder/add {file_name, pid}，
        与 p115client fs_mkdir 一致）。创建后重新列父目录按名取新 cid（不依赖响应里的
        cid 字段，避免响应格式差异），失败返回 ''。"""
        try:
            self._api_post("/open/folder/add",
                           {"file_name": name, "pid": str(parent_cid)}, base=self._PROAPI)
        except Exception as e:
            logger.warn(f"【TG115】创建目录 {name} 异常: {e}")
            return ""
        # 重新列父目录按名找到新建目录 cid（可靠，不依赖 create 响应格式）
        return self._find_subdir(parent_cid, name)

    def _client(self):
        """懒加载 httpx.Client（带 Cookie + Chrome UA + 20s 超时）。"""
        if self._http is not None:
            return self._http
        import httpx
        self._http = httpx.Client(
            timeout=20.0,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cookie": self.cookie,
            },
            follow_redirects=True,
            trust_env=False,  # 115 接口直连，彻底绕过 docker HTTP_PROXY 环境变量
        )
        return self._http

    def _api_get(self, path: str, params: Dict[str, Any], base: str = None) -> Dict[str, Any]:
        from urllib.parse import urlencode
        base = base or self._API
        url = f"{base}{path}?{urlencode(params)}"
        resp = self._client().get(url)
        return self._parse_json(resp)

    def _api_post(self, path: str, data: Dict[str, Any], base: str = None) -> Dict[str, Any]:
        base = base or self._API
        url = f"{base}{path}"
        resp = self._client().post(url, data=data,
                                   headers={"Content-Type": "application/x-www-form-urlencoded"})
        return self._parse_json(resp)

    @staticmethod
    def _parse_json(resp) -> Dict[str, Any]:
        import json as _json
        try:
            return resp.json()
        except Exception:
            try:
                return _json.loads(resp.text)
            except Exception:
                return {"state": False, "error": resp.text[:200]}

    @staticmethod
    def _extract_payload(url: str) -> Tuple[str, str]:
        """从 115 分享链接解析 share_code / receive_code。"""
        url = str(url or "").strip()
        if not url:
            return "", ""
        parsed = urlparse(url)
        share_code = ""
        m = re.search(r"/s/([^/?#]+)", parsed.path or "")
        if m:
            share_code = m.group(1).strip()
        q = dict(parse_qsl(parsed.query, keep_blank_values=True))
        receive_code = str(
            q.get("password") or q.get("receive_code") or q.get("pwd") or ""
        ).strip()
        return share_code, receive_code

    @staticmethod
    def _is_115_share_url(url: str) -> bool:
        host = urlparse(str(url or "")).netloc.lower()
        return (
            host == "115.com"
            or host.endswith(".115.com")
            or "115cdn.com" in host
            or host == "anxia.com"
        )

    @staticmethod
    def _normalize(v: Any) -> str:
        return "" if v is None else str(v).strip()

    @staticmethod
    def _normalize_path(v: Any) -> str:
        t = str(v or "").strip()
        if not t:
            return ""
        if not t.startswith("/"):
            t = "/" + t
        return t.rstrip("/") or "/"

    @classmethod
    def _parse_cookie_pairs(cls, cookie: str) -> Dict[str, str]:
        pairs: Dict[str, str] = {}
        for part in cls._normalize(cookie).strip(";").split(";"):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and v:
                pairs[k] = v
        return pairs

    @staticmethod
    def _safe_int(v: Any, default: int = -1) -> int:
        try:
            return int(v)
        except Exception:
            return default

    @staticmethod
    def _response_ok(resp: Any) -> bool:
        if not isinstance(resp, dict):
            return False
        if resp.get("state") is True:
            return True
        if resp.get("code") in (0, "0") and resp.get("state") not in (False, 0):
            return True
        if resp.get("errno") in (0, "0") and resp.get("state") not in (False, 0):
            return True
        return False

    @staticmethod
    def _response_error(resp: Any) -> str:
        if not isinstance(resp, dict):
            return str(resp or "")
        for k in ("error", "message", "msg", "errno"):
            v = resp.get(k)
            if v not in (None, ""):
                return str(v)
        return str(resp)

    @staticmethod
    def _response_code(resp: Any) -> str:
        if not isinstance(resp, dict):
            return ""
        for key in ("code", "errno", "status"):
            value = resp.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()[:32]
        return ""

    @classmethod
    def _safe_115_message(cls, resp: Any, fallback: str) -> str:
        """Return a useful but non-sensitive 115 error category."""
        text = cls._response_error(resp).strip().lower()
        if "参数" in text or "param" in text:
            return "115 返回参数错误"
        if "提取码" in text or "password" in text or "receive" in text:
            return "115 拒绝分享提取码"
        if "分享" in text or "share" in text:
            return "115 拒绝该分享资源"
        if "登录" in text or "cookie" in text or "auth" in text:
            return "115 登录状态或权限无效"
        return fallback

    @staticmethod
    def _transfer_failure(
            result: Dict[str, Any], stage: str, message: str, error_code: str = ""
    ) -> Tuple[bool, str, Dict[str, Any]]:
        diagnostic = {"stage": stage, "status": "failed"}
        if error_code:
            diagnostic["error_code"] = error_code
        result["diagnostic"] = diagnostic
        return False, message, result

    @staticmethod
    def _is_already_saved(text: Any) -> bool:
        t = str(text or "")
        return any(m in t for m in (
            "已经转存", "已转存", "已经保存", "已保存", "已接收", "无需重复接收",
            "already", "exist",
        ))

    @staticmethod
    def _jsonable(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, (str, int, float, bool, list, dict)):
            return v
        if hasattr(v, "model_dump"):
            try:
                return v.model_dump()
            except Exception:
                pass
        if hasattr(v, "__dict__"):
            return {k: val for k, val in vars(v).items() if not k.startswith("_")}
        return str(v)
