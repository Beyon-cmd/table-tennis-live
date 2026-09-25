"""Independent background ranking requests never hold up score polling."""
import threading
from PySide6.QtCore import Qt, Signal, QTimer
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QFrame
from data_sources.rankings import fetch_rankings, parse_rankings
from data_sources.name_map import to_chinese_name
from services.storage import JsonStore, DATA_DIR
from ui.flags import flag_path
from ui.player_link import PlayerLink
from data_sources.player_profiles import PlayerRequest
from PySide6.QtGui import QIcon


class RankingsPage(QWidget):
    loaded = Signal(object, str)
    player_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._closed = threading.Event()
        self._event = "MS"
        self._store = JsonStore(DATA_DIR / "rankings.json", {})
        try:
            cached = self._store._data
            self._rows = parse_rankings({"Result": cached.get("MS", []) + cached.get("WS", [])})
        except (ValueError, TypeError, AttributeError, KeyError):
            self._rows = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        hero = QFrame()
        hero.setObjectName("RankingHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel("世界排名")
        title.setObjectName("HeroTitle")
        hero_layout.addWidget(title)
        caption = QLabel("WORLD RANKING  /  男单与女单 · 官方发布后自动同步")
        caption.setObjectName("HeroCaption")
        caption.setWordWrap(True)
        hero_layout.addWidget(caption)
        podium = QHBoxLayout()
        self._podium = []
        for index in range(3):
            label = PlayerLink("等待官方排名")
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setObjectName("Podium")
            label.setWordWrap(True)
            label.clicked.connect(lambda i=index: self._open_row(i))
            podium.addWidget(label, 1)
            self._podium.append(label)
        hero_layout.addLayout(podium)
        layout.addWidget(hero)
        tabs = QHBoxLayout()
        self._tabs = {}
        for code, title in (("MS", "男子单打"), ("WS", "女子单打")):
            button = QPushButton(title)
            button.setObjectName("RankingButton")
            button.setCheckable(True)
            self._tabs[code] = button
            button.clicked.connect(lambda checked=False, c=code: self.select(c))
            tabs.addWidget(button)
        tabs.addStretch()
        self.refresh_button = QPushButton("更新排名")
        self.refresh_button.setObjectName("RankingButton")
        self.refresh_button.clicked.connect(self.refresh)
        tabs.addWidget(self.refresh_button)
        layout.addLayout(tabs)
        self.info = QLabel("排名按官方发布周期更新，不随比赛实时变化")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.table = QTableWidget(0, 5)
        self.table.setObjectName("RankingTable")
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setHorizontalHeaderLabels(["世界排名", "选手", "协会", "积分", "排名变化"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellClicked.connect(lambda row, column: self._open_row(row))
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.loaded.connect(self._complete)
        self.select("MS")
        self.sync_status = QLabel("每 60 秒检查官方更新 · 官方排名非逐场实时积分")
        self.sync_status.setObjectName("Meta")
        layout.addWidget(self.sync_status)
        self._timer = QTimer(self)
        self._timer.setInterval(60000)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        QTimer.singleShot(0, self.refresh)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def select(self, event):
        self._event = event
        for code, button in self._tabs.items():
            button.setChecked(code == event)
        rows = self._rows.get(event, [])
        for index, label in enumerate(self._podium):
            label.setEnabled(index < len(rows))
            if index < len(rows):
                row = rows[index]
                name = to_chinese_name(row["PlayerName"]) or row["PlayerName"]
                label.setText(f"#{row['rank']}  {name}\n{row['points']:,} 积分")
            else:
                label.setText("等待官方排名")
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            name = to_chinese_name(row["PlayerName"]) or row["PlayerName"]
            if isinstance(name, tuple):
                name = name[0]
            try:
                change = int(row.get("RankingDifference") or 0)
                difference = f"↑ {change}" if change > 0 else f"↓ {abs(change)}" if change < 0 else "—"
            except (ValueError, TypeError):
                difference = "—"
            values = [row["rank"], name, row.get("CountryCode", ""), row["points"], difference]
            for j, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if j == 2:
                    path = flag_path(str(value))
                    if path:
                        item.setIcon(QIcon(str(path)))
                item.setToolTip(row["PlayerName"])
                self.table.setItem(i, j, item)
        self.table.setUpdatesEnabled(True)
        if rows:
            label = "男单" if event == "MS" else "女单"
            self.info.setText(f"{label} · {len(rows)} 位选手 · 官方发布日期：{rows[0].get('PublishDate', '未知')} · 来源：WTT / ITTF")

    def _open_row(self, index):
        rows = self._rows.get(self._event, [])
        if 0 <= index < len(rows):
            row = rows[index]
            self.player_clicked.emit(PlayerRequest(row["PlayerName"], row["PlayerName"], str(row.get("CountryCode") or ""), str(row.get("IttfId") or "")))

    def refresh(self):
        if self._busy or self._closed.is_set():
            return
        self._timer.stop()
        self._busy = True
        self.refresh_button.setEnabled(False)
        self.sync_status.setText("正在检查官方排名…已有数据保持可浏览")
        def run():
            try:
                rows, error = fetch_rankings(), ""
            except Exception as exc:
                rows, error = None, str(exc)
            if not self._closed.is_set():
                try:
                    self.loaded.emit(rows, error)
                except RuntimeError:
                    pass  # The Qt parent may already have been deleted on exit.
        threading.Thread(target=run, daemon=True).start()

    def _complete(self, rows, error):
        if self._closed.is_set():
            return
        self._busy = False
        self.refresh_button.setEnabled(True)
        self._timer.start()
        if rows:
            changed = rows != self._rows
            self._rows = rows
            self._store._data = rows
            try:
                self._store.save()
            except OSError:
                pass
            if changed:
                scroll = self.table.verticalScrollBar().value()
                self.select(self._event)
                self.table.verticalScrollBar().setValue(scroll)
            self.sync_status.setText(f"{datetime.now():%H:%M:%S} 已核对 · {'排名已更新' if changed else '官方暂无新排名'} · 60 秒后再次检查")
            self.info.setToolTip("")
        else:
            self.sync_status.setText("更新失败 · 保留上次排名 · 60 秒后自动重试")
            self.info.setToolTip(error)

    def shutdown(self):
        self._closed.set()
        self._timer.stop()
