"""与 WTT 签表共用现代化画布的亚运会乒乓球签表页。"""
from __future__ import annotations

import threading
from datetime import datetime

import httpx

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QLabel, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QWidget

from data_sources.asian_games import BASE, _official_json, apply_team_detail
from data_sources.asian_games_draws import PROJECTS, fetch_brackets
from models import Match, STATUS_FINISHED
from ui.player_link import PlayerLink
from ui.score_strip import ScoreStrip
from ui.wtt_draws import WTTDrawsPage


class AsianGamesDrawsPage(WTTDrawsPage):
    """保持 WTT 的卡片、平移、缩放、选择器和 30 秒自动刷新。"""

    team_detail_ready = Signal(object, object, str)

    def __init__(self, theme, parent=None):
        super().__init__(theme, parent)
        self._events = [{"id": "AG2026"}]
        self.event_combo.blockSignals(True)
        self.event_combo.addItem("2026 爱知·名古屋亚运会", "AG2026")
        self.event_combo.blockSignals(False)
        self.event_combo.hide()
        self.project.blockSignals(True)
        self.project.clear()
        for label, code in PROJECTS.items():
            self.project.addItem(label, code)
        self.project.blockSignals(False)
        for label in self.findChildren(QLabel):
            if label.objectName() == "HeroTitle" and label.text() == "赛事签表":
                label.setText("亚运会 · 乒乓球签表")
            elif label.text().startswith("官方晋级路线"):
                label.setText("官方签表 · 单打 / 双打 / 团体 · 拖动浏览 · Ctrl＋滚轮缩放 · 点击卡片查看比分")
        self.status.setText("选择项目后读取亚运会官方签表")
        self.team_detail_ready.connect(self._show_team_detail)

    def refresh(self):
        if self._closed.is_set() or self._busy:
            return
        self.timer.stop()
        self._busy = True
        self.refresh_button.setEnabled(False)
        key = self.key()
        self.status.setText("正在读取亚运会官方签表…")

        def work():
            try:
                data, error = fetch_brackets(key[1]), ""
            except Exception as exc:
                data, error = None, str(exc)
            if not self._closed.is_set():
                try:
                    self.ready.emit(key, data, error)
                except RuntimeError:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def open_match(self, match):
        if ".TEAM" not in (self.project.currentData() or "") or match["bye"]:
            super().open_match(match)
            return
        self.status.setText("正在读取团体赛逐场比分…")

        def work():
            try:
                with httpx.Client(headers={"User-Agent": "Mozilla/5.0", "Referer": "https://results.asiangames2026.org/",
                                           "Accept-Encoding": "identity"}, timeout=16.0) as client:
                    payload = _official_json(client.get(f"{BASE}/results/{match['id']}"))
                detail = Match(
                    id=f"asiangames:{match['id']}", source="majors", competition="2026 亚运会 · 团体",
                    status=STATUS_FINISHED, start_time=datetime.now(),
                    player_a=match["players"][0]["name"], player_b=match["players"][1]["name"],
                )
                apply_team_detail(detail, payload)
                games, error = detail.games, ""
            except Exception as exc:
                games, error = [], str(exc)
            if not self._closed.is_set():
                try:
                    self.team_detail_ready.emit(match, games, error)
                except RuntimeError:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _show_team_detail(self, match, games, error):
        if self._closed.is_set():
            return
        self.status.setText("官方团体赛逐场比分已核对" if games else "官方逐场比分暂不可用")
        dialog = QDialog(self)
        dialog.setWindowTitle("亚运会 · 团体赛详情")
        dialog.resize(660, min(720, 230 + len(games) * 105))
        layout = QVBoxLayout(dialog)
        players = match["players"]
        title = QLabel(f"{players[0]['name']}  {players[0]['score']} : {players[1]['score']}  {players[1]['name']}")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        if not games:
            note = QLabel("官方尚未发布逐场比分" if not error else "官方详情暂时无法获取，请稍后重试")
            note.setObjectName("Meta")
            layout.addWidget(note)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            rows = QVBoxLayout(content)
            for index, game in enumerate(games, 1):
                header = QLabel(f"第 {index} 场")
                header.setObjectName("Meta")
                rows.addWidget(header)
                names = QHBoxLayout()
                for name, score, country in ((game.player_a, game.score_a, players[0]["country"]),
                                             (game.player_b, game.score_b, players[1]["country"])):
                    link = PlayerLink(f"{name}  {score}")
                    link.setTextFormat(Qt.TextFormat.PlainText)
                    link.clicked.connect(lambda n=name, c=country: self._open_player({"name": n, "raw": n, "country": c}))
                    names.addWidget(link)
                rows.addLayout(names)
                strip = ScoreStrip()
                strip.set_scores(game.sets, None)
                rows.addWidget(strip)
            rows.addStretch()
            scroll.setWidget(content)
            layout.addWidget(scroll)
        close = QPushButton("关闭")
        close.setObjectName("RankingButton")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()
