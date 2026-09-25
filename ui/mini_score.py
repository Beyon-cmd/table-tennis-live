"""Compact always-on-top match view driven by the main window's live data."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from models import Match, STATUS_FINISHED, STATUS_LIVE
from services.storage import FavoritesStore


class MiniScoreWindow(QWidget):
    detail_requested = Signal(str)

    def __init__(self, favorites: FavoritesStore, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("迷你比分 · Table Tennis Live")
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setObjectName("MiniScoreWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(350)
        self._favorites = favorites
        self._matches: dict[str, Match] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 16)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("●  迷你比分")
        title.setObjectName("MiniTitle")
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("IconButton")
        self.close_button.clicked.connect(self.hide)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.close_button)
        layout.addLayout(header)
        self.selector = QComboBox()
        self.selector.setObjectName("MiniSelector")
        self.selector.currentIndexChanged.connect(self._render_selected)
        layout.addWidget(self.selector)
        self.competition = QLabel()
        self.competition.setObjectName("MiniMeta")
        self.competition.setWordWrap(True)
        layout.addWidget(self.competition)
        self.players = QLabel()
        self.players.setObjectName("MiniPlayers")
        self.players.setWordWrap(True)
        layout.addWidget(self.players)
        self.score = QLabel("—")
        self.score.setObjectName("MiniScore")
        self.score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.score)
        self.detail_button = QPushButton("查看比赛详情  ↗")
        self.detail_button.setObjectName("RankingButton")
        self.detail_button.clicked.connect(self._open_selected)
        layout.addWidget(self.detail_button)
        self.note = QLabel("比分随主程序刷新 · 关闭主程序后停止")
        self.note.setObjectName("MiniMeta")
        layout.addWidget(self.note)

    def set_matches(self, matches: list[Match]) -> None:
        selected = self.selector.currentData()
        candidates = [m for m in matches if m.status == STATUS_LIVE or self._favorites.contains(m.id)]
        candidates.sort(key=lambda m: (
            not self._favorites.contains(m.id), m.status != STATUS_LIVE,
            m.status == STATUS_FINISHED, m.start_time))
        self._matches = {m.id: m for m in candidates[:40]}
        self.selector.blockSignals(True)
        self.selector.clear()
        for match in self._matches.values():
            marker = "★ " if self._favorites.contains(match.id) else "● "
            self.selector.addItem(marker + match.player_a + " vs " + match.player_b, match.id)
        if selected in self._matches:
            self.selector.setCurrentIndex(self.selector.findData(selected))
        self.selector.blockSignals(False)
        self._render_selected()

    def _render_selected(self) -> None:
        match = self._matches.get(self.selector.currentData())
        self.detail_button.setEnabled(match is not None)
        if match is None:
            self.competition.setText("暂无直播或已收藏比赛")
            self.players.clear()
            self.score.setText("—")
            return
        self.competition.setText(match.competition)
        self.players.setText(f"{match.player_a}  vs  {match.player_b}")
        if match.status == STATUS_LIVE:
            state = "● LIVE"
        elif match.status == STATUS_FINISHED:
            state = "已结束"
        else:
            state = f"{match.start_time:%m-%d %H:%M} 开始"
        if match.data_stale:
            state = "⚠ 旧数据"
        score = f"{match.score_a} : {match.score_b}" if match.score_known and match.status != "upcoming" else "—"
        current = f"  ·  本局 {match.current_set[0]}:{match.current_set[1]}" if match.current_set else ""
        self.score.setText(f"{score}{current}\n{state}")

    def _open_selected(self) -> None:
        match_id = self.selector.currentData()
        if match_id in self._matches:
            self.detail_requested.emit(match_id)
