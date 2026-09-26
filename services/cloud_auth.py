"""Supabase email auth and owner-scoped favorites REST client."""
from __future__ import annotations

import ctypes
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from services.storage import DATA_DIR


@dataclass(frozen=True)
class CloudConfig:
    url: str
    publishable_key: str

    def __post_init__(self):
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/"):
            raise ValueError("项目 URL 必须是 HTTPS 地址，且不能包含路径或账号信息")
        if not self.publishable_key or self.publishable_key.startswith("sb_secret_"):
            raise ValueError("只可使用 publishable / anon key，不可使用 secret / service_role key")

    @staticmethod
    def load() -> "CloudConfig | None":
        url = os.environ.get("TABLE_TENNIS_SUPABASE_URL", "")
        key = os.environ.get("TABLE_TENNIS_SUPABASE_KEY", "")
        if url and key:
            return CloudConfig(url.rstrip("/"), key)
        paths = [DATA_DIR / "cloud_config.json"]
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        paths.append(base / "assets" / "cloud_config.json")
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return CloudConfig(str(data["url"]).rstrip("/"), str(data["publishable_key"]))
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return None

    def save_local(self) -> None:
        path = DATA_DIR / "cloud_config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"url": self.url, "publishable_key": self.publishable_key},
                                   ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class CloudSession:
    user_id: str
    email: str
    access_token: str
    refresh_token: str
    expires_at: datetime


class CloudAPI:
    def __init__(self, config: CloudConfig):
        self.config = config

    def _request(self, method: str, path: str, *, token: str | None = None, **kwargs):
        headers = {"apikey": self.config.publishable_key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers.update(kwargs.pop("headers", {}))
        try:
            with httpx.Client(timeout=15) as client:
                response = client.request(method, self.config.url + path, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except httpx.HTTPStatusError as exc:
            try:
                message = exc.response.json().get("msg") or exc.response.json().get("message") or exc.response.json().get("error_description")
            except (ValueError, AttributeError):
                message = None
            raise RuntimeError(str(message or f"云端请求失败 ({exc.response.status_code})")) from None
        except httpx.RequestError as exc:
            raise RuntimeError(f"网络连接失败：{exc.__class__.__name__}") from None

    @staticmethod
    def _session(data: dict) -> CloudSession:
        user = data.get("user") or {}
        if not data.get("access_token") or not data.get("refresh_token") or not user.get("id"):
            raise RuntimeError("尚未建立登录会话；若刚注册，请先验证邮箱再登录")
        seconds = int(data.get("expires_in") or 3600)
        return CloudSession(str(user["id"]), str(user.get("email") or ""),
                            str(data["access_token"]), str(data["refresh_token"]),
                            datetime.now(timezone.utc) + timedelta(seconds=seconds))

    def sign_in(self, email: str, password: str) -> CloudSession:
        data = self._request("POST", "/auth/v1/token?grant_type=password",
                             json={"email": email, "password": password})
        return self._session(data)

    def sign_up(self, email: str, password: str) -> CloudSession | None:
        data = self._request("POST", "/auth/v1/signup", json={"email": email, "password": password})
        if data.get("access_token"):
            return self._session(data)
        return None

    def refresh(self, refresh_token: str) -> CloudSession:
        data = self._request("POST", "/auth/v1/token?grant_type=refresh_token",
                             json={"refresh_token": refresh_token})
        return self._session(data)

    def user(self, access_token: str) -> dict:
        return self._request("GET", "/auth/v1/user", token=access_token)

    def favorites(self, session: CloudSession) -> set[str]:
        values: set[str] = set()
        start = 0
        while True:
            rows = self._request("GET", "/rest/v1/user_favorites", token=session.access_token,
                                 params={"select": "match_id", "user_id": f"eq.{session.user_id}"},
                                 headers={"Range": f"{start}-{start + 999}"})
            if not isinstance(rows, list):
                raise RuntimeError("云端关注数据格式无效")
            values.update(row["match_id"] for row in rows if isinstance(row.get("match_id"), str))
            if len(rows) < 1000:
                return values
            start += 1000

    def push(self, session: CloudSession, operations: dict[str, bool]) -> None:
        adds = [{"user_id": session.user_id, "match_id": match_id}
                for match_id, enabled in operations.items() if enabled]
        if adds:
            self._request("POST", "/rest/v1/user_favorites?on_conflict=user_id,match_id",
                          token=session.access_token, json=adds,
                          headers={"Prefer": "resolution=merge-duplicates,return=minimal"})
        for match_id, enabled in operations.items():
            if not enabled:
                self._request("DELETE", "/rest/v1/user_favorites", token=session.access_token,
                              params={"user_id": f"eq.{session.user_id}",
                                      "match_id": f"eq.{match_id}"},
                              headers={"Prefer": "return=minimal"})


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, decrypt: bool) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("此版本仅在 Windows 上保存登录会话")
    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    in_blob = _DataBlob(len(data), source)
    out_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = ([ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
                          ctypes.POINTER(_DataBlob)] if decrypt else
                         [ctypes.POINTER(_DataBlob), ctypes.c_wchar_p, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
                          ctypes.POINTER(_DataBlob)])
    function.restype = ctypes.c_int
    ok = function(ctypes.byref(in_blob), None, None, None, None, 0,
                  ctypes.byref(out_blob))
    if not ok:
        raise OSError("Windows 无法解密或保存登录会话")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


class SessionStore:
    """Only a Windows-DPAPI encrypted refresh token is persisted; never a password."""
    def __init__(self):
        self.path = DATA_DIR / "cloud_session.json"

    def save(self, session: CloudSession) -> None:
        encrypted = _dpapi(session.refresh_token.encode("utf-8"), False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"user_id": session.user_id, "email": session.email,
                                   "refresh_token_dpapi": encrypted.hex()}), encoding="utf-8")
        tmp.replace(self.path)

    def load_refresh_token(self) -> str | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return _dpapi(bytes.fromhex(data["refresh_token_dpapi"]), True).decode("utf-8")
        except (OSError, KeyError, ValueError, UnicodeError):
            return None

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
