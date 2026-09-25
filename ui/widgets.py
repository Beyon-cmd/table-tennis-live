"""共用的小部件与工具函数。"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QPushButton

from models import Match


def relative_update_text(updated: datetime, now: datetime) -> str:
    seconds = max(0, int((now - updated).total_seconds()))
    if seconds < 60:
        return f"{seconds} 秒前比分变化"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前比分变化"
    return f"{seconds // 3600} 小时前比分变化"


def countdown_text(match: Match, now: datetime) -> str:
    seconds = (match.start_time - now).total_seconds()
    if seconds <= 60:
        return "即将开始"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} 分钟后开始"
    hours, mins = divmod(minutes, 60)
    return f"{hours} 小时 {mins} 分后开始" if mins else f"{hours} 小时后开始"


def match_time_text(match: Match) -> str:
    return match.start_time.strftime("%H:%M")


def set_star_state(button: QPushButton, favorite: bool) -> None:
    button.setText("★" if favorite else "☆")
    button.setProperty("favorite", favorite)
    style = button.style()
    style.unpolish(button)
    style.polish(button)


class ClickableFrame(QFrame):
    clicked = Signal(str)

    def __init__(self, match_id: str, parent=None):
        super().__init__(parent)
        self._match_id = match_id
        self.setObjectName("Card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(self._match_id)
        super().mouseReleaseEvent(event)


def apply_card_shadow(widget: QFrame, dark: bool = False) -> None:
    # Hundreds of offscreen blur effects slow scrolling; cards use themed borders.
    widget.setGraphicsEffect(None)
