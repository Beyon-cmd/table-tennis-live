"""主窗口：顶部栏 + 左侧导航 + 右侧信息流。"""
from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from models import Match, SOURCE_ORDER, SOURCE_NAMES, STATUS_LIVE
from services.storage import FavoritesStore
from services.updater import Updater
from services.score_trend import ScoreTrendStore
from services.h2h import build_h2h
from ui.match_detail import MatchDetailPage
from ui.section_view import FeedPage
from ui.theme import ThemeManager
from ui.rankings import RankingsPage
from ui.motion import TransitionStack
from ui.wtt_draws import WTTDrawsPage
from ui.asian_games_draws import AsianGamesDrawsPage
from ui.player_profile import PlayerProfileDialog
from data_sources.player_profiles import PlayerRequest, PlayerProfileService, split_players
from data_sources.majors import MAJOR_EVENTS, MajorsDataSource

NAV_ITEMS = [
    ("home", "首页"),
    ("live", "🔴 实时"),
    ("schedule", "📅 今日赛程"),
    ("favorites", "⭐ 我的关注"),
    ("rankings", "世界排名"),
]

PAGE_TITLES = {
    "home": "首页",
    "live": "实时",
    "schedule": "今日赛程",
    "favorites": "我的关注",
    "search": "搜索",
    "detail": "比赛详情",
    "rankings": "世界排名",
}

