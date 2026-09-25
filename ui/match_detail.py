"""比赛详情页：大比分 + 逐局比分。"""
from __future__ import annotations
from ui.flags import player_html
from ui.player_link import PlayerLink
from data_sources.player_profiles import PlayerRequest, request_from_match
from ui.motion import SmoothScrollArea
from ui.score_trend import ScoreTrendWidget
from services.score_trend import TrendPoint

from datetime import datetime
from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models import Match, STATUS_FINISHED, STATUS_LIVE, STATUS_UPCOMING
from services.storage import FavoritesStore
from services.h2h import H2HReport
from ui.score_strip import ScoreStrip
from ui.widgets import (
    countdown_text,
    match_time_text,
    relative_update_text,
    set_star_state,
)


class MatchDetailPage(QWidget):
    back_requested = Signal()
    favorite_toggled = Signal(str, bool)
    player_clicked = Signal(object)

    def __init__(self, favorites: FavoritesStore, parent=None):
        super().__init__(parent)
        self._favorites = favorites
        self._match: Match | None = None
        self._content_key = None
        self._updated_at: datetime | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 14, 28, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.back = QPushButton("← 返回")
        self.back.setObjectName("BackButton")
        self.competition = QLabel()
        self.competition.setObjectName("Competition")
        self.competition.setWordWrap(True)
        self.star = QPushButton()
        self.star.setObjectName("StarButton")
        self.star.setCursor(Qt.CursorShape.PointingHandCursor)
        self.badge = QLabel()
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.back)
        header.addWidget(self.competition, 1)
        header.addWidget(self.star)
        header.addWidget(self.badge)
        root.addLayout(header)

        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container.setObjectName("DetailContainer")
        v = QVBoxLayout(container)
        v.addStretch(1)
        h = QHBoxLayout()
        h.addStretch(0)
        self.card = QFrame()
        self.card.setObjectName("Card")
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.card.setMaximumWidth(820)
        h.addWidget(self.card, 1)
        h.addStretch(0)
        v.addLayout(h)
        v.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(12)
        players = QHBoxLayout()
        players.setSpacing(20)
        self.player_a = PlayerLink()
        self.player_a.setWordWrap(True)
        self.player_a_raw = QLabel()
        self.player_a_raw.setObjectName("Meta")
        self.score = QLabel()
        self.score.setObjectName("MatchScore")
        self.score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.player_b = PlayerLink()
        self.player_b.setWordWrap(True)
        self.player_b.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.player_b_raw = QLabel()
        self.player_b_raw.setObjectName("Meta")
        home_box = QVBoxLayout()
        home_box.setSpacing(0)
        home_box.addWidget(self.player_a)
        home_box.addWidget(self.player_a_raw)
        away_box = QVBoxLayout()
        away_box.setSpacing(0)
        away_box.addWidget(self.player_b)
        away_box.addWidget(self.player_b_raw)
        players.addLayout(home_box)
        players.addWidget(self.score, 1)
        players.addLayout(away_box)
        card_layout.addLayout(players)

        self.sets_text = QLabel()
        self.sets_text.setObjectName("DetailSet")
        self.sets_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.sets_text)
        self.score_strip = ScoreStrip()
        card_layout.addWidget(self.score_strip)
        self.games_container = QWidget()
        self.games_container.setVisible(False)
        self.games_box = QVBoxLayout(self.games_container)
        self.games_box.setSpacing(8)
        card_layout.addWidget(self.games_container)
        self.current_label = QLabel()
        self.current_label.setObjectName("AccentText")
        self.current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.current_label)
        self.h2h_container = QFrame()
        self.h2h_container.setObjectName("H2HPanel")
        self.h2h_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.h2h_box = QVBoxLayout(self.h2h_container)
        self.h2h_box.setContentsMargins(18, 18, 18, 18)
        self.h2h_box.setSpacing(10)
        card_layout.addWidget(self.h2h_container)
        self.h2h_container.hide()
        self.trend_heading = QLabel("得分走势")
        self.trend_heading.setObjectName("ScoreHeading")
        card_layout.addWidget(self.trend_heading)
        self.trend_chart = ScoreTrendWidget()
        card_layout.addWidget(self.trend_chart)
        self.trend_note = QLabel("仅展示本机运行期间观察到的局分；不补造漏掉的回合。")
        self.trend_note.setObjectName("Meta")
        self.trend_note.setWordWrap(True)
        card_layout.addWidget(self.trend_note)
        self.meta = QLabel()
        self.meta.setObjectName("Meta")
        self.meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.meta)

        self.back.clicked.connect(self.back_requested)
        self.star.clicked.connect(self._on_star_clicked)
        self.player_a.clicked.connect(lambda: self.player_clicked.emit(request_from_match(self._match, 0)))
        self.player_b.clicked.connect(lambda: self.player_clicked.emit(request_from_match(self._match, 1)))

    def set_match(self, match: Match) -> None:
        key = match.content_key()
        if key == self._content_key:
            return
        self._match = match
        self._content_key = key
        self._updated_at = datetime.now()
        now = self._updated_at
        self.score_strip.set_scores([])

        self.competition.setText(match.competition)
        set_star_state(self.star, self._favorites.contains(match.id))
        self.player_a.setText(player_html(match.player_a))
        self.player_b.setText(player_html(match.player_b))
        self.player_a.setEnabled(not match.has_games)
        self.player_b.setEnabled(not match.has_games)
        self.player_a_raw.setText(match.player_a_raw or "")
        self.player_a_raw.setVisible(bool(match.player_a_raw))
        self.player_b_raw.setText(match.player_b_raw or "")
        self.player_b_raw.setVisible(bool(match.player_b_raw))
        trend_available = not match.has_games and bool(match.sets or match.current_set or match.score_events)
        self.h2h_container.setVisible(match.status == STATUS_UPCOMING)
        self.trend_heading.setVisible(trend_available)
        self.trend_chart.setVisible(trend_available)
        self.trend_note.setVisible(trend_available or match.has_games)
        if match.has_games:
            self.trend_note.setText("团体赛目前只有逐场对阵与局分，没有可核实的逐分过程。")

        if match.status == STATUS_LIVE:
            self.badge.setObjectName("BadgeLive")
            self.badge.setText("● LIVE")
            self.score.setObjectName("MatchScore")
            self.score.setText(
                f"{match.score_a} : {match.score_b}" if match.score_known else "—"
            )
            if match.has_games:
                self._set_games(match)
                self.sets_text.setVisible(False)
            else:
                self._set_sets(match)
                self.sets_text.setVisible(True)
            self.meta.setText(relative_update_text(self._updated_at, now))
        elif match.status == STATUS_UPCOMING:
            self.badge.clear()
            self.score.setObjectName("MatchTime")
            self.score.setText(match_time_text(match))
            self.sets_text.clear()
            self.sets_text.setVisible(True)
            self.games_container.setVisible(False)
            self.current_label.clear()
            self.meta.setText(countdown_text(match, now))
        else:
            self.badge.setObjectName("BadgeFinal")
            self.badge.setText("已结束")
            self.score.setObjectName("MatchScore")
            self.score.setText(
                f"{match.score_a} : {match.score_b}" if match.has_score else "—"
            )
            if match.has_games:
                self._set_games(match)
                self.sets_text.setVisible(False)
            else:
                self._set_sets(match)
                self.sets_text.setVisible(True)
            self.meta.setText("已结束")
        if match.data_stale:
            self.badge.setObjectName("BadgeStale")
            self.badge.setText("⚠ 旧数据")
            self.meta.setText("比分未重新核对 · 数据源正在重试")
        elif match.score_reconciled:
            self.meta.setText(self.meta.text() + " · 总比分按已结束局分校正")
        for label in (self.badge, self.score):
            style = label.style()
            style.unpolish(label)
            style.polish(label)

    def set_h2h_report(self, report: H2HReport) -> None:
        """Render the verified sample only; an empty sample is not a 0:0 career record."""
        while self.h2h_box.count():
            item = self.h2h_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._match or self._match.status != STATUS_UPCOMING:
            self.h2h_container.hide()
            return
        self.h2h_container.show()
        title = QLabel("历史交手 · 已核实赛果")
        title.setObjectName("H2HHeading")
        self.h2h_box.addWidget(title)
        if not report.eligible:
            self._h2h_label("个人交手统计仅适用于已确认身份的单打对阵。", "H2HMuted")
            return
        if not report.meetings:
            self._h2h_label("暂无可核实的交手记录；这不代表双方此前从未交手。", "H2HMuted")
            self._h2h_label("统计范围：当前已加载的官方赛事结果及本程序收录的大赛决赛。", "H2HMuted")
            return
        self._h2h_label(
            f"已核实 {len(report.meetings)} 场   {report.wins_a} 胜 : {report.wins_b} 胜",
            "H2HScore")
        self._h2h_label(
            f"局数合计  {report.sets_a} : {report.sets_b}  ·  左侧为{escape(self._match.player_a)}",
            "H2HMuted")
        self._h2h_label("最近 5 场", "H2HSubheading")
        for row in report.meetings[:5]:
            winner = self._match.player_a if row.winner == 0 else self._match.player_b
            label = QLabel(
                f"{row.date:%Y-%m-%d}  ·  {escape(row.competition)}<br>"
                f"<b>{escape(winner)}胜</b>  {row.sets_a} : {row.sets_b}")
            label.setObjectName("H2HRow")
            label.setWordWrap(True)
            self.h2h_box.addWidget(label)
        self._h2h_label("按赛事统计", "H2HSubheading")
        for item in report.competitions:
            label = QLabel(
                f"{escape(item.name)}  ·  {item.meetings} 场  ·  "
                f"胜场 {item.wins_a}:{item.wins_b}  ·  局数 {item.sets_a}:{item.sets_b}")
            label.setObjectName("H2HRow")
            label.setWordWrap(True)
            self.h2h_box.addWidget(label)
        self._h2h_label(
            "仅统计当前已加载、身份与比分均可核实的单打结果；不是完整职业生涯交手记录。",
            "H2HMuted")

    def _h2h_label(self, text: str, object_name: str) -> None:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        self.h2h_box.addWidget(label)

    def set_trend_points(self, points: list[TrendPoint]) -> None:
        self.trend_chart.set_points(points)
        if self._match and self._match.has_games:
            self.trend_note.setText("团体赛目前只有逐场对阵与局分，没有可核实的逐分过程。")
            return
        if not points:
            self.trend_note.setText("暂无逐分样本；数据源未提供得分过程。")
        elif all(sum(p.set_number == n for p in points) == 1
                 for n in {p.set_number for p in points}):
            self.trend_note.setText("正值为左方领先，负值为右方领先。仅有每局终值，无法还原局内领先与反超；空心圆点表示局末。")
        else:
            self.trend_note.setText(
                "正值为左方领先，负值为右方领先。实线为连续采样，虚线表示中间有漏采样；"
                "橙圈标记局点、已确认的连得分或官方事件。"
                "暂停与赛点仅在官方事件或赛制数据明确时显示。"
            )

    def _set_sets(self, match: Match) -> None:
        self.sets_text.setText("逐局比分 · 上行为左侧选手" if match.sets or match.current_set else
                               "逐场对阵资料暂缺" if "团体" in match.competition else "逐局比分暂未取得")
        self.score_strip.set_scores(match.sets, match.current_set if match.status == STATUS_LIVE else None)
        self.games_container.setVisible(False)
        if match.status == STATUS_LIVE and match.current_set:
            self.current_label.setText(
                f"本局 {match.current_set[0]} : {match.current_set[1]}"
            )
            self.current_label.setVisible(True)
        else:
            self.current_label.clear()
            self.current_label.setVisible(False)

    def _set_games(self, match: Match) -> None:
        """队伍制比赛：逐场显示选手对阵与每局比分（WTT 风格）。"""
        while self.games_box.count():
            item = self.games_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.current_label.setVisible(False)
        self.games_container.setVisible(True)
        for index, game in enumerate(match.games):
            row = QWidget()
            row.setObjectName("GameRow")
            row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            layout = QVBoxLayout(row)
            layout.setContentsMargins(14, 10, 14, 10)
            layout.setSpacing(2)
            title = QLabel(f"第 {index + 1} 场 · " + ("双打" if "/" in game.player_a else "单打"))
            title.setObjectName("ScoreHeading")
            layout.addWidget(title)
            header = QHBoxLayout()
            header.setSpacing(12)
            home = PlayerLink(game.player_a)
            home.setWordWrap(True)
            home.clicked.connect(lambda name=game.player_a: self.player_clicked.emit(PlayerRequest(name)))
            score = QLabel(f"{game.score_a} : {game.score_b}")
            score.setObjectName("GameScore")
            score.setAlignment(Qt.AlignmentFlag.AlignCenter)
            away = PlayerLink(game.player_b)
            away.setWordWrap(True)
            away.clicked.connect(lambda name=game.player_b: self.player_clicked.emit(PlayerRequest(name)))
            away.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            header.addWidget(home, 1)
            header.addWidget(score)
            header.addWidget(away, 1)
            layout.addLayout(header)
            sets = ScoreStrip()
            sets.set_scores(game.sets)
            layout.addWidget(sets)
            if not game.sets:
                missing = QLabel("逐局分资料暂缺")
                missing.setObjectName("Meta")
                layout.addWidget(missing)
            self.games_box.addWidget(row)
            if index < len(match.games) - 1:
                divider = QLabel()
                divider.setObjectName("Divider")
                self.games_box.addWidget(divider)

    def refresh_time(self, now: datetime) -> None:
        if not self._match or self._match.status != STATUS_LIVE or self._match.data_stale:
            return
        text = relative_update_text(self._updated_at, now)
        if self._match.score_reconciled:
            text += " · 总比分按已结束局分校正"
        if self.meta.text() != text:
            self.meta.setText(text)

    def _on_star_clicked(self) -> None:
        favorite = self._favorites.toggle(self._match.id)
        set_star_state(self.star, favorite)
        self.favorite_toggled.emit(self._match.id, favorite)
