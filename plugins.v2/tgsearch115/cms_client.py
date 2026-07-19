# -*- coding: utf-8 -*-
"""Client for Cloud Media Sync's token-authenticated 115 offline API."""
from typing import Callable, Optional, Tuple


class Cms115Client:
    """Submit magnet links to a user-managed CMS instance without exposing its token."""

    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        timeout: int = 20,
        client_factory: Optional[Callable] = None,
    ):
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.token = str(token or "").strip()
        self.timeout = max(3, int(timeout or 20))
        self._client_factory = client_factory

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _client(self):
        if self._client_factory:
            return self._client_factory(timeout=self.timeout, trust_env=False)
        import httpx
        return httpx.Client(timeout=self.timeout, trust_env=False)

    def check(self) -> Tuple[bool, str]:
        if not self.base_url:
            return False, "未配置 CMS 地址"
        if not self.token:
            return False, "未配置 CMS API Token"
        try:
            with self._client() as client:
                response = client.get(self.base_url)
            if response.status_code != 200:
                return False, f"CMS 服务返回 HTTP {response.status_code}"
            return True, "CMS 服务可访问，Token 将在提交磁力任务时使用"
        except Exception as exc:
            return False, f"CMS 服务连接失败: {exc}"

    def add_magnet(self, magnet: str) -> Tuple[bool, str]:
        magnet = str(magnet or "").strip()
        if not magnet.lower().startswith("magnet:?"):
            return False, "磁力链接无效"
        if not self.configured:
            return False, "CMS 地址或 API Token 未配置"

        endpoint = f"{self.base_url}/api/cloud/add_share_down_by_token"
        try:
            with self._client() as client:
                response = client.post(endpoint, json={"url": magnet, "token": self.token})
            if response.status_code < 200 or response.status_code >= 300:
                return False, f"CMS 返回 HTTP {response.status_code}"
            try:
                payload = response.json()
            except Exception:
                return False, "CMS 返回了无法解析的响应"
            if not isinstance(payload, dict):
                return False, "CMS 返回格式无效"
            code = payload.get("code")
            message = str(payload.get("msg") or payload.get("message") or "").strip()
            if str(code or "").strip() != "200":
                return False, message or f"CMS 返回业务状态 {code}"
            return True, message or "已创建 115 磁力离线任务"
        except Exception as exc:
            return False, f"CMS 磁力任务提交失败: {exc}"