MAJOR_HISTORY_SECTIONS = {
    "奥运会": [("奥运会", "历届奥运会 · 乒乓球决赛")],
    "世锦赛": [("世锦赛", "世界乒乓球锦标赛 · 单项决赛"),
             ("团体世锦赛", "世界乒乓球团体锦标赛 · 决赛")],
    "世界杯": [("世界杯", "乒乓球世界杯 · 单项决赛"),
             ("团体世界杯", "乒乓球团体世界杯 · 决赛"),
             ("混合团体世界杯", "混合团体世界杯 · 决赛")],
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        updater: Updater,
        theme: ThemeManager,
        favorites: FavoritesStore,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Table Tennis Live")
        self.resize(1180, 780)
        self.setMinimumSize(960, 640)

        self._updater = updater
        self._theme = theme
        self._favorites = favorites
        self._matches: dict[str, Match] = {}
        self._score_trends = ScoreTrendStore()
        self._source_health: dict[str, tuple[datetime | None, str]] = {}
        self._league_filter: str | None = None
        self._major_category = "亚运会"
        self._major_draw_mode = False
        self._major_history_selected = False
        self._major_active = {category: False for category in MAJOR_HISTORY_SECTIONS}
        self._query = ""
        self._current_nav_key = "home"
        self._prev_page: QWidget | None = None
        self._detail_id: str | None = None
        self._nav_keys: dict[str, QPushButton] = {}
        self._page_for_nav: dict[str, QWidget] = {}
        self._profile_service = PlayerProfileService()
        event_types = {str(event["id"]): event["type"] for event in MAJOR_EVENTS}
        historical = MajorsDataSource().get_historical_matches()
        self._historical_matches = {match.id: match for match in historical}
        self._historical_by_type: dict[str, list[Match]] = {}
        for match in historical:
            event_id = match.id.split(":", 2)[1]
            self._historical_by_type.setdefault(event_types[event_id], []).append(match)

        # ---------- 主体布局 ----------
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_sidebar())
        outer.addLayout(self._build_right(), 1)

        # ---------- 刷新与信号 ----------
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_times)
        self._timer.start()

        updater.changed.connect(self._on_matches_changed)
        updater.removed.connect(self._on_matches_removed)
        updater.error.connect(self._on_refresh_error)
        updater.source_status.connect(self._on_source_status)
        updater.detail_ready.connect(self._on_detail_ready)
        theme.changed.connect(self._update_theme_button)
        self._update_theme_button()

    # ================= 界面搭建 =================
    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 18, 12, 14)
        layout.setSpacing(4)

        brand = QLabel("●  TABLE TENNIS")
        brand.setObjectName("Brand")
        brand.setContentsMargins(8, 0, 0, 10)
        layout.addWidget(brand)
        tagline = QLabel("LIVE CENTER  /  乒乓球赛事中心")
        tagline.setObjectName("Meta")
        tagline.setContentsMargins(8, 0, 0, 16)
        layout.addWidget(tagline)

        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setProperty("nav", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            nav_group.addButton(btn)
            layout.addWidget(btn)
            self._nav_keys[key] = btn

        divider = QLabel()
        divider.setObjectName("Divider")
        layout.addSpacing(10)
        layout.addWidget(divider)
        layout.addSpacing(6)

        group_title = QLabel("赛事")
        group_title.setObjectName("NavGroupTitle")
        group_title.setContentsMargins(8, 4, 0, 4)
        layout.addWidget(group_title)

        league_group = QButtonGroup(self)
        league_group.setExclusive(False)
        for source in SOURCE_ORDER:
            btn = QPushButton(SOURCE_NAMES[source])
            btn.setProperty("nav", True)
            btn.setProperty("league", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda checked, s=source: self._on_league_toggled(s, checked)
            )
            league_group.addButton(btn)
            layout.addWidget(btn)

        layout.addStretch(1)
        self.source_health_label = QLabel("数据源 · 等待首次取数")
        self.source_health_label.setObjectName("SourceHealth")
        self.source_health_label.setContentsMargins(8, 4, 8, 0)
        layout.addWidget(self.source_health_label)
        self.status_label = QLabel("● 正在连接…")
        self.status_label.setObjectName("SidebarStatus")
        self.status_label.setContentsMargins(8, 8, 8, 0)
        layout.addWidget(self.status_label)

        nav_group.buttonClicked.connect(self._on_nav_clicked)
        self._nav_group = nav_group
        return sidebar

    def _build_right(self) -> QVBoxLayout:
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        topbar = QWidget()
        topbar.setObjectName("TopBar")
        bar = QHBoxLayout(topbar)
        bar.setContentsMargins(24, 10, 20, 10)
        bar.setSpacing(10)
        self.page_title = QLabel("首页")
        self.page_title.setObjectName("PageTitle")
        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText("🔍 搜索比赛、球员、赛事")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedWidth(280)
        self.refresh_button = QPushButton("🔄")
        self.refresh_button.setObjectName("IconButton")
        self.refresh_button.setToolTip("立即刷新")
        self.refresh_button.setToolTip("立即检查更新；直播约每 2 秒轮询，实际延迟取决于官方数据源")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("IconButton")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        bar.addWidget(self.page_title)
        bar.addStretch(1)
        bar.addWidget(self.search_box)
        bar.addWidget(self.refresh_button)
        bar.addWidget(self.theme_button)
        right.addWidget(topbar)

        self.wtt_tabs = QWidget()
        tab_layout = QHBoxLayout(self.wtt_tabs)
        tab_layout.setContentsMargins(24,8,24,0)
        self.wtt_list_button = QPushButton("比赛列表")
        self.wtt_draw_button = QPushButton("赛事签表")
        for button in (self.wtt_list_button,self.wtt_draw_button):
            button.setObjectName("RankingButton")
            button.setCheckable(True)
            tab_layout.addWidget(button)
        tab_layout.addStretch()
        self.wtt_list_button.setChecked(True)
        self.wtt_list_button.clicked.connect(lambda: self._switch_wtt_tab(False))
        self.wtt_draw_button.clicked.connect(lambda: self._switch_wtt_tab(True))
        self.wtt_tabs.hide()
        right.addWidget(self.wtt_tabs)

        self.majors_tabs = QWidget()
        majors_layout = QHBoxLayout(self.majors_tabs)
        majors_layout.setContentsMargins(24, 8, 24, 0)
        self._major_buttons = {}
        for name in ("奥运会", "世锦赛", "世界杯", "亚运会"):
            button = QPushButton(name)
            button.setObjectName("RankingButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, category=name: self._switch_major_category(category))
            majors_layout.addWidget(button)
            self._major_buttons[name] = button
        majors_layout.addStretch()
        self.majors_tabs.hide()
        right.addWidget(self.majors_tabs)

        self.major_view_tabs = QWidget()
        major_view_layout = QHBoxLayout(self.major_view_tabs)
        major_view_layout.setContentsMargins(24, 4, 24, 0)
        self.major_list_button = QPushButton("比赛列表")
        self.major_draw_button = QPushButton("赛事签表")
        for button in (self.major_list_button, self.major_draw_button):
            button.setObjectName("RankingButton")
            button.setCheckable(True)
            major_view_layout.addWidget(button)
        major_view_layout.addStretch()
        self.major_list_button.clicked.connect(lambda: self._switch_major_view(False))
        self.major_draw_button.clicked.connect(lambda: self._switch_major_view(True))
        self.major_view_tabs.hide()
        right.addWidget(self.major_view_tabs)

        self._stack = TransitionStack()
        self.home_page = FeedPage(
            [("live", "正在进行"), ("upcoming", "即将开始"), ("finished", "最近结束")],
            self._favorites,
            self._open_detail,
            self._on_favorite_toggled,
        )
        self.live_page = FeedPage(
            [("live", "正在直播")],
            self._favorites,
            self._open_detail,
            self._on_favorite_toggled,
        )
        self.schedule_page = FeedPage(
            [("upcoming", "今日赛程 · 即将开始"), ("finished", "已结束")],
            self._favorites,
            self._open_detail,
            self._on_favorite_toggled,
        )
        self.favorites_page = FeedPage(
            [("all", "我的关注")],
            self._favorites,
            self._open_detail,
            self._on_favorite_toggled,
        )
        self.search_page = FeedPage(
            [("all", "搜索结果")],
            self._favorites,
            self._open_detail,
            self._on_favorite_toggled,
        )
        self.detail_page = MatchDetailPage(self._favorites)
        self.rankings_page = RankingsPage()
        self.draws_page = WTTDrawsPage(self._theme)
        self.asian_draws_page = AsianGamesDrawsPage(self._theme)
        self.major_history_pages = {}
        self.major_current_pages = {}
        for category, sections in MAJOR_HISTORY_SECTIONS.items():
            self.major_current_pages[category] = FeedPage(
                [("live", "正在进行"), ("upcoming", "即将开始"), ("finished", "最近结束")],
                self._favorites, self._open_detail, self._on_favorite_toggled,
            )
            page = FeedPage(sections, self._favorites, self._open_detail, self._on_favorite_toggled)
            groups = {kind: sorted(self._historical_by_type.get(kind, []),
                                   key=lambda match: match.start_time, reverse=True)
                      for kind, _ in sections}
            page.update_sections(groups)
            self.major_history_pages[category] = page
        self.detail_page.back_requested.connect(self._back_from_detail)
        self.detail_page.favorite_toggled.connect(self._on_favorite_toggled)
        for page in (self.home_page, self.live_page, self.schedule_page, self.favorites_page,
                     self.search_page, self.detail_page, self.rankings_page, self.draws_page,
                     self.asian_draws_page, *self.major_history_pages.values(),
                     *self.major_current_pages.values()):
            page.player_clicked.connect(self._open_player)
        for page in (
            self.home_page,
            self.live_page,
            self.schedule_page,
            self.favorites_page,
            self.search_page,
            self.detail_page,
            self.rankings_page,
            self.draws_page,
            self.asian_draws_page,
            *self.major_history_pages.values(),
            *self.major_current_pages.values(),
        ):
            self._stack.addWidget(page)

        self._page_for_nav = {
            "home": self.home_page,
            "live": self.live_page,
            "schedule": self.schedule_page,
            "favorites": self.favorites_page,
            "rankings": self.rankings_page,
        }
        right.addWidget(self._stack, 1)

        self.search_box.textChanged.connect(self._on_search_changed)
        self.refresh_button.clicked.connect(self._refresh_current_page)
        self.theme_button.clicked.connect(self._cycle_theme)
        self._nav_keys["home"].setChecked(True)
        return right

    # ================= 导航 =================
    def _switch_wtt_tab(self, draws):
        self.wtt_list_button.setChecked(not draws)
        self.wtt_draw_button.setChecked(draws)
        self.page_title.setText("WTT · 赛事签表" if draws else "WTT · 比赛列表")
        self._stack.setCurrentWidget(self.draws_page if draws else self.home_page)

    def _switch_major_category(self, category: str) -> None:
        self._major_category = category
        for name, button in self._major_buttons.items():
            button.setChecked(name == category)
        self.major_view_tabs.setVisible(True)
        if category == "亚运会":
            self.major_list_button.setText("比赛列表")
            self.major_draw_button.setText("赛事签表")
            self.major_list_button.setEnabled(True)
            self._switch_major_view(self._major_draw_mode)
        else:
            self.major_list_button.setText("当期比赛")
            self.major_draw_button.setText("历届决赛")
            self.major_list_button.setEnabled(self._has_current_major(category))
            self._major_history_selected = not self._has_current_major(category)
            self._switch_major_view(self._major_history_selected)

    def _has_current_major(self, category: str) -> bool:
        now = datetime.now()
        return any(
            m.source == "majors" and m.major_category == category and not m.data_stale
            and ((m.status == "live" and now - timedelta(days=2) <= m.start_time <= now)
                 or (m.status == "upcoming" and now - timedelta(days=1) <= m.start_time
                     <= now + timedelta(days=45)))
            for m in self._matches.values()
        )

    def _switch_major_view(self, draws: bool) -> None:
        if self._major_category != "亚运会":
            category = self._major_category
            self._major_history_selected = draws
            self.major_list_button.setChecked(not draws)
            self.major_draw_button.setChecked(draws)
            self.page_title.setText(f"大赛 · {category} · {'历届决赛' if draws else '当期比赛'}")
            self._stack.setCurrentWidget(
                self.major_history_pages[category] if draws else self.major_current_pages[category]
            )
            return
        self._major_draw_mode = draws
        self.major_list_button.setChecked(not draws)
        self.major_draw_button.setChecked(draws)
        self.page_title.setText("大赛 · 亚运会 · 赛事签表" if draws else "大赛 · 亚运会 · 比赛列表")
        self._stack.setCurrentWidget(self.asian_draws_page if draws else self.home_page)

    def _refresh_current_page(self):
        if self._stack.currentWidget() is self.draws_page:
            self.draws_page.refresh()
        elif self._stack.currentWidget() is self.asian_draws_page:
            self.asian_draws_page.refresh()
        elif self._stack.currentWidget() is self.rankings_page:
            self.rankings_page.refresh()
        else:
            self._updater.request_refresh()

    def _on_nav_clicked(self, button: QPushButton) -> None:
        for key, btn in self._nav_keys.items():
            if btn is button:
                self.wtt_tabs.setVisible(self._league_filter == "WTT" and key == "home")
                self.majors_tabs.setVisible(self._league_filter == "majors" and key == "home")
                self.major_view_tabs.setVisible(self._league_filter == "majors" and key == "home")
                self.wtt_list_button.setChecked(True)
                self.wtt_draw_button.setChecked(False)
                btn.setChecked(True)
                self._current_nav_key = key
                self.page_title.setText(PAGE_TITLES[key])
                if key == "home" and self._league_filter == "majors":
                    self._switch_major_category(self._major_category)
                else:
                    self._stack.setCurrentWidget(self._page_for_nav[key])
                return

    def _go_home(self) -> None:
        self._nav_keys["home"].setChecked(True)
        self._current_nav_key = "home"
        self.page_title.setText(PAGE_TITLES["home"])
        self._stack.setCurrentWidget(self.home_page)

    def _on_league_toggled(self, source: str, checked: bool) -> None:
        self._league_filter = source if checked else None
        for btn in self.findChildren(QPushButton):
            if btn.property("league"):
                btn.setChecked(checked and btn.text() == SOURCE_NAMES[source])
        self._go_home()
        self.wtt_tabs.setVisible(checked and source == "WTT")
        self.majors_tabs.setVisible(checked and source == "majors")
        self.major_view_tabs.setVisible(checked and source == "majors")
        self.wtt_list_button.setChecked(True)
        self.wtt_draw_button.setChecked(False)
        if checked and source == "WTT":
            self.page_title.setText("WTT · 比赛列表")
        elif checked and source == "majors":
            self._switch_major_category(self._major_category)
        self._refresh_pages()

    def _on_search_changed(self, text: str) -> None:
        self._query = text.strip().lower()
        if self._query:
            if self._stack.currentWidget() is not self.search_page:
                self._prev_page = self._stack.currentWidget()
            self.page_title.setText(PAGE_TITLES["search"])
            self._stack.setCurrentWidget(self.search_page)
            self._uncheck_nav()
        elif self._stack.currentWidget() is self.search_page:
            self._stack.setCurrentWidget(self._prev_page or self.home_page)
            self._nav_keys[self._current_nav_key].setChecked(True)
        self._refresh_pages()

    def _uncheck_nav(self) -> None:
        for btn in self._nav_keys.values():
            btn.setChecked(False)

    # ================= 详情 =================
    def _open_player(self, request: PlayerRequest) -> None:
        names = split_players(request.name)
        if len(names) > 1:
            raw_names = split_players(request.raw)
            menu = QMenu(self)
            for index, name in enumerate(names):
                action = menu.addAction(name)
                action.setData(index)
            chosen = menu.exec(QCursor.pos())
            if chosen is not None:
                index = chosen.data()
                self._open_player(PlayerRequest(names[index], raw_names[index] if index < len(raw_names) else "", request.country))
            return
        if not names or names[0] in ("轮空", "待定", "TBD", "BYE", "—"):
            return
        dialog = PlayerProfileDialog(request, self._profile_service, self.rankings_page._rows, self)
        dialog.exec()
        dialog.deleteLater()

    def _open_detail(self, match_id: str) -> None:
        match = self._matches.get(match_id) or self._historical_matches.get(match_id)
        if match is None:
            return
        self._prev_page = self._stack.currentWidget()
        self._detail_id = match_id
        self.page_title.setText(PAGE_TITLES["detail"])
        self.detail_page.set_match(match)
        self._update_h2h(match)
        self._score_trends.observe(match)
        self.detail_page.set_trend_points(self._score_trends.points(match))
        if match_id not in self._historical_matches:
            self._updater.request_detail(match_id)
        self._uncheck_nav()
        self._stack.setCurrentWidget(self.detail_page)

    def _on_detail_ready(self, match) -> None:
        self._matches[match.id] = match
        self._score_trends.observe(match)
        if self._detail_id == match.id:
            self.detail_page.set_match(match)
            self._update_h2h(match)
            self.detail_page.set_trend_points(self._score_trends.points(match))

    def _update_h2h(self, match: Match) -> None:
        if match.status == "upcoming":
            self.detail_page.set_h2h_report(build_h2h(
                match, list(self._matches.values()) + list(self._historical_matches.values())))

    def _back_from_detail(self) -> None:
        self._detail_id = None
        self._stack.setCurrentWidget(self._prev_page or self.home_page)
        if self._league_filter == "majors" and self._major_category in MAJOR_HISTORY_SECTIONS:
            suffix = "历届决赛" if self._major_history_selected else "当期比赛"
            self.page_title.setText(f"大赛 · {self._major_category} · {suffix}")
        else:
            self.page_title.setText(PAGE_TITLES[self._current_nav_key])
        self._nav_keys[self._current_nav_key].setChecked(True)

    # ================= 数据更新 =================
    def _on_matches_changed(self, matches) -> None:
        for m in matches:
            self._matches[m.id] = m
            self._score_trends.observe(m)
        if self._detail_id and self._detail_id in {m.id for m in matches}:
            detail = self._matches.get(self._detail_id)
            if detail is not None:
                self.detail_page.set_match(detail)
                self._update_h2h(detail)
                self.detail_page.set_trend_points(self._score_trends.points(detail))
        elif self._detail_id and self._detail_id in self._matches:
            # Another result may have finished while this fixture remains open.
            self._update_h2h(self._matches[self._detail_id])
        self._refresh_pages()

    def _on_matches_removed(self, ids) -> None:
        for mid in ids:
            self._matches.pop(mid, None)
        if self._detail_id in ids:
            self._back_from_detail()
        elif self._detail_id and self._detail_id in self._matches:
            self._update_h2h(self._matches[self._detail_id])
        self._refresh_pages()

    def _on_refresh_error(self, message: str) -> None:
        # 具体状态由 source_status 管理，不能让下一次页面刷新抹掉告警。
        self.status_label.setToolTip(message)

    def _on_source_status(self, source: str, last_success: datetime | None, error: str) -> None:
        self._source_health[source] = (last_success, error)
        self._update_source_health()

    def _update_source_health(self) -> None:
        lines = ["数据源 · 最近成功取数"]
        tooltips = ["时间是本机取数时间，并非官网发布比分的时间。"]
        for source in SOURCE_ORDER:
            name = SOURCE_NAMES[source].replace("日本 ", "").replace("德国 ", "").replace("中国", "")
            checked, error = self._source_health.get(source, (None, ""))
            time_text = checked.strftime("%H:%M:%S") if checked else "尚未成功"
            state = "⚠" if error else "●" if checked else "○"
            lines.append(f"{state} {name}  {time_text}")
            if error:
                tooltips.append(f"{SOURCE_NAMES[source]}：{error}")
        self.source_health_label.setText("\n".join(lines))
        self.source_health_label.setToolTip("\n".join(tooltips))
        matches = [m for m in self._matches.values()
                   if not self._league_filter or m.source == self._league_filter]
        live_count = sum(m.status == STATUS_LIVE for m in matches)
        visible_sources = [self._league_filter] if self._league_filter else SOURCE_ORDER
        failed = sum(bool(self._source_health.get(source, (None, ""))[1]) for source in visible_sources)
        scope = SOURCE_NAMES.get(self._league_filter, "全部赛事")
        if failed:
            self.status_label.setText(f"⚠ {failed} 个源异常 · {live_count} 场 LIVE")
        else:
            self.status_label.setText(f"● {scope} · {live_count} 场 LIVE")
        self.status_label.setToolTip("\n".join(tooltips))

    def _refresh_pages(self) -> None:
        matches = list(self._matches.values())
        if self._league_filter:
            matches = [m for m in matches if m.source == self._league_filter]

        self._update_source_health()

        live = self._sort_live([m for m in matches if m.status == "live"])
        upcoming = self._sort_upcoming([m for m in matches if m.status == "upcoming"])
        finished_all = self._sort_finished([m for m in matches if m.status == "finished"])
        if self._league_filter:
            # 选中具体赛事（如「大赛」）时展示该组全部已结束比赛
            finished = finished_all
        else:
            # 信息流里展示最近 72 小时的已结束比赛，并确保有官方比分的
            # 场次一定可见（搜索不受此限制）
            now = datetime.now()
            recent_finished = [
                m for m in finished_all
                if m.start_time >= now - timedelta(hours=72)
            ]
            scored_extra = [
                m for m in finished_all
                if m.has_score and m not in recent_finished
            ]
            finished = (recent_finished + scored_extra)[:30]
        self.home_page.update_sections(
            {"live": live, "upcoming": upcoming, "finished": finished}
        )
        self.live_page.update_sections({"live": live})
        self.schedule_page.update_sections(
            {"upcoming": upcoming, "finished": finished}
        )
        for category, page in self.major_current_pages.items():
            current = [m for m in self._matches.values()
                       if m.source == "majors" and m.major_category == category]
            page.update_sections({
                "live": self._sort_live([m for m in current if m.status == "live"]),
                "upcoming": self._sort_upcoming([m for m in current if m.status == "upcoming"]),
                "finished": self._sort_finished([m for m in current if m.status == "finished"]),
            })
            active = self._has_current_major(category)
            if active != self._major_active[category]:
                self._major_active[category] = active
                if (self._league_filter == "majors" and self._major_category == category
                        and self._current_nav_key == "home" and self._stack.currentWidget()
                        in (self.major_current_pages[category], self.major_history_pages[category])):
                    self.major_list_button.setEnabled(active)
                    self._switch_major_view(not active)
        favorites = matches + list(self._historical_matches.values())
        self.favorites_page.update_sections(
            {"all": self._sort_display([m for m in favorites if self._favorites.contains(m.id)])}
        )
        if self._query:
            terms = self._query.split()
            search_pool = matches + (list(self._historical_matches.values())
                                     if self._league_filter in (None, "majors") else [])
            results = [
                m for m in search_pool
                if all(term in m.search_text() for term in terms)
            ]
            self.search_page.update_sections({"all": self._sort_display(results)})

    def _refresh_times(self) -> None:
        now = datetime.now()
        for page in (
            self.home_page,
            self.live_page,
            self.schedule_page,
            self.favorites_page,
            self.search_page,
            *self.major_current_pages.values(),
        ):
            for card in page.all_cards():
                card.refresh_time(now)
        self.detail_page.refresh_time(now)

    # ================= 收藏 =================
    def _on_favorite_toggled(self, match_id: str, favorite: bool) -> None:
        self._refresh_pages()

    # ================= 主题 =================
    def _cycle_theme(self) -> None:
        self._theme.cycle()

    def _update_theme_button(self) -> None:
        self.theme_button.setText(self._theme.mode_label())
        self.theme_button.setToolTip("切换主题：浅色 / 深色 / 跟随系统")

    # ================= 排序 =================
    @staticmethod
    def _sort_live(matches):
        return sorted(
            matches,
            key=lambda m: (
                SOURCE_ORDER.index(m.source) if m.source in SOURCE_ORDER else 99,
                m.start_time,
            ),
        )

    @staticmethod
    def _sort_upcoming(matches):
        return sorted(matches, key=lambda m: m.start_time)

    @staticmethod
    def _sort_finished(matches):
        return sorted(matches, key=lambda m: m.last_update, reverse=True)

    @staticmethod
    def _sort_display(matches):
        rank = {"live": 0, "upcoming": 1, "finished": 2}
        source_rank = {s: i for i, s in enumerate(SOURCE_ORDER)}
        return sorted(
            matches,
            key=lambda m: (
                source_rank.get(m.source, 99),
                rank.get(m.status, 3),
                m.start_time,
            ),
        )

    # ================= 退出 =================
    def closeEvent(self, event):
        self.draws_page.shutdown()
        self.asian_draws_page.shutdown()
        self.rankings_page.shutdown()
        self._updater.stop()
        super().closeEvent(event)
