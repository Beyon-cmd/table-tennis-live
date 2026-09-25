"""数据源统一接口。

所有方法均为同步调用：刷新逻辑运行在普通后台线程中，
避免 asyncio 与 Qt 线程在打包环境下的退出清理冲突。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from models import Match

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}


def make_client() -> httpx.Client:
    """统一的 HTTP 客户端（跟随重定向，15 秒超时）。"""
    return httpx.Client(
        headers=HEADERS,
        timeout=15.0,
        follow_redirects=True,
    )


class DataSource(ABC):
    name: str = ""

    @abstractmethod
    def get_live_matches(self) -> list[Match]:
        """当前正在进行的比赛。"""

    @abstractmethod
    def get_schedule(self) -> list[Match]:
        """今日赛程：未开始 + 已结束。"""

    @abstractmethod
    def get_match_detail(self, match_id: str) -> Match | None:
        """比赛详情；查不到返回 None。"""

    def get_matches(self) -> list[Match]:
        """一次性返回该数据源的全部比赛。"""
        return self.get_live_matches() + self.get_schedule()
