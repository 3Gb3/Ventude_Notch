from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ventude.core.async_worker import AsyncWorker
from ventude.services.market import MarketService, Quote
from ventude.ui import themes
from ventude.ui.icons import icon_button


class _Bridge(QObject):
    quotes = Signal(list)
    error = Signal(str)


class MarketPage(QWidget):
    def __init__(self, service: MarketService, worker: AsyncWorker) -> None:
        super().__init__()
        self.service, self.worker = service, worker
        self.bridge = _Bridge()
        self.bridge.quotes.connect(self._show)
        self.bridge.error.connect(lambda m: self.status.setText(m))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        row = QHBoxLayout()
        refresh = icon_button("refresh", "Atualizar cotações")
        refresh.clicked.connect(self.refresh)
        title = QLabel("Mercado")
        title.setObjectName("Title")
        title.setToolTip("Cotações de Yahoo Finance e CoinGecko")
        row.addWidget(title)
        row.addStretch()
        row.addWidget(refresh)
        lay.addLayout(row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nome", "Preço", "Var. %", "Fonte"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(
            f"QTableWidget {{ background:{themes.GRAPHITE}; border:1px solid {themes.BORDER};"
            "border-radius:12px; padding:4px; }"
            f"QHeaderView::section {{ background:{themes.GRAPHITE}; color:{themes.TEXT_MUTED};"
            "border:none; padding:10px; text-align:left; }"
            "QTableWidget::item { border:none; padding:6px; }"
            f"QTableWidget::item:selected {{ background:{themes.GREEN_DIM}; }}"
            f"QTableCornerButton::section {{ background:{themes.GRAPHITE}; border:none; }}"
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self.table, 1)
        self.status = QLabel("Cache de 10 min.")
        self.status.setObjectName("Muted")
        lay.addWidget(self.status)
        self.refresh()

    def refresh(self) -> None:
        self.status.setText("Carregando cotações…")

        async def run() -> None:
            try:
                self.bridge.quotes.emit(await self.service.all())
            except Exception as exc:  # noqa: BLE001
                self.bridge.error.emit(f"Falha: {exc.__class__.__name__}")

        self.worker.submit(run())

    def _show(self, quotes: list) -> None:
        self.table.setRowCount(len(quotes))
        for r, q in enumerate(quotes):
            assert isinstance(q, Quote)
            price = f"{q.price:,.2f}"
            if q.currency:
                price = f"{price} {q.currency}"
            change = "—" if q.change_pct is None else f"{q.change_pct:+.2f}%"
            vals = [q.name, price, change, q.source]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if c in (1, 2):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if c == 3:
                    item.setForeground(QColor(themes.TEXT_MUTED))
                if c == 2 and q.change_pct is not None:
                    color = themes.GREEN if q.change_pct >= 0 else themes.DANGER
                    item.setForeground(QColor(color))
                self.table.setItem(r, c, item)
        self.status.setText(f"{len(quotes)} cotações (cache até 10 min).")
