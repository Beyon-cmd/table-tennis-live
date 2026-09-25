"""Opt-in, in-process alerts for followed matches only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from models import Match, STATUS_FINISHED, STATUS_LIVE, STATUS_UPCOMING


@dataclass(frozen=True)
class MatchAlert:
    match_id: str
    kind: str
    title: str
    message: str


class MatchAlertTracker:
    def __init__(self):
        self._previous: dict[str, Match] = {}
        self._start_sent: set[str] = set()
        self._final_sent: set[str] = set()

    def update(self, match: Match, favorite: bool, enabled: dict[str, bool]) -> list[MatchAlert]:
        if not favorite:
            self._previous.pop(match.id, None)
            return []
        if match.data_stale:
            return []
        old = self._previous.get(match.id)
        self._previous[match.id] = match
        if old is None:
            return []
        label = f"{match.player_a} vs {match.player_b}"
        events: list[MatchAlert] = []
        if old.status == STATUS_UPCOMING and match.status == STATUS_LIVE:
            already_sent = match.id in self._start_sent
            self._start_sent.add(match.id)
            if enabled.get("start") and not already_sent:
                events.append(MatchAlert(match.id, "start", "关注的比赛已开始", label))
        elif match.status == STATUS_LIVE and old.status == STATUS_LIVE:
            if (enabled.get("score") and match.score_known and old.score_known
                    and (match.score_a, match.score_b) != (old.score_a, old.score_b)):
                events.append(MatchAlert(match.id, "score", "关注的比赛大比分变化",
                                         f"{label}  {match.score_a}:{match.score_b}"))
        if old.status != STATUS_FINISHED and match.status == STATUS_FINISHED:
            if match.id not in self._final_sent and enabled.get("final"):
                score = f"  {match.score_a}:{match.score_b}" if match.score_known else ""
                events.append(MatchAlert(match.id, "final", "关注的比赛已结束", label + score))
            self._final_sent.add(match.id)
        return events

    def due(self, match: Match, now: datetime, enabled: dict[str, bool]) -> MatchAlert | None:
        if (not enabled.get("start") or match.data_stale or match.status != STATUS_UPCOMING
                or match.id in self._start_sent):
            return None
        remaining = (match.start_time - now).total_seconds()
        if not 0 <= remaining <= 300:
            return None
        self._start_sent.add(match.id)
        return MatchAlert(match.id, "start", "关注的比赛即将开始",
                          f"{match.player_a} vs {match.player_b} · {match.start_time:%H:%M}")

    def forget(self, match_id: str) -> None:
        self._previous.pop(match_id, None)
        self._start_sent.discard(match_id)
        self._final_sent.discard(match_id)
