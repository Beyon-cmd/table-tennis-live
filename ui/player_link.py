"""A player name that can be activated without opening its parent match card."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel


class PlayerLink(QLabel):
    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("PlayerLink")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("点击查看选手资料")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)
