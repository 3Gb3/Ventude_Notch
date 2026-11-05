from __future__ import annotations

from calendar import monthcalendar
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ventude.services.calendar_store import CalendarStore, parse_time
from ventude.ui import themes
from ventude.ui.icons import icon_button


class CalendarPage(QWidget):
    def __init__(self, store: CalendarStore) -> None:
        super().__init__()
        self.store = store
        self.cursor = date.today().replace(day=1)
        self.selected = date.today()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        nav = QHBoxLayout()
        prev = icon_button("arrow-left", "Mês anterior", 32)
        nxt = icon_button("arrow-right", "Próximo mês", 32)
        prev.clicked.connect(lambda: self._shift(-1))
        nxt.clicked.connect(lambda: self._shift(1))
        self.month_label = QLabel()
        self.month_label.setObjectName("Title")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        today_btn = QPushButton("Hoje")
        today_btn.clicked.connect(self._today)
        nav.addWidget(prev)
        nav.addWidget(self.month_label, 1)
        nav.addWidget(today_btn)
        nav.addWidget(nxt)
        lay.addLayout(nav)

        body = QHBoxLayout()
        body.setSpacing(20)
        month = QVBoxLayout()
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(4)
        self.grid.setVerticalSpacing(4)
        self.day_buttons: list[QPushButton] = []
        for i, name in enumerate(["S", "T", "Q", "Q", "S", "S", "D"]):
            lab = QLabel(name)
            lab.setObjectName("Muted")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(lab, 0, i)
        for r in range(6):
            for c in range(7):
                b = QPushButton("")
                b.setCheckable(True)
                b.setFixedHeight(30)
                b.setMinimumWidth(28)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(self._day_clicked)
                self.grid.addWidget(b, r + 1, c)
                self.day_buttons.append(b)
        month.addLayout(self.grid)
        month.addStretch()
        body.addLayout(month, 1)

        agenda = QVBoxLayout()
        self.day_title = QLabel()
        self.day_title.setObjectName("Section")
        agenda.addWidget(self.day_title)
        self.events = QListWidget()
        self.events.setWordWrap(True)
        agenda.addWidget(self.events, 1)
        body.addLayout(agenda, 1)
        lay.addLayout(body, 1)

        form = QHBoxLayout()
        self.title_in = QLineEdit()
        self.title_in.setPlaceholderText("Novo evento")
        self.title_in.returnPressed.connect(self._add)
        self.time_in = QLineEdit()
        self.time_in.setPlaceholderText("HH:MM")
        self.time_in.setFixedWidth(70)
        self.time_in.returnPressed.connect(self._add)
        add = icon_button("plus", "Adicionar evento no dia selecionado")
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        rem = icon_button("trash", "Remover evento selecionado")
        rem.clicked.connect(self._remove)
        form.addWidget(self.title_in, 1)
        form.addWidget(self.time_in)
        form.addWidget(add)
        form.addWidget(rem)
        lay.addLayout(form)
        note = QLabel("Calendário local. Eventos ficam só neste PC.")
        note.setObjectName("Muted")
        lay.addWidget(note)
        self._rebuild()

    def _shift(self, months: int) -> None:
        y, m = self.cursor.year, self.cursor.month + months
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        self.cursor = date(y, m, 1)
        self._rebuild()

    def _today(self) -> None:
        self.selected = date.today()
        self.cursor = self.selected.replace(day=1)
        self._rebuild()

    def _rebuild(self) -> None:
        months = [
            "",
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ]
        self.month_label.setText(f"{months[self.cursor.month]} {self.cursor.year}")
        marked = self.store.month_days_with_events(self.cursor.year, self.cursor.month)
        weeks = monthcalendar(self.cursor.year, self.cursor.month)
        for i, b in enumerate(self.day_buttons):
            week = i // 7
            col = i % 7
            day = weeks[week][col] if week < len(weeks) else 0
            b.blockSignals(True)
            b.setVisible(week < len(weeks))
            border = "transparent"
            color = themes.TEXT
            if day == 0:
                b.setText("")
                b.setEnabled(False)
                b.setChecked(False)
            else:
                b.setEnabled(True)
                b.setText(str(day))
                d = date(self.cursor.year, self.cursor.month, day)
                b.setChecked(d == self.selected)
                b.setToolTip(d.strftime("%d/%m/%Y") + (" · com eventos" if day in marked else ""))
                if day in marked:
                    color = themes.GREEN
                if d == date.today():
                    border = themes.GREEN_DIM
            b.setStyleSheet(
                "QPushButton { padding:0; border-radius:9px; background:transparent; "
                f"border:1px solid {border}; color:{color}; }}"
                f"QPushButton:hover {{ background:{themes.GRAPHITE_LIGHT}; }}"
                f"QPushButton:checked {{ background:{themes.GREEN_DIM}; color:{themes.GREEN}; }}"
            )
            b.blockSignals(False)
        self._load_day()

    def _day_clicked(self) -> None:
        btn = self.sender()
        if not isinstance(btn, QPushButton) or not btn.text():
            return
        self.selected = date(self.cursor.year, self.cursor.month, int(btn.text()))
        self._rebuild()

    def _load_day(self) -> None:
        self.day_title.setText(self.selected.strftime("%d/%m/%Y"))
        self.events.clear()
        for ev in self.store.for_day(self.selected):
            item = QListWidgetItem(f"{ev.when}  {ev.title}")
            item.setData(Qt.ItemDataRole.UserRole, ev.id)
            self.events.addItem(item)
        if not self.events.count():
            self.day_title.setText(self.day_title.text() + " · dia livre")

    def _add(self) -> None:
        title = self.title_in.text().strip()
        if not title:
            return
        try:
            start = parse_time(self.time_in.text())
        except ValueError:
            self.day_title.setText("Horário inválido (use HH:MM).")
            return
        self.store.add(title, self.selected, start)
        self.title_in.clear()
        self.time_in.clear()
        self._rebuild()

    def _remove(self) -> None:
        item = self.events.currentItem()
        if not item:
            return
        self.store.remove(int(item.data(Qt.ItemDataRole.UserRole)))
        self._rebuild()
