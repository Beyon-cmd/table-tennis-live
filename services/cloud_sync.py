"""Non-blocking account session and offline-safe favorite synchronization."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QObject, QTimer, Signal

from services.cloud_auth import CloudAPI, CloudConfig, CloudSession, SessionStore
from services.storage import FavoritesStore


class CloudSyncManager(QObject):
    state_changed = Signal(str)
    favorites_changed = Signal()
    auth_finished = Signal(bool, str)

    def __init__(self, favorites: FavoritesStore, parent=None):
        super().__init__(parent)
        self.favorites = favorites
        self.config = CloudConfig.load()
        self.api = CloudAPI(self.config) if self.config else None
        self.session: CloudSession | None = None
        self._store = SessionStore()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cloud-sync")
        self._future: Future | None = None
        self._operation = ""
        self._sent: dict[str, bool] = {}
        self._sync_requested = False
        self._poll = QTimer(self)
        self._poll.setInterval(100)
        self._poll.timeout.connect(self._collect)
        self._periodic = QTimer(self)
        self._periodic.setInterval(30_000)
        self._periodic.timeout.connect(self.sync)
        self._periodic.start()

    @property
    def email(self) -> str:
        return self.session.email if self.session else ""

    def configure(self, url: str, publishable_key: str) -> None:
        config = CloudConfig(url.strip().rstrip("/"), publishable_key.strip())
        config.save_local()
        self.config = config
        self.api = CloudAPI(config)
        self.state_changed.emit("云端已配置 · 请登录")

    def restore(self) -> None:
        if not self.api or self._future is not None:
            return
        token = self._store.load_refresh_token()
        if token:
            self._submit("restore", self.api.refresh, token)

    def sign_in(self, email: str, password: str) -> None:
        self._authenticate("login", email, password)

    def sign_up(self, email: str, password: str) -> None:
        self._authenticate("signup", email, password)

    def _authenticate(self, operation: str, email: str, password: str) -> None:
        if not self.api:
            self.auth_finished.emit(False, "请先配置 Supabase 项目")
        elif self._future is not None:
            self.auth_finished.emit(False, "正在连接云端，请稍候")
        elif not email.strip() or not password:
            self.auth_finished.emit(False, "请输入邮箱和密码")
        else:
            method = self.api.sign_in if operation == "login" else self.api.sign_up
            self._submit(operation, method, email.strip(), password)

    def _submit(self, operation: str, fn, *args) -> None:
        self._operation = operation
        self._future = self._executor.submit(fn, *args)
        self._poll.start()
        self.state_changed.emit("正在连接云端…")

    def _collect(self) -> None:
        if self._future is None or not self._future.done():
            return
        future, operation = self._future, self._operation
        self._future = None
        self._operation = ""
        self._poll.stop()
        try:
            result = future.result()
        except Exception as exc:
            message = str(exc)
            self.state_changed.emit(f"同步失败 · {message}" if operation == "sync" else message)
            if operation in ("login", "signup"):
                self.auth_finished.emit(False, message)
            return
        if operation in ("login", "signup", "restore"):
            if result is None:
                self.state_changed.emit("注册邮件已发送，请验证邮箱后登录")
                self.auth_finished.emit(True, "注册邮件已发送，请验证邮箱后登录")
                return
            self.session = result
            self._store.save(result)
            self.favorites.activate_account(result.user_id)
            self.favorites_changed.emit()
            self.state_changed.emit(f"已登录 · {result.email} · 正在同步")
            if operation != "restore":
                self.auth_finished.emit(True, "登录成功，正在同步关注")
            self.sync()
        elif operation == "sync":
            session, remote_ids = result
            self.session = session
            self._store.save(session)
            self.favorites.acknowledge(self._sent)
            self.favorites.apply_remote(remote_ids)
            self.favorites_changed.emit()
            self.state_changed.emit(f"已同步 · {session.email}")
            if self._sync_requested or self.favorites.pending_operations():
                self._sync_requested = False
                self.sync()

    def sync(self) -> None:
        if not self.session or not self.api:
            return
        if self._future is not None:
            self._sync_requested = True
            return
        self._sent = self.favorites.pending_operations()
        self._submit("sync", self._sync_worker, self.api, self.session, self._sent)

    @staticmethod
    def _sync_worker(api: CloudAPI, session: CloudSession,
                     operations: dict[str, bool]) -> tuple[CloudSession, set[str]]:
        if session.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=2):
            session = api.refresh(session.refresh_token)
        api.push(session, operations)
        return session, api.favorites(session)

    def favorite_changed(self) -> None:
        self.sync()

    def logout(self) -> None:
        if self._future is not None:
            self._future.cancel()
            self._future = None
            self._poll.stop()
        self.session = None
        self._store.clear()
        self.favorites.activate_account(None)
        self.favorites_changed.emit()
        self.state_changed.emit("未登录 · 关注仅保存在此电脑")

    def shutdown(self) -> None:
        self._periodic.stop()
        self._poll.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
