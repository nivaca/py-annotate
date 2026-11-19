"""Find and highlight: look for a word, a phrase or a regular expression, on
all the pages or on the page shown, see where it is, and highlight (or
underline, strike out...) all the places found, or those chosen."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)

from ..annots import MARKUP, NAMES
from ..interface import N_, ntr, tr
from ..search import Match, find_text

SCOPES = [("all", N_("All pages")), ("page", N_("This page")), ("from", N_("From this page to the end"))]


class FindDialog(QDialog):
    """Not modal: the window stays usable while it is open. It asks the window (through the
    signals) to show a place found, and to mark the places chosen."""

    show_match = Signal(object)  # Match
    mark = Signal(list, str)  # [Match], the kind of mark

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(tr("Find and highlight"))
        self.matches: list[Match] = []
        self.searching = False
        self.stop_asked = False
        self.query = QLineEdit()
        self.query.setPlaceholderText(tr("Text to find"))
        self.query.returnPressed.connect(self.search)
        self.case = QCheckBox(tr("Match case"))
        self.whole = QCheckBox(tr("Whole words"))
        self.regex = QCheckBox(tr("Regular expression"))
        self.scope = QComboBox()
        for value, name in SCOPES:
            self.scope.addItem(tr(name), value)
        self.kind = QComboBox()
        for kind in MARKUP:
            self.kind.addItem(tr(NAMES[kind]), kind)
        self.find_button = QPushButton(tr("Find"))
        self.find_button.setDefault(True)
        self.find_button.clicked.connect(self.search)
        self.results = QListWidget()
        self.results.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.results.itemDoubleClicked.connect(lambda item: self.show_match.emit(self._match(item)))
        self.results.currentItemChanged.connect(lambda item, _: self.show_match.emit(self._match(item))
                                                if item is not None else None)
        self.summary = QLabel()
        self.mark_all = QPushButton(tr("Mark all"))
        self.mark_all.clicked.connect(lambda: self._mark(self.matches))
        self.mark_chosen = QPushButton(tr("Mark those chosen"))
        self.mark_chosen.clicked.connect(lambda: self._mark([self._match(i) for i in self.results.selectedItems()]))
        close = QPushButton(tr("Close"))
        close.clicked.connect(self.close)
        options = QHBoxLayout()
        for box in (self.case, self.whole, self.regex):
            options.addWidget(box)
        options.addStretch(1)
        form = QFormLayout()
        row = QHBoxLayout()
        row.addWidget(self.query, 1)
        row.addWidget(self.find_button)
        form.addRow(tr("Find:"), row)
        form.addRow("", options)
        form.addRow(tr("Where:"), self.scope)
        form.addRow(tr("Mark as:"), self.kind)
        buttons = QHBoxLayout()
        buttons.addWidget(self.mark_all)
        buttons.addWidget(self.mark_chosen)
        buttons.addStretch(1)
        buttons.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.results, 1)
        lay.addWidget(self.summary)
        lay.addLayout(buttons)
        self.resize(560, 520)
        self._enable()

    def start(self, text: str = ""):
        if text:
            self.query.setText(text)
        self.show()
        self.raise_()
        self.activateWindow()
        self.query.setFocus()
        self.query.selectAll()

    def _match(self, item: QListWidgetItem) -> Match:
        return self.matches[item.data(Qt.ItemDataRole.UserRole)]

    def _enable(self):
        self.mark_all.setEnabled(bool(self.matches) and not self.searching)
        self.mark_chosen.setEnabled(bool(self.matches) and not self.searching)

    def pages(self) -> list[int] | None:
        scope = self.scope.currentData()
        if scope == "page":
            return [self.window.page]
        if scope == "from":
            return list(range(self.window.page, self.window.count))
        return None

    def search(self):
        """Find (or, while it looks, stop)."""
        if self.searching:
            self.stop_asked = True
            return
        doc = self.window.doc
        self.matches, self.stop_asked = [], False
        self.results.clear()
        if doc is None or not self.query.text().strip():
            self.summary.setText("")
            self._enable()
            return
        self.searching = True
        self.find_button.setText(tr("Stop"))
        self._enable()

        def progress(done, total):
            self.summary.setText(tr("Looking… page {page} of {count}", page=done, count=total))
            QApplication.processEvents()
            return not self.stop_asked

        error = ""
        try:
            self.matches = find_text(doc, self.query.text(), self.pages(), self.case.isChecked(),
                                     self.whole.isChecked(), self.regex.isChecked(), progress)
        except re.error as e:
            error = tr("The regular expression is not right: {error}", error=e)
            self.matches = []
        finally:
            self.searching = False
            self.find_button.setText(tr("Find"))
        for n, m in enumerate(self.matches):
            item = QListWidgetItem(tr("Page {page}", page=m.page + 1) + ": " + m.context)
            item.setData(Qt.ItemDataRole.UserRole, n)
            self.results.addItem(item)
        if error:
            self.summary.setText(error)
        elif self.matches:
            self.summary.setText(ntr("{count} place found", "{count} places found", len(self.matches))
                                 + ntr(", on {count} page", ", on {count} pages",
                                       len({m.page for m in self.matches})))
        else:
            self.summary.setText(tr("Not found"))
        self._enable()

    def _mark(self, matches: list[Match]):
        if matches:
            self.mark.emit(matches, self.kind.currentData())
