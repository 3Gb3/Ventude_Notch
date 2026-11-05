from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ventude.core.async_worker import AsyncWorker
from ventude.services.news import FEEDS, NewsItem, NewsService
from ventude.ui.icons import icon_button


class _Bridge(QObject):
    items = Signal(list)
    error = Signal(str)


class NewsPage(QWidget):
    def __init__(self, service: NewsService, worker: AsyncWorker) -> None:
        super().__init__()
        self.service, self.worker = service, worker
        self.bridge = _Bridge()
        self.bridge.items.connect(self._show)
        self.bridge.error.connect(lambda m: self.status.setText(m))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        row = QHBoxLayout()
        refresh = icon_button("refresh", "Atualizar notícias")
        refresh.clicked.connect(self.refresh)
        open_btn = icon_button("arrow-right", "Abrir notícia selecionada no navegador")
        open_btn.clicked.connect(self._open)
        title = QLabel("No radar")
        title.setObjectName("Title")
        title.setToolTip("Fontes: " + ", ".join(FEEDS))
        row.addWidget(title)
        row.addStretch()
        row.addWidget(refresh)
        row.addWidget(open_btn)
        lay.addLayout(row)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setSpacing(4)
        self.list.itemActivated.connect(lambda _: self._open())
        lay.addWidget(self.list, 1)
        self.status = QLabel("G1 · BBC Brasil · Tecnoblog")
        self.status.setObjectName("Muted")
        lay.addWidget(self.status)
        self.refresh()

    def refresh(self) -> None:
        self.status.setText("Carregando…")

        async def run() -> None:
            try:
                items = await self.service.fetch()
                self.bridge.items.emit(items)
            except Exception as exc:  # noqa: BLE001
                self.bridge.error.emit(f"Falha: {exc.__class__.__name__}")

        self.worker.submit(run())

    def _show(self, items: list) -> None:
        self.list.clear()
        for it in items:
            assert isinstance(it, NewsItem)
            meta = it.source + (f" · {it.published}" if it.published else "")
            text = f"{it.title}\n{meta}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, it.link)
            item.setToolTip(it.summary or it.link)
            self.list.addItem(item)
        self.status.setText(f"{len(items)} notícias (cache até 15 min).")

    def _open(self) -> None:
        item = self.list.currentItem()
        if item:
            QDesktopServices.openUrl(QUrl(str(item.data(Qt.ItemDataRole.UserRole))))
