"""本地 JSON 存储：收藏 + 界面设置。不用 SQLite，保持简单。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


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
        super().__init__(DATA_DIR / "settings.json", {"theme": "system"})

    @property
    def theme(self) -> str:
        return self._data.get("theme", "system")

    def set_theme(self, mode: str) -> None:
        self._data["theme"] = mode
        self.save()


class FavoritesStore(JsonStore):
    def __init__(self):
        super().__init__(DATA_DIR / "favorites.json", [])

    def _ids(self) -> set[str]:
        return set(self._data if isinstance(self._data, list) else [])

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
        return match_id in ids
