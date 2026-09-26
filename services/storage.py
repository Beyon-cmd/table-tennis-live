"""本地 JSON 存储：收藏 + 界面设置。不用 SQLite，保持简单。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import UUID


def _default_data_dir() -> Path:
    """打包成 exe 后没有固定项目目录，数据放到 %LOCALAPPDATA%。"""
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "TableTennisLive"
    return Path(__file__).resolve().parent.parent / "data"


DATA_DIR = _default_data_dir()


class JsonStore:
    def __init__(self, path: Path, default):
        self.path = Path(path)
        self._data = default
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, type(self._data)):
                    self._data = loaded
        except (OSError, json.JSONDecodeError):
            pass  # 文件损坏时使用默认值，不让程序崩溃

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)


class SettingsStore(JsonStore):
    def __init__(self):
        super().__init__(DATA_DIR / "settings.json", {"alerts": {}})

    def alert_enabled(self, kind: str) -> bool:
        alerts = self._data.get("alerts")
        return bool(alerts.get(kind)) if isinstance(alerts, dict) else False

    def set_alert(self, kind: str, enabled: bool) -> None:
        if kind not in {"start", "score", "final"}:
            raise ValueError("未知提醒类别")
        alerts = self._data.setdefault("alerts", {})
        if not isinstance(alerts, dict):
            alerts = self._data["alerts"] = {}
        alerts[kind] = bool(enabled)
        self.save()


class FavoritesStore(JsonStore):
    def __init__(self):
        super().__init__(DATA_DIR / "favorites.json", [])
        self.account_id: str | None = None
        self._pending_store: JsonStore | None = None

    def _ids(self) -> set[str]:
        return {value for value in self._data if isinstance(value, str)}

    def ids(self) -> set[str]:
        return self._ids()

    def activate_account(self, user_id: str | None) -> None:
        """Keep signed-out and per-account favorites in separate local files."""
        if user_id is None:
            self.account_id = None
            self.path = DATA_DIR / "favorites.json"
            self._pending_store = None
        else:
            safe_id = str(UUID(user_id))
            self.account_id = safe_id
            self.path = DATA_DIR / f"favorites-{safe_id}.json"
            first_login = not self.path.exists()
            anonymous_ids = JsonStore(DATA_DIR / "favorites.json", [])._data if first_login else []
            self._pending_store = JsonStore(DATA_DIR / f"favorites-pending-{safe_id}.json", {})
        self._data = []
        self.load()
        if user_id is not None and first_login:
            for match_id in anonymous_ids:
                if isinstance(match_id, str):
                    self._pending_store._data[match_id] = True
            self._data = sorted(self._ids() | {x for x in anonymous_ids if isinstance(x, str)})
            self.save()
            self._pending_store.save()

    def pending_operations(self) -> dict[str, bool]:
        if self._pending_store is None:
            return {}
        return {key: value for key, value in self._pending_store._data.items()
                if isinstance(key, str) and isinstance(value, bool)}

    def acknowledge(self, sent: dict[str, bool]) -> None:
        if self._pending_store is None:
            return
        for key, value in sent.items():
            if self._pending_store._data.get(key) == value:
                self._pending_store._data.pop(key, None)
        self._pending_store.save()

    def apply_remote(self, remote_ids: set[str]) -> None:
        if self.account_id is None:
            return
        ids = set(remote_ids)
        for key, enabled in self.pending_operations().items():
            if enabled:
                ids.add(key)
            else:
                ids.discard(key)
        self._data = sorted(ids)
        self.save()

    def contains(self, match_id: str) -> bool:
        return match_id in self._ids()

    def toggle(self, match_id: str) -> bool:
        ids = self._ids()
        if match_id in ids:
            ids.discard(match_id)
        else:
            ids.add(match_id)
        self._data = sorted(ids)
        self.save()
        if self._pending_store is not None:
            self._pending_store._data[match_id] = match_id in ids
            self._pending_store.save()
        return match_id in ids
