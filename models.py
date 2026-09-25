"""数据模型：第一版只需要一个 Match，不做复杂建模。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

STATUS_LIVE = "live"
STATUS_UPCOMING = "upcoming"
STATUS_FINISHED = "finished"

# 赛事在信息流中的展示顺序（大赛置顶）
SOURCE_ORDER = ["majors", "WTT", "T.League", "TTBL", "CTTSL"]

SOURCE_NAMES = {
    "majors": "大赛",
    "WTT": "WTT",
    "T.League": "日本 T.League",
    "TTBL": "德国 TTBL",
    "CTTSL": "中国乒超",
}


@dataclass
class Game:
    """队伍制比赛里的单场对阵（含每局比分）。"""

    player_a: str
    player_b: str
    score_a: int = 0
    score_b: int = 0
    sets: list[tuple[int, int]] = field(default_factory=list)


@dataclass(frozen=True)
class ScoreEvent:
    """仅记录官方数据明确给出的逐分/暂停事件，不由比分反推。"""

    set_number: int
    score_a: int
    score_b: int
    kind: str  # point / timeout / match_point
    player: int | None = None  # 0 左侧、1 右侧


@dataclass
class Match:
    id: str
    source: str
    competition: str
    status: str
    start_time: datetime
    player_a: str
    player_b: str
    player_a_raw: str = ""  # 官方原文名（中文名来自对照表时保留，用于搜索/对照）
    player_b_raw: str = ""
    score_a: int = 0
    score_b: int = 0
    sets: list[tuple[int, int]] = field(default_factory=list)  # 已结束的局
    current_set: tuple[int, int] | None = None  # 正在进行的局（仅 LIVE）
    last_update: datetime = field(default_factory=datetime.now)
    score_known: bool = True  # 数据源没有比分时显示 “—”，不编造
    games: list[Game] = field(default_factory=list)  # 队伍制比赛的单场对阵
    player_a_id: str = ""  # 官网确认的个人选手 ID；团体/双打组合不猜测
    player_b_id: str = ""
    data_stale: bool = False  # 沿用旧数据，不能当作已核对的实时比分
    major_category: str = ""  # 当期三大赛的明确分类；历史条目不参与自动切换
    score_events: list[ScoreEvent] = field(default_factory=list)
    winning_sets: int | None = None  # 只有官方赛制明确时才用于赛点标记
    score_reconciled: bool = False  # 官网大比分滞后时按已结束逐局分校正

    @property
    def source_name(self) -> str:
        return SOURCE_NAMES.get(self.source, self.source)

    @property
    def has_score(self) -> bool:
        return bool(self.sets) or self.score_a > 0 or self.score_b > 0

    @property
    def has_games(self) -> bool:
        return bool(self.games)

    def content_key(self) -> tuple:
        """内容指纹：内容没变就不重绘 UI。"""
        return (
            self.id,
            self.status,
            self.score_a,
            self.score_b,
            tuple(self.sets),
            self.current_set,
            self.player_a,
            self.player_b,
            self.competition,
            self.start_time.timestamp(),
            self.score_known,
            tuple((g.player_a, g.player_b, g.score_a, g.score_b, tuple(g.sets)) for g in self.games),
            self.player_a_raw,
            self.player_b_raw,
            self.player_a_id,
            self.player_b_id,
            self.data_stale,
            self.major_category,
            tuple(self.score_events),
            self.winning_sets,
            self.score_reconciled,
        )

    def search_text(self) -> str:
        parts = [
            self.player_a,
            self.player_b,
            self.player_a_raw,
            self.player_b_raw,
            self.competition,
            self.source,
            self.source_name,
        ]
        for game in self.games:
            parts.extend([game.player_a, game.player_b])
        return " ".join(parts).lower()
