from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ventude.core.events import EventBus
from ventude.services.lists_store import ListsStore
from ventude.ui import themes
from ventude.ui.icons import icon, icon_button


class ListsPage(QWidget):
    def __init__(self, store: ListsStore, bus: EventBus) -> None:
        super().__init__()
        self.store, self.bus = store, bus
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        toolbar = QHBoxLayout()
        title = QLabel("Suas listas")
        title.setObjectName("Title")
        toolbar.addWidget(title)
        toolbar.addStretch()
        for name, tooltip, fn in (
            ("plus", "Criar lista", self._add_list),
            ("trash", "Excluir lista selecionada e seus itens", self._del_list),
        ):
            button = icon_button(name, tooltip)
            button.clicked.connect(fn)
            toolbar.addWidget(button)
        lay.addLayout(toolbar)
        top = QHBoxLayout()
        self.lists = QListWidget()
        self.lists.setMaximumWidth(160)
        self.lists.currentRowChanged.connect(lambda _: self._load_items())
        top.addWidget(self.lists)
        right = QVBoxLayout()
        self.items = QListWidget()
        self.items.itemDoubleClicked.connect(self._toggle)
        right.addWidget(self.items, 1)
        form = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Novo item")
        self.input.returnPressed.connect(self._add_item)
        add = icon_button("plus", "Adicionar item à lista")
        add.setObjectName("Primary")
        add.clicked.connect(self._add_item)
        form.addWidget(self.input, 1)
        form.addWidget(add)
        right.addLayout(form)
        top.addLayout(right, 1)
        lay.addLayout(top, 1)
        btns = QHBoxLayout()
        hint = QLabel("Duplo clique para concluir")
        hint.setObjectName("Muted")
        btns.addWidget(hint)
        btns.addStretch()
        for name, tooltip, fn in (
            ("check", "Concluir ou reabrir item selecionado", self._toggle_selected),
            ("trash", "Remover item selecionado", self._del_item),
        ):
            b = icon_button(name, tooltip)
            b.clicked.connect(fn)
            btns.addWidget(b)
        lay.addLayout(btns)
        self._load_lists()

    def _dialog(self, fn):
        self.bus.menu_opened.emit()
        try:
            return fn()
        finally:
            self.bus.menu_closed.emit()

    def _load_lists(self, select_id: int | None = None) -> None:
        current = select_id
        if current is None and self.lists.currentItem():
            current = int(self.lists.currentItem().data(Qt.ItemDataRole.UserRole))
        self.lists.clear()
        for lst in self.store.lists():
            item = QListWidgetItem(lst.name)
            item.setToolTip(lst.name)
            item.setData(Qt.ItemDataRole.UserRole, lst.id)
            self.lists.addItem(item)
            if current == lst.id:
                self.lists.setCurrentItem(item)
        if self.lists.count() and self.lists.currentRow() < 0:
            self.lists.setCurrentRow(0)
        self._load_items()

    def _current_list_id(self) -> int | None:
        item = self.lists.currentItem()
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _load_items(self) -> None:
        self.items.clear()
        lid = self._current_list_id()
        if lid is None:
            return
        for it in self.store.items(lid):
            item = QListWidgetItem(it.text)
            item.setToolTip(it.text)
            item.setData(Qt.ItemDataRole.UserRole, it.id)
            if it.done:
                item.setIcon(icon("check", themes.GREEN))
                item.setForeground(Qt.GlobalColor.gray)
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
            self.items.addItem(item)

    def _add_list(self) -> None:
        name, ok = self._dialog(lambda: QInputDialog.getText(self, "Nova lista", "Nome:"))
        if ok and name.strip():
            lst = self.store.add_list(name)
            self._load_lists(lst.id)

    def _del_list(self) -> None:
        lid = self._current_list_id()
        if lid is not None:
            self.store.remove_list(lid)
            self._load_lists()

    def _add_item(self) -> None:
        lid = self._current_list_id()
        text = self.input.text().strip()
        if lid is None or not text:
            return
        self.store.add_item(lid, text)
        self.input.clear()
        self._load_items()

    def _toggle(self, item: QListWidgetItem) -> None:
        self.store.toggle(int(item.data(Qt.ItemDataRole.UserRole)))
        self._load_items()

    def _toggle_selected(self) -> None:
        item = self.items.currentItem()
        if item:
            self._toggle(item)

    def _del_item(self) -> None:
        item = self.items.currentItem()
        if item:
            self.store.remove_item(int(item.data(Qt.ItemDataRole.UserRole)))
            self._load_items()
