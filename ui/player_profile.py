"""Lightweight on-demand player profile, with a verified WTT link when possible."""
from __future__ import annotations

import threading
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from data_sources.player_profiles import PlayerRequest, PlayerProfileService, profile_url, clean_name, resolve_from_rows
from ui.flags import flag_path


class PlayerProfileDialog(QDialog):
    loaded = Signal(object)
    photo_loaded = Signal(object)

    def __init__(self, request: PlayerRequest, service: PlayerProfileService, known_rows=None, parent=None):
        super().__init__(parent)
        self.request = request
        self.service = service
        self._closed = False
        self.setWindowTitle("选手资料")
        self.setMinimumSize(680, 510)
        self.resize(790, 550)
        self.setObjectName("PlayerProfileDialog")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(15)

        hero = QFrame()
        hero.setObjectName("ProfileHero")
        h = QHBoxLayout(hero)
        h.setContentsMargins(24, 22, 24, 22)
        h.setSpacing(20)
        self.avatar = QLabel("正在加载头像…")
        self.avatar.setObjectName("ProfileAvatar")
        self.avatar.setFixedSize(200, 250)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setWordWrap(True)
        h.addWidget(self.avatar)
        headline = QVBoxLayout()
        overline = QLabel("PLAYER PROFILE  /  选手资料")
        overline.setObjectName("ProfileOverline")
        headline.addWidget(overline)
        self.name = QLabel(clean_name(request.name))
        self.name.setObjectName("ProfileName")
        self.name.setWordWrap(True)
        headline.addWidget(self.name)
        self.original = QLabel(request.raw if request.raw and request.raw != clean_name(request.name) else "")
        self.original.setObjectName("ProfileSecondary")
        headline.addWidget(self.original)
        country_row = QHBoxLayout()
        self.flag = QLabel()
        self.flag.setFixedSize(30, 21)
        self.country = QLabel("协会信息加载中…")
        self.country.setObjectName("ProfileSecondary")
        country_row.addWidget(self.flag)
        country_row.addWidget(self.country, 1)
        headline.addLayout(country_row)
        self.age = QLabel("年龄  ·  查询中…")
        self.age.setObjectName("ProfileFact")
        self.style = QLabel("打法  ·  查询中…")
        self.style.setObjectName("ProfileFact")
        headline.addWidget(self.age)
        headline.addWidget(self.style)
        headline.addStretch()
        h.addLayout(headline, 1)
        root.addWidget(hero)

        stats = QHBoxLayout()
        self.rank = self._stat("世界排名", "查询中…")
        self.win_rate = self._stat("本年度胜率", "查询中…")
        self.points = self._stat("排名积分", "查询中…")
        self.category = self._stat("项目", "查询中…")
        for panel in (self.rank[0], self.win_rate[0], self.points[0], self.category[0]):
            stats.addWidget(panel, 1)
        root.addLayout(stats)

        self.note = QLabel("正在核对 WTT 官方排名…")
        self.note.setObjectName("ProfileNote")
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        root.addStretch()
        actions = QHBoxLayout()
        self.source = QLabel("来源：WTT 官方选手资料与 ITTF 排名")
        self.source.setObjectName("Meta")
        actions.addWidget(self.source, 1)
        self.website = QPushButton("查看 WTT 官网资料 ↗")
        self.website.setObjectName("ProfileAction")
        self.website.setEnabled(bool(profile_url(request.player_id)))
        self.website.clicked.connect(self._open_website)
        actions.addWidget(self.website)
        root.addLayout(actions)
        self.loaded.connect(self._show_result)
        self.photo_loaded.connect(self._show_photo)
        self.finished.connect(self._mark_closed)
        if request.country:
            self._set_country(request.country)
        self._data = {"id": request.player_id}
        if known_rows and all(known_rows.values()):
            initial = resolve_from_rows(request, known_rows)
            if initial:
                self._show_result(initial)

        def load():
            try:
                result = service.resolve(request, known_rows)
            except Exception:
                result = {"id": request.player_id, "name": request.raw or request.name, "country": request.country}
            if not self._closed:
                self.loaded.emit(result)
            if result.get("image_url"):
                try:
                    photo = service.photo(result["image_url"])
                except Exception:
                    photo = b""
                if not self._closed:
                    self.photo_loaded.emit(photo)
        threading.Thread(target=load, daemon=True).start()

    @staticmethod
    def _stat(label, value):
        panel = QFrame()
        panel.setObjectName("ProfileStat")
        layout = QVBoxLayout(panel)
        heading = QLabel(label)
        heading.setObjectName("ProfileStatLabel")
        figure = QLabel(value)
        figure.setObjectName("ProfileStatValue")
        figure.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(figure)
        return panel, figure

    def _set_country(self, code):
        code = str(code or "").upper()
        path = flag_path(code)
        if path:
            self.flag.setPixmap(QPixmap(str(path)).scaled(28, 19, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.flag.clear()
        self.country.setText(code)

    def _show_result(self, data):
        self._data = data
        self.name.setText(clean_name(self.request.name))
        if data.get("country"):
            self._set_country(data["country"])
        if data.get("country_name"):
            self.country.setText(f"{data['country_name']}  ·  {data.get('country') or ''}")
        self.age.setText(f"年龄  ·  {data['age']} 岁" if data.get("age") else "年龄  ·  官网未提供")
        hand = {"Right Hand": "右手", "Left Hand": "左手"}.get(data.get("hand"), data.get("hand") or "")
        grip = {"Shakehand": "横拍", "Penhold": "直拍"}.get(data.get("grip"), data.get("grip") or "")
        style = " · ".join(part for part in (hand, grip) if part)
        self.style.setText(f"打法  ·  {style}" if style else "打法  ·  官网未提供")
        if not self.avatar.pixmap():
            self.avatar.setText("正在加载官方头像…" if data.get("image_url") or profile_url(data.get("id")) else "官方暂无头像")
        self.rank[1].setText(f"#{data['rank']}" if data.get("rank") else "暂无排名")
        self.win_rate[1].setText(f"{data['win_rate']}%" if data.get("win_rate") is not None else "—")
        if data.get("year_matches"):
            self.win_rate[1].setToolTip(f"本年度 {data.get('year_wins')} 胜 / {data['year_matches']} 场")
        try:
            self.points[1].setText(f"{int(data['points']):,}" if data.get("points") is not None else "—")
        except (TypeError, ValueError):
            self.points[1].setText("—")
        self.category[1].setText({"MS": "男子单打", "WS": "女子单打"}.get(data.get("event"), "—"))
        verified = bool(profile_url(data.get("id")))
        self.website.setEnabled(verified)
        if data.get("age") or data.get("image_bytes"):
            self.note.setText(f"{data.get('bio') or '个人简介：官网暂未提供。'}  本年度胜率按 WTT 公布的单打胜场与场次计算；资料缺失时不推测。")
        elif data.get("rank"):
            self.note.setText("已取得官方排名，但个人资料暂时未返回。可点击下方按钮查看官网个人页。")
        elif verified:
            self.note.setText("已识别 WTT 选手 ID；当前官方排名数据未列出该选手。可点击下方按钮查看官网个人页。")
        else:
            self.note.setText("目前无法可靠匹配 WTT 个人页。为避免打开同名选手的错误资料，本软件不会猜测链接。")

    def _show_photo(self, data):
        photo = QPixmap()
        if data and photo.loadFromData(data):
            self.avatar.setPixmap(photo.scaled(self.avatar.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.avatar.setText("官方暂无头像")

    def _open_website(self):
        url = profile_url(self._data.get("id"))
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _mark_closed(self, *_):
        self._closed = True

    def closeEvent(self, event):
        self._closed = True
        super().closeEvent(event)
