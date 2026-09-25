"""内存中的得分趋势。只保存实际观察到的局分或官方事件，不补造逐分过程。"""
from __future__ import annotations

from dataclasses import dataclass, field

from models import Match, STATUS_UPCOMING


@dataclass(frozen=True)
class TrendPoint:
    set_number: int
    score_a: int
    score_b: int
    final: bool = False
    official_events: tuple[str, ...] = ()
    streak_player: int | None = None
    streak_count: int = 0
    game_point_player: int | None = None
    match_point_player: int | None = None

    @property
    def progress(self) -> int:
        return self.score_a + self.score_b

    @property
    def difference(self) -> int:
        return self.score_a - self.score_b


@dataclass
class _Observation:
    score_a: int
    score_b: int
    final: bool = False
    events: set[str] = field(default_factory=set)


class ScoreTrendStore:
    def __init__(self, max_matches: int = 128, max_points_per_set: int = 250):
        self._series: dict[str, dict[int, dict[int, _Observation]]] = {}
        self._max_matches = max_matches
        self._max_points_per_set = max_points_per_set

    def observe(self, match: Match) -> None:
        if match.status == STATUS_UPCOMING or match.data_stale or match.has_games:
            return
        if not match.sets and match.current_set is None and not match.score_events:
            return
        if match.id not in self._series and len(self._series) >= self._max_matches:
            self._series.pop(next(iter(self._series)))
        sets = self._series.setdefault(match.id, {})

        # 官网如果补发逐分事件，可按该局累计得分插入到先前的轮询样本之间。
        for event in match.score_events:
            if event.set_number < 1 or event.score_a < 0 or event.score_b < 0:
                continue
            point = self._put(sets, event.set_number, event.score_a, event.score_b)
            if point is not None and event.kind in {"point", "timeout", "match_point"}:
                point.events.add(event.kind)

        for number, (a, b) in enumerate(match.sets, 1):
            if a == b == 0:
                continue
            point = self._put(sets, number, a, b)
            if point is not None:
                point.final = True
        if match.current_set is not None:
            a, b = match.current_set
            if a >= 0 and b >= 0:
                self._put(sets, len(match.sets) + 1, a, b)

    def _put(self, sets: dict[int, dict[int, _Observation]], number: int,
             a: int, b: int) -> _Observation | None:
        points = sets.setdefault(number, {})
        progress = a + b
        old = points.get(progress)
        if old is not None and (old.score_a, old.score_b) != (a, b):
            # 官方修正同一得分节点时，不保留矛盾的轨迹。
            points.clear()
        if progress not in points and len(points) >= self._max_points_per_set:
            return None
        return points.setdefault(progress, _Observation(a, b))

    def points(self, match: Match) -> list[TrendPoint]:
        result: list[TrendPoint] = []
        for number, observations in sorted(self._series.get(match.id, {}).items()):
            previous: _Observation | None = None
            streak_player: int | None = None
            streak_count = 0
            for progress, sample in sorted(observations.items()):
                actor = None
                if previous is not None and progress == previous.score_a + previous.score_b + 1:
                    if sample.score_a == previous.score_a + 1 and sample.score_b == previous.score_b:
                        actor = 0
                    elif sample.score_b == previous.score_b + 1 and sample.score_a == previous.score_a:
                        actor = 1
                if actor is None:
                    streak_player, streak_count = None, 0
                else:
                    streak_count = streak_count + 1 if streak_player == actor else 1
                    streak_player = actor
                game_point = None if sample.final else _game_point_player(sample.score_a, sample.score_b)
                match_point = None
                if (game_point is not None and match.winning_sets is not None
                        and match.winning_sets > 0):
                    won_a = sum(a > b for a, b in match.sets[:number - 1])
                    won_b = sum(b > a for a, b in match.sets[:number - 1])
                    if (won_a, won_b)[game_point] == match.winning_sets - 1:
                        match_point = game_point
                result.append(TrendPoint(
                    number, sample.score_a, sample.score_b, sample.final,
                    tuple(sorted(sample.events)), streak_player if streak_count >= 3 else None,
                    streak_count if streak_count >= 3 else 0,
                    game_point, match_point,
                ))
                previous = sample
        return result


def _game_point_player(a: int, b: int) -> int | None:
    # 每局先到 11 分且领先至少 2 分；已结束的 11:9 不算待打的局点。
    if max(a, b) >= 11 and abs(a - b) >= 2:
        return None
    if a >= 10 and a > b:
        return 0
    if b >= 10 and b > a:
        return 1
    return None
