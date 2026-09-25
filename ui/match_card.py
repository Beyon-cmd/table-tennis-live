"""比赛卡片：信息流里的每一张卡。"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton

from models import Match, STATUS_FINISHED, STATUS_LIVE, STATUS_UPCOMING
from services.storage import FavoritesStore
from ui.score_strip import ScoreStrip
from ui.flags import player_html
from ui.player_link import PlayerLink
from data_sources.player_profiles import request_from_match
from ui.widgets import (
    ClickableFrame,
    apply_card_shadow,
    countdown_text,
    match_time_text,
    relative_update_text,
    set_star_state,
)


class MatchCard(ClickableFrame):
    favorite_toggled = Signal(str, bool)  # (match_id, is_favorite)
    player_clicked = Signal(object)

    def __init__(self, match: Match, favorites: FavoritesStore, parent=None):
        super().__init__(match.id, parent)
        self._match: Match | None = None
        self._content_key = None
        self._updated_at: datetime | None = None
        self._favorites = favorites
        self.setMinimumHeight(116)

        self.competition = QLabel()
        self.competition.setObjectName("Competition")
        self.competition.setWordWrap(True)
        self.star = QPushButton()
        self.star.setObjectName("StarButton")
        self.star.setFixedSize(30, 26)
        self.star.setCursor(Qt.CursorShape.PointingHandCursor)
        self.badge = QLabel()
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.player_a = PlayerLink()
        self.player_a.setWordWrap(True)
        self.center = QLabel()
        self.center.setObjectName("MatchScore")
        self.center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label = QLabel()
        self.time_label.setObjectName("MatchTime")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.player_b = PlayerLink()
        self.player_b.setWordWrap(True)
        self.player_b.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.sets_a = QLabel(self)
        self.sets_a.setObjectName("SetScore")
        self.set_center = QLabel(self)
        self.set_center.setObjectName("AccentText")
        self.set_center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sets_b = QLabel(self)
        self.sets_b.setObjectName("SetScore")
        self.sets_b.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.meta = QLabel()
        self.meta.setObjectName("Meta")

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.competition, 1)
        top.addWidget(self.star)
        top.addWidget(self.badge)

        grid = QGridLayout(self)
        grid.setContentsMargins(16, 10, 16, 10)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)
        grid.addLayout(top, 0, 0, 1, 3)
        grid.addWidget(
            self.player_a, 1, 0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        grid.addWidget(self.center, 1, 1)
        grid.addWidget(self.time_label, 1, 1)
        grid.addWidget(
            self.player_b, 1, 2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.score_strip = ScoreStrip()
        grid.addWidget(self.score_strip, 2, 0, 1, 3)
        grid.addWidget(self.meta, 3, 0, 1, 3, Qt.AlignmentFlag.AlignLeft)

        self.star.clicked.connect(self._on_star_clicked)
        self.player_a.clicked.connect(lambda: self.player_clicked.emit(request_from_match(self._match, 0)))
        self.player_b.clicked.connect(lambda: self.player_clicked.emit(request_from_match(self._match, 1)))
        self.set_match(match, datetime.now())
        apply_card_shadow(self)

    # ---------- 数据 ----------
    def set_match(self, match: Match, now: datetime) -> None:
        key = match.content_key()
        if key == self._content_key:
            return  # 内容没变，不重绘
        self._match = match
        self._content_key = key
        self._updated_at = now

        set_star_state(self.star, self._favorites.contains(match.id))
        self.competition.setText(match.competition)
        self.player_a.setText(player_html(match.player_a))
        self.player_b.setText(player_html(match.player_b))
        self.player_a.setEnabled(not match.has_games)
        self.player_b.setEnabled(not match.has_games)

        if match.status == STATUS_LIVE:
            self.badge.setObjectName("BadgeLive")
            self.badge.setText("● LIVE")
            self.center.setText(
                f"{match.score_a} : {match.score_b}" if match.score_known else "—"
            )
            self.center.show()
            self.time_label.hide()
            completed = match.sets
            self.sets_a.setText("  ".join(str(a) for a, _ in completed))
            self.sets_b.setText("  ".join(str(b) for _, b in completed))
            self.sets_a.setVisible(bool(completed))
            self.sets_b.setVisible(bool(completed))
            if match.current_set:
                self.set_center.setText(f"本局 {match.current_set[0]} : {match.current_set[1]}")
                self.set_center.setVisible(True)
            else:
                self.set_center.clear()
                self.set_center.setVisible(False)
            self.meta.setText(relative_update_text(self._updated_at, now))
        elif match.status == STATUS_UPCOMING:
            self.badge.clear()
            self.center.hide()
            self.time_label.setText(match_time_text(match))
            self.time_label.show()
            self.sets_a.clear()
            self.sets_b.clear()
            self.sets_a.setVisible(False)
            self.sets_b.setVisible(False)
            self.set_center.clear()
            self.set_center.setVisible(False)
            self.meta.setText(countdown_text(match, now))
        else:  # STATUS_FINISHED
            self.badge.setObjectName("BadgeFinal")
            self.badge.setText("已结束")
            self.center.setText(
                f"{match.score_a} : {match.score_b}" if match.has_score else "—"
            )
            self.center.show()
            self.time_label.hide()
            self.sets_a.setText("  ".join(str(a) for a, _ in match.sets))
            self.sets_b.setText("  ".join(str(b) for _, b in match.sets))
            self.sets_a.setVisible(bool(match.sets))
            self.sets_b.setVisible(bool(match.sets))
            self.set_center.clear()
            self.set_center.setVisible(False)
            self.meta.setText("已结束")

        if match.data_stale:
            self.badge.setObjectName("BadgeStale")
            self.badge.setText("⚠ 旧数据")
            self.meta.setText("比分未重新核对 · 数据源正在重试")
        elif match.score_reconciled:
            self.meta.setText(self.meta.text() + " · 总比分按已结束局分校正")

        self._repolish_badge()
        # 上下两行对应左、右选手，避免把双方小分分散在卡片两端。
        for old_label in (self.sets_a, self.sets_b, self.set_center):
            old_label.hide()
        self.score_strip.set_scores(match.sets, match.current_set if match.status == STATUS_LIVE else None)
        if match.has_games:
            self.meta.setText(self.meta.text() + f" · {len(match.games)} 场对阵 · 点击查看详情")
        elif match.status == STATUS_FINISHED and not match.has_score:
            self.meta.setText("已结束 · 官方比分暂未取得")

    def refresh_time(self, now: datetime) -> None:
        """每秒刷新“Updated Xs ago / 倒计时”，只有文字变化才重设。"""
        if not self._match:
            return
        if self._match.data_stale:
            return
        if self._match.status == STATUS_LIVE:
            text = relative_update_text(self._updated_at, now)
        elif self._match.status == STATUS_UPCOMING:
            text = countdown_text(self._match, now)
        else:
            return
        if self._match.has_games:
            text += f" · {len(self._match.games)} 场对阵 · 点击查看详情"
        if self._match.score_reconciled:
            text += " · 总比分按已结束局分校正"
        if self.meta.text() != text:
            self.meta.setText(text)

    # ---------- 收藏 ----------
    def _on_star_clicked(self) -> None:
        favorite = self._favorites.toggle(self._match.id)
        set_star_state(self.star, favorite)
        self.favorite_toggled.emit(self._match.id, favorite)

    def _repolish_badge(self) -> None:
        style = self.badge.style()
        style.unpolish(self.badge)
        style.polish(self.badge)
