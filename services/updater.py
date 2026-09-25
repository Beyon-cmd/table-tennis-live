"""后台刷新服务。

在普通后台线程（threading.Thread）中定时抓取数据；
比较新旧数据，只把“发生变化”的比赛通过 Qt 信号发给主线程 UI。
网络请求全部在后台线程完成，不阻塞 UI。
"""
from __future__ import annotations

import threading
import time
from dataclasses import replace
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal

from models import Match, STATUS_LIVE, STATUS_UPCOMING


class _UpdaterWorker(QObject):
    changed = Signal(list)  # 新增 / 内容变化的 Match
    removed = Signal(list)  # 消失的比赛 id
    detail_ready = Signal(object)
    error = Signal(str)
    source_status = Signal(str, object, str)  # 来源、最近成功取数时间、错误

    def __init__(
        self,
        sources,
        live_interval: float = 2.0,
        schedule_interval: float = 10.0,
        other_interval: float = 15.0,
    ):
        super().__init__()
        self._sources = sources
        self._live_interval = live_interval
        self._schedule_interval = schedule_interval
        self._other_interval = other_interval
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot: dict[str, Match] = {}
        self._pending_detail: list[str] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="data-updater", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def request_refresh(self) -> None:
        self._wake_event.set()

    def request_detail(self, match_id: str) -> None:
        with self._lock:
            if match_id not in self._pending_detail:
                self._pending_detail.append(match_id)
        self._wake_event.set()

    def _run(self) -> None:
        # 每个数据源独立调度；完成一个就推送一个，不等慢源。
        pool = ThreadPoolExecutor(max_workers=max(1, len(self._sources)))
        pending = {}
        due = {src: 0.0 for src in self._sources}
        snapshots = {src: [] for src in self._sources}
        backoffs = {src: 1.0 for src in self._sources}
        last_success = {src: None for src in self._sources}
        try:
            while not self._stop_event.is_set():
                if self._wake_event.is_set():
                    self._wake_event.clear()
                    due = {src: 0.0 for src in self._sources}
                for src, future in list(pending.items()):
                    if not future.done():
                        continue
                    del pending[src]
                    try:
                        matches = future.result()
                        snapshots[src] = matches
                        has_stale = any(m.data_stale for m in matches)
                        if not has_stale:
                            last_success[src] = datetime.now()
                        self._apply_snapshot([m for rows in snapshots.values() for m in rows])
                        self.source_status.emit(src.name, last_success[src],
                                                "部分结果沿用缓存" if has_stale else "")
                        statuses = {m.status for m in matches}
                        interval = (self._live_interval if STATUS_LIVE in statuses else
                                    self._schedule_interval if STATUS_UPCOMING in statuses else self._other_interval)
                        backoffs[src] = 1.0
                    except Exception as exc:
                        # 暂时失败时保留该源上一次成功的比分。
                        snapshots[src] = [replace(m, data_stale=True) for m in snapshots[src]]
                        self._apply_snapshot([m for rows in snapshots.values() for m in rows])
                        self.source_status.emit(src.name, last_success[src], str(exc))
                        self.error.emit(f"{src.name} 数据获取失败：{exc}")
                        interval = backoffs[src]
                        backoffs[src] = min(interval * 2, 30.0)
                    due[src] = time.monotonic() + interval
                for src in self._sources:
                    if src not in pending and time.monotonic() >= due[src]:
                        pending[src] = pool.submit(self._fetch_source, src)
                self._stop_event.wait(0.1)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _fetch_source(self, src):
        matches = src.get_matches()
        # 同一个源内串行处理详情，避免缓存并发覆盖；不阻塞其它源刷新。
        ids = {m.id for m in matches}
        with self._lock:
            requested = [mid for mid in self._pending_detail if mid in ids]
            self._pending_detail = [mid for mid in self._pending_detail if mid not in ids]
        for mid in requested:
            detail = src.get_match_detail(mid)
            if detail is not None:
                self.detail_ready.emit(detail)
        return matches

    def _drain_details(self) -> None:
        """后台线程按需处理详情请求，避免阻塞 UI 线程。"""
        with self._lock:
            if not self._pending_detail:
                return
            match_id = self._pending_detail.pop(0)
        for src in self._sources:
            try:
                detail = src.get_match_detail(match_id)
            except Exception:
                continue
            if detail is not None:
                self.detail_ready.emit(detail)
                return

    def _sleep(self, seconds: float) -> None:
        self._wake_event.wait(timeout=seconds)
        self._wake_event.clear()

    def _apply_snapshot(self, matches: list[Match]) -> None:
        new_snapshot = {m.id: m for m in matches}
        changed = [
            m
            for mid, m in new_snapshot.items()
            if mid not in self._snapshot
            or self._snapshot[mid].content_key() != m.content_key()
        ]
        removed = [mid for mid in self._snapshot if mid not in new_snapshot]
        self._snapshot = new_snapshot
        if changed:
            self.changed.emit(changed)
        if removed:
            self.removed.emit(removed)


class Updater(QObject):
    """主线程可见的刷新服务壳，内部把工作放到后台线程。"""

    changed = Signal(list)
    removed = Signal(list)
    detail_ready = Signal(object)
    error = Signal(str)
    source_status = Signal(str, object, str)

    def __init__(self, sources, **kwargs):
        super().__init__()
        self._worker = _UpdaterWorker(sources, **kwargs)
        self._worker.changed.connect(self.changed)
        self._worker.removed.connect(self.removed)
        self._worker.detail_ready.connect(self.detail_ready)
        self._worker.error.connect(self.error)
        self._worker.source_status.connect(self.source_status)

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._worker.stop()

    def request_refresh(self) -> None:
        self._worker.request_refresh()

    def request_detail(self, match_id: str) -> None:
        self._worker.request_detail(match_id)
