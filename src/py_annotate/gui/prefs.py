"""The Settings dialog: the author written in new annotations and the
recovery copies; the colours offered in the menus, with what each means; and
the keyboard shortcuts."""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config, settings
from ..annots import NAMES
from ..interface import N_, tr
from .props import ColorButton

# the actions with a shortcut that aren't tools
ACTION_NAMES = {"select": N_("Select"), "hand": N_("Hand"), "eraser": N_("Eraser"),
                "comment": N_("Comment on the annotation selected"), "next": N_("Next annotation"),
                "previous": N_("Previous annotation"), "copy": N_("Copy"), "paste": N_("Paste"),
                "duplicate": N_("Duplicate"), "properties": N_("Properties")}


def action_name(action: str) -> str:
    return tr(ACTION_NAMES[action]) if action in ACTION_NAMES else tr(NAMES[action])


class SettingsDialog(QDialog):
    def __init__(self, prefs: settings.Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Settings"))
        self.prefs = prefs
        tabs = QTabWidget()

        general = QWidget()
        form = QFormLayout(general)
        self.author = QLineEdit(prefs.author)
        self.author.setPlaceholderText(tr("Your name"))
        self.author.setToolTip(tr("Written in each new annotation, as its author"))
        form.addRow(tr("Author:"), self.author)
        self.autosave = QSpinBox()
        self.autosave.setRange(0, 120)
        self.autosave.setSuffix(" " + tr("min"))
        self.autosave.setSpecialValueText(tr("Never"))
        self.autosave.setValue(prefs.autosave)
        self.autosave.setToolTip(tr("A copy of the annotations not yet saved is kept this often, and offered "
                                    "if the program stops before they are saved"))
        form.addRow(tr("Recovery copy every:"), self.autosave)
        self.reset = QCheckBox(tr("Put the tools back as they were at first"))
        self.reset.setToolTip(tr("The colours, lines, fonts and opacity of the annotations each tool makes, and "
                                 "how it behaves"))
        form.addRow("", self.reset)
        where = QLabel(tr("The settings are kept in {path}", path=config.config_path()))
        where.setWordWrap(True)
        where.setStyleSheet("color: palette(placeholder-text);")
        form.addRow(where)
        tabs.addTab(general, tr("General"))

        colours = QWidget()
        form = QFormLayout(colours)
        intro = QLabel(tr("The colours offered in the menus, and what each one means to you (shown with its name)"))
        intro.setWordWrap(True)
        form.addRow(intro)
        self.palette_rows = []
        for i, (color, meaning) in enumerate(prefs.palette):
            button = ColorButton(color)
            edit = QLineEdit(meaning if meaning is not None else (
                tr(settings.PALETTE[i][2]) if color == settings.PALETTE[i][0] and settings.PALETTE[i][2] else ""))
            edit.setPlaceholderText(tr("What it means"))
            self.palette_rows.append((button, edit))
            form.addRow(button, edit)
        usual = QPushButton(tr("The usual colours"))
        usual.clicked.connect(self._usual_colours)
        form.addRow("", usual)
        tabs.addTab(colours, tr("Colours"))

        keys = QWidget()
        lay = QVBoxLayout(keys)
        self.keys = QTableWidget(len(settings.SHORTCUTS), 2)
        self.keys.setHorizontalHeaderLabels([tr("Action"), tr("Shortcut")])
        self.keys.verticalHeader().setVisible(False)
        self.keys.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.key_edits: dict[str, QKeySequenceEdit] = {}
        for row, action in enumerate(settings.SHORTCUTS):
            item = QTableWidgetItem(action_name(action))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.keys.setItem(row, 0, item)
            edit = QKeySequenceEdit(QKeySequence(prefs.shortcut(action)))
            edit.setClearButtonEnabled(True)
            self.key_edits[action] = edit
            self.keys.setCellWidget(row, 1, edit)
        lay.addWidget(self.keys)
        usual = QPushButton(tr("The usual keys"))
        usual.clicked.connect(self._usual_keys)
        lay.addWidget(usual, 0, Qt.AlignmentFlag.AlignRight)
        tabs.addTab(keys, tr("Shortcuts"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer = QVBoxLayout(self)
        outer.addWidget(tabs)
        outer.addWidget(buttons)
        self.resize(560, 620)

    def _usual_colours(self):
        for (button, edit), (color, _, meaning) in zip(self.palette_rows, settings.PALETTE):
            button.set_color(color)
            edit.setText(tr(meaning) if meaning else "")

    def _usual_keys(self):
        for action, key in settings.SHORTCUTS.items():
            self.key_edits[action].setKeySequence(QKeySequence(key))

    def shortcuts(self) -> dict[str, str]:
        return {action: edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
                for action, edit in self.key_edits.items()}

    def conflicts(self) -> list[tuple[str, str, str]]:
        """(key, action, action) of each key given to two actions."""
        seen: dict[str, str] = {}
        out = []
        for action, key in self.shortcuts().items():
            if not key:
                continue
            if key in seen:
                out.append((key, seen[key], action))
            seen[key] = action
        return out

    def accept(self):
        clash = self.conflicts()
        if clash:
            key, a, b = clash[0]
            QMessageBox.warning(self, tr("Shortcuts"), tr("{key} is the shortcut of two actions: {first} and "
                                                          "{second}. Give another to one of them.", key=key,
                                                          first=action_name(a), second=action_name(b)))
            return
        super().accept()

    def settings(self) -> settings.Settings:
        author = " ".join(self.author.text().split())[:200]
        palette = []
        for i, (button, edit) in enumerate(self.palette_rows):
            color, text = button.color, " ".join(edit.text().split())[:200]
            usual_color, _, usual_meaning = settings.PALETTE[i]
            same = color == usual_color and text == (tr(usual_meaning) if usual_meaning else "")
            palette.append((color, None if same else text))
        prefs = dataclasses.replace(self.prefs, author=author, autosave=self.autosave.value(),
                                    palette=tuple(palette), shortcuts=tuple(self.shortcuts().items()))
        if self.reset.isChecked():
            prefs = dataclasses.replace(prefs, styles=settings.DEFAULTS.styles)
        return prefs

