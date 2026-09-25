"""Consistent searchable selector for event, project and draw stage."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QScrollArea, QFrame, QLineEdit, QLabel, QHBoxLayout, QApplication


class ModernSelect(QWidget):
    currentIndexChanged = Signal(int)

    def __init__(self, placeholder="请选择", searchable=False, parent=None):
        super().__init__(parent)
        self._items = []
        self._index = -1
        self._searchable = searchable
        self._popup = None
        self.button = QPushButton(placeholder)
        self.button.setObjectName("ModernSelectButton")
        self.button.setToolTip(placeholder)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.open_popup)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.button)

    def addItem(self, text, data=None):
        self._items.append((str(text),data))
        if self._index < 0:
            self.setCurrentIndex(0)

    def clear(self):
        self._items.clear()
        self._index = -1
        self.button.setText("请选择")
        self.button.setToolTip("请选择")
        if self._popup:
            self._popup.close()

    def currentData(self):
        return self._items[self._index][1] if 0 <= self._index < len(self._items) else None

    def currentIndex(self):
        return self._index

    def findData(self, data):
        return next((i for i,item in enumerate(self._items) if item[1] == data),-1)

    def setCurrentIndex(self,index):
        if not 0 <= index < len(self._items) or index == self._index:
            return
        self._index = index
        text = self._items[index][0]
        self.button.setText(text)
        self.button.setToolTip(text)
        self.currentIndexChanged.emit(index)

    def open_popup(self):
        if not self._items:
            return
        if self._popup:
            self._popup.close()
        popup = QFrame(None,Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        popup.setObjectName("ModernSelectPopup")
        self._popup = popup
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(5)
        if self._searchable and len(self._items) > 8:
            search = QLineEdit()
            search.setObjectName("SelectorSearch")
            search.setPlaceholderText("搜索赛事…")
            layout.addWidget(search)
        else:
            search = None
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("SelectorList")
        items_layout = QVBoxLayout(content)
        items_layout.setContentsMargins(0,0,0,0)
        items_layout.setSpacing(3)
        rows = []
        for index,(text,data) in enumerate(self._items):
            option = QPushButton(("✓  " if index == self._index else "   ") + text)
            option.setObjectName("SelectorOption")
            option.setToolTip(text)
            option.setProperty("selected",index == self._index)
            option.setCursor(Qt.CursorShape.PointingHandCursor)
            option.setMinimumHeight(40)
            option.clicked.connect(lambda checked=False,i=index: self._choose(i,popup))
            items_layout.addWidget(option)
            rows.append((text.lower(),option))
        items_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        if search:
            def filter_items(query):
                terms = query.lower().split()
                for text,option in rows:
                    option.setVisible(all(term in text for term in terms))
            search.textChanged.connect(filter_items)
        width = max(self.width(),min(680,max(len(x[0]) for x in self._items)*10+54))
        width = min(width, max(220,QApplication.primaryScreen().availableGeometry().width()-32))
        height = min(440, len(self._items)*43+25+(48 if search else 0))
        popup.resize(width,height)
        anchor = self.mapToGlobal(self.rect().bottomLeft())
        screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = min(max(anchor.x(),area.left()+8),area.right()-width-8)
        y = anchor.y()
        if y+height > area.bottom()-8:
            y = self.mapToGlobal(self.rect().topLeft()).y()-height
        popup.move(x,max(area.top()+8,y))
        popup.show()
        if search:
            search.setFocus()

    def _choose(self,index,popup):
        self.setCurrentIndex(index)
        popup.close()
        if self._popup is popup:
            self._popup = None
