from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ventude.core.events import EventBus
from ventude.services.launcher import default_label, open_path, validate_path
from ventude.storage.database import Database
from ventude.ui.icons import icon, icon_button


class PinnedPage(QWidget):
    """Lista de aplicativos ou pastas fixados."""

    def __init__(self, kind: str, db: Database, bus: EventBus) -> None:
        super().__init__()
        self.kind, self.db, self.bus = kind, db, bus
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.list = QListWidget()
        self.list.itemActivated.connect(self._open_item)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        row = QHBoxLayout()
        title = QLabel("Seus aplicativos" if kind == "app" else "Suas pastas")
        title.setObjectName("Title")
        row.addWidget(title)
        row.addStretch()
        add = icon_button("plus", "Adicionar aplicativo" if kind == "app" else "Adicionar pasta")
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        buttons = [
            ("arrow-right", "Abrir item selecionado", self._open_selected),
            ("chevron-down", "Mover para cima", lambda: self._move(-1)),
            ("chevron-down", "Mover para baixo", lambda: self._move(1)),
            ("trash", "Desafixar item selecionado", self._remove),
        ]
        row.addWidget(add)
        for name, tooltip, fn in buttons:
            b = icon_button(name, tooltip)
            if tooltip == "Mover para cima":
                b.setIcon(QIcon(icon(name).pixmap(20, 20).transformed(QTransform().rotate(180))))
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        lay.addWidget(self.list)
        lay.addWidget(self.status)
        self.reload()

    def reload(self) -> None:
        self.list.clear()
        items = self.db.list_pinned(self.kind)
        for it in items:
            ok, _ = validate_path(self.kind, it.path)
            text = it.label if ok else f"{it.label}  (caminho inválido)"
            li = QListWidgetItem(text)
            li.setIcon(icon("apps" if self.kind == "app" else "folder"))
            li.setData(Qt.ItemDataRole.UserRole, it.id)
            li.setData(Qt.ItemDataRole.UserRole + 1, it.path)
            li.setToolTip(it.path)
            self.list.addItem(li)
        if not items:
            self.status.setText("Seu espaço está livre. Use + para fixar o que você mais usa.")
        else:
            self.status.setText("Clique duas vezes num item para abrir.")

    def _pick(self) -> str:
        self.bus.menu_opened.emit()
        try:
            if self.kind == "folder":
                return QFileDialog.getExistingDirectory(self, "Escolher pasta")
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Escolher aplicativo",
                "",
                "Aplicativos (*.exe *.lnk *.url *.bat *.cmd *.appref-ms)",
            )
            return path
        finally:
            self.bus.menu_closed.emit()

    def _add(self) -> None:
        path = self._pick()
        if not path:
            return
        ok, msg = validate_path(self.kind, path)
        if not ok:
            self.status.setText(msg)
            return
        if self.db.add_pinned(self.kind, default_label(path), path) is None:
            self.status.setText("Esse item já está fixado.")
            return
        self.reload()
        self.bus.pinned_changed.emit()

    def _selected_id(self) -> int | None:
        it = self.list.currentItem()
        return int(it.data(Qt.ItemDataRole.UserRole)) if it else None

    def _open_item(self, item: QListWidgetItem) -> None:
        ok, msg = open_path(str(item.data(Qt.ItemDataRole.UserRole + 1)))
        self.status.setText("" if ok else f"Não foi possível abrir: {msg}")

    def _open_selected(self) -> None:
        if it := self.list.currentItem():
            self._open_item(it)

    def _move(self, delta: int) -> None:
        if (i := self._selected_id()) is not None:
            row = self.list.currentRow()
            self.db.move_pinned(i, delta)
            self.reload()
            self.list.setCurrentRow(max(0, min(self.list.count() - 1, row + delta)))

    def _remove(self) -> None:
        if (i := self._selected_id()) is not None:
            self.db.remove_pinned(i)
            self.reload()
            self.bus.pinned_changed.emit()
