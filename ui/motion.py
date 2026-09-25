"""Interruptible scrolling and lightweight page transitions."""
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt
from PySide6.QtWidgets import QScrollArea, QStackedWidget, QLabel, QGraphicsOpacityEffect


class SmoothScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._scroll.setDuration(180)
        self._scroll.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._target = 0
        self.verticalScrollBar().sliderPressed.connect(self._scroll.stop)

    def wheelEvent(self, event):
        if not event.pixelDelta().isNull() or event.modifiers() != Qt.KeyboardModifier.NoModifier:
            self._scroll.stop()
            return super().wheelEvent(event)
        delta = event.angleDelta().y()
        if not delta:
            return super().wheelEvent(event)
        bar = self.verticalScrollBar()
        origin = self._target if self._scroll.state() == QPropertyAnimation.State.Running else bar.value()
        self._target = max(bar.minimum(), min(bar.maximum(), origin - int(delta * 0.9)))
        self._scroll.stop()
        self._scroll.setStartValue(bar.value())
        self._scroll.setEndValue(self._target)
        self._scroll.start()
        event.accept()


class TransitionStack(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._overlay = QLabel(self)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        effect = QGraphicsOpacityEffect(self._overlay)
        self._overlay.setGraphicsEffect(effect)
        self._fade = QPropertyAnimation(effect, b"opacity", self)
        self._fade.setDuration(150)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._overlay.hide)
        self._overlay.hide()

    def resizeEvent(self, event):
        self._fade.stop()
        self._overlay.hide()
        super().resizeEvent(event)

    def setCurrentWidget(self, widget):
        if widget is self.currentWidget():
            return
        self._fade.stop()
        self._overlay.hide()
        old = self.currentWidget()
        snapshot = old.grab() if old and self.isVisible() else None
        super().setCurrentWidget(widget)
        if snapshot:
            self._overlay.setPixmap(snapshot)
            self._overlay.setGeometry(self.rect())
            self._overlay.show()
            self._overlay.raise_()
            self._fade.setStartValue(1.0)
            self._fade.setEndValue(0.0)
            self._fade.start()
