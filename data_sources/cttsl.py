"""中国乒超数据源。

截至开发时，中国乒超联赛没有公开的官方数据接口（官网/APP 数据需要
登录或鉴权）。按照“不绕过访问控制、不编造数据”的原则，
本数据源返回空列表；界面会显示空状态，不展示伪造的比赛。
"""
from __future__ import annotations

from data_sources.base import DataSource
from models import Match


class CTTSLDataSource(DataSource):
    name = "CTTSL"

    def get_live_matches(self) -> list[Match]:
        return []

    def get_schedule(self) -> list[Match]:
        return []

    def get_match_detail(self, match_id: str) -> Match | None:
        return None
