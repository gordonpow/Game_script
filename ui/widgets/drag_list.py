"""
可拖曳排序清單容器
支援節點卡片的拖曳重新排序
"""
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PyQt6.QtCore import Qt, pyqtSignal


class DragList(QListWidget):
    """
    可拖曳排序的清單
    拖曳後觸發 order_changed signal
    """
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setSpacing(2)
        self.setUniformItemSizes(False)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.order_changed.emit()
