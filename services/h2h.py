"""Conservative head-to-head statistics from results already verified by the app.

This is deliberately a coverage-limited sample, not a claim about career records.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from data_sources.player_profiles import _name_key, clean_name
from models import Match, STATUS_FINISHED, STATUS_UPCOMING


@dataclass(frozen=True)
class H2HMeeting:
    match_id: str
    date: datetime
    competition: str
    winner: int  # 0 = left player in the upcoming match
    sets_a: int
    sets_b: int


@dataclass(frozen=True)
class H2HCompetition:
    name: str
    meetings: int
    wins_a: int
    wins_b: int
    sets_a: int
    sets_b: int


@dataclass(frozen=True)
class H2HReport:
    meetings: tuple[H2HMeeting, ...]
    competitions: tuple[H2HCompetition, ...]
    wins_a: int
    wins_b: int
    sets_a: int
    sets_b: int
    eligible: bool = True


def _individual(match: Match) -> bool:
    if match.has_games:
        return False
    names = (match.player_a, match.player_b, match.player_a_raw, match.player_b_raw)
    if any("/" in name for name in names):
        return False
    competition = match.competition.casefold()
    if any(term in competition for term in ("doubles", "双打", "团体", "team")):
        return False
    placeholders = {"", "待定", "轮空", "tbd", "bye", "—"}
    return all(clean_name(name).casefold() not in placeholders
               for name in (match.player_a, match.player_b))


def _same_player(target: Match, ti: int, old: Match, oi: int) -> bool:
    target_id = str(target.player_a_id if ti == 0 else target.player_b_id)
    old_id = str(old.player_a_id if oi == 0 else old.player_b_id)
    if target_id and old_id:
        return target_id == old_id
    target_name = target.player_a if ti == 0 else target.player_b
    old_name = old.player_a if oi == 0 else old.player_b
    target_raw = target.player_a_raw if ti == 0 else target.player_b_raw
    old_raw = old.player_a_raw if oi == 0 else old.player_b_raw
    target_names = (target_raw, target_name)
    old_names = (old_raw, old_name)
    target_keys = {key for name in target_names if name
                   for key in (clean_name(name).casefold(), _name_key(name)) if key}
    old_keys = {key for name in old_names if name
                for key in (clean_name(name).casefold(), _name_key(name)) if key}
    return bool(target_keys & old_keys)


def build_h2h(target: Match, results: list[Match]) -> H2HReport:
    """Count only completed, scored, individual results before this fixture."""
    if target.status != STATUS_UPCOMING or not _individual(target):
        return H2HReport((), (), 0, 0, 0, 0, False)
    found: list[H2HMeeting] = []
    seen: set[str] = set()
    for old in results:
        if (old.id == target.id or old.id in seen or old.status != STATUS_FINISHED
                or not old.score_known or not old.has_score or old.score_a == old.score_b
                or old.start_time >= target.start_time or not _individual(old)):
            continue
        direct = _same_player(target, 0, old, 0) and _same_player(target, 1, old, 1)
        reverse = _same_player(target, 0, old, 1) and _same_player(target, 1, old, 0)
        if direct == reverse:  # neither orientation, or ambiguous identity
            continue
        a, b = (old.score_a, old.score_b) if direct else (old.score_b, old.score_a)
        found.append(H2HMeeting(old.id, old.start_time, old.competition, 0 if a > b else 1, a, b))
        seen.add(old.id)
    found.sort(key=lambda row: (row.date, row.match_id), reverse=True)
    groups: dict[str, list[H2HMeeting]] = {}
    for row in found:
        event = row.competition.split(" · ", 1)[0].strip() or row.competition
        groups.setdefault(event, []).append(row)
    competitions = tuple(
        H2HCompetition(name, len(rows), sum(r.winner == 0 for r in rows),
                       sum(r.winner == 1 for r in rows), sum(r.sets_a for r in rows),
                       sum(r.sets_b for r in rows))
        for name, rows in groups.items()
    )
    return H2HReport(tuple(found), competitions, sum(r.winner == 0 for r in found),
                     sum(r.winner == 1 for r in found), sum(r.sets_a for r in found),
                     sum(r.sets_b for r in found))
