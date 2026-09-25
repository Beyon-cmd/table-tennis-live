"""信息流页面：若干“标题 + 比赛卡片”分区。"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models import Match
from services.storage import FavoritesStore
from ui.match_card import MatchCard
from ui.motion import SmoothScrollArea


class SectionView(QWidget):
    """一个分区：标题 + 若干比赛卡片。"""
    player_clicked = Signal(object)

    def __init__(
        self,
        title: str,
        favorites: FavoritesStore,
        on_click,
        on_favorite,
        parent=None,
    ):
        super().__init__(parent)
        self._favorites = favorites
        self._on_click = on_click
        self._on_favorite = on_favorite
        self._cards: dict[str, MatchCard] = {}

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        self.count_label = QLabel()
        self.count_label.setObjectName("SectionCount")
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(title_label)
        header.addWidget(self.count_label)
        header.addStretch(1)

        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(10)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addLayout(self.list_layout)
        self.setVisible(False)  # 没有比赛时整个分区隐藏

    def set_matches(self, matches: list[Match]) -> None:
        ids = {m.id for m in matches}
        # 移除已经不在数据里的卡片
        for mid in list(self._cards):
            if mid not in ids:
                card = self._cards.pop(mid)
                self.list_layout.removeWidget(card)
                card.deleteLater()
        # 新增 / 更新卡片（内部有内容指纹，没变化就不重绘）
        for m in matches:
            card = self._cards.get(m.id)
            if card is None:
                card = MatchCard(m, self._favorites)
                card.clicked.connect(self._on_click)
                card.player_clicked.connect(self.player_clicked)
                card.favorite_toggled.connect(self._on_favorite)
                self._cards[m.id] = card
                self.list_layout.addWidget(card)
            else:
                card.set_match(m, datetime.now())
        self.count_label.setText(f"· {len(matches)}")
        for index, match in enumerate(matches):
            card = self._cards[match.id]
            if self.list_layout.indexOf(card) != index:
                self.list_layout.insertWidget(index, card)
        self.setVisible(bool(matches))

    def cards(self) -> list[MatchCard]:
        return list(self._cards.values())


class FeedPage(SmoothScrollArea):
    """滚动信息流页：按分区展示比赛卡片。"""
    player_clicked = Signal(object)

    def __init__(
        self,
        sections: list[tuple[str, str]],
        favorites: FavoritesStore,
        on_click,
        on_favorite,
        parent=None,
    ):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._sections: dict[str, SectionView] = {}

        container = QWidget()
        container.setObjectName("FeedContainer")
        v = QVBoxLayout(container)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(24)
        for key, title in sections:
            section = SectionView(title, favorites, on_click, on_favorite)
            section.player_clicked.connect(self.player_clicked)
            self._sections[key] = section
            v.addWidget(section)
        self.empty_label = QLabel("暂无比赛")
        self.empty_label.setObjectName("EmptyText")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addStretch(1)
        v.addWidget(self.empty_label)
        v.addStretch(1)
        self.setWidget(container)

    def update_sections(self, groups: dict[str, list[Match]]) -> None:
        any_visible = False
        for key, section in self._sections.items():
            matches = groups.get(key, [])
            section.set_matches(matches)
            any_visible = any_visible or bool(matches)
        self.empty_label.setVisible(not any_visible)

    def all_cards(self) -> list[MatchCard]:
        cards: list[MatchCard] = []
        for section in self._sections.values():
            cards.extend(section.cards())
        return cards
