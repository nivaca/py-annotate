"""The main window: the pages of a PDF, the page being annotated with its
annotations, and the list of annotations (searched and filtered) with the
comment of the one selected."""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
import os
import tempfile
from pathlib import Path

import pymupdf
from PySide6.QtCore import QByteArray, QItemSelection, QItemSelectionModel, QPoint, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, annots, config, conform, exchange, interface, recovery, settings
from ..annots import (
    FILLED,
    KINDS,
    MARKUP,
    NAMES,
    STAMPS,
    AnnotateError,
    Annotation,
    PasswordError,
    Rect,
    date_text,
)
from ..interface import N_, ntr, tr
from . import colors
from .canvas import PageCanvas, page_image
from .colors import color_name, swatch, swatches
from .paint import paint
from .prefs import SettingsDialog
from .props import PropertiesDialog
from .renderer import renderer
from .stamps import text_stamp

RECENT = 10  # documents in File ▸ Open recent
AUTHOR = '<a href="https://nicolasvaughan.org">Nicolas Vaughan</a>'
THUMB = QSize(84, 112)  # the largest thumbnail of a page
# the tools: (name, freedesktop icon, tooltip), in groups; besides select, hand and eraser, they are the
# kinds of annotations they make (annots.KINDS)
TOOLS = [
    [("select", "edit-select", N_("Select, move and resize annotations; drag around them to select several")),
     ("hand", "transform-browse", N_("Dragging moves the page in the window")),
     ("eraser", "draw-eraser", N_("Drag over annotations to erase them (over a drawing, only what is touched)"))],
    [("highlight", "draw-highlight", N_("Drag over text to highlight it")),
     ("area", "highlight-area", N_("Drag on the page to highlight a region (a picture, a table, a scanned page)")),
     ("underline", "format-text-underline", N_("Drag over text to underline it")),
     ("strikeout", "format-text-strikethrough", N_("Drag over text to strike it out")),
     ("squiggly", "format-text-underline-squiggle", N_("Drag over text to underline it with a wavy line")),
     ("caret", "insert-text", N_("Click where text should be inserted, and write it"))],
    [("note", "note", N_("Click on the page to add a note")),
     ("freetext", "draw-text", N_("Drag a box on the page (or click) to write a text in it")),
     ("callout", "draw-callout", N_("Press on the place to point at, and drag to where its text goes")),
     ("stamp", "stamp", N_("Click on the page to put a stamp (right-click the tool to choose it)"))],
    [("rect", "draw-rectangle", N_("Drag on the page to draw a rectangle")),
     ("ellipse", "draw-ellipse", N_("Drag on the page to draw an ellipse")),
     ("polygon", "draw-polygon", N_("Click each corner; double-click, or press Enter, to end")),
     ("cloud", "draw-cloud", N_("Drag on the page to draw a cloud")),
     ("line", "draw-line", N_("Drag on the page to draw a line")),
     ("arrow", "draw-arrow", N_("Drag on the page to draw an arrow")),
     ("polyline", "draw-polyline", N_("Click each point; double-click, or press Enter, to end")),
     ("ink", "draw-freehand", N_("Draw on the page by hand"))],
]
TOOL_NAMES = {"select": N_("Select"), "hand": N_("Hand"), "eraser": N_("Eraser")}
SORTS = {"page": N_("By page"), "changed": N_("Last changed first"), "kind": N_("By kind"),
         "author": N_("By author")}
_CLIPBOARD: list[Annotation] = []  # (annotations copied, for all the windows)

_WINDOWS: list = []  # (windows built again in another language must stay referenced)


def install_qt_translations():
    """Qt's own texts (file dialogs, standard buttons) in the language in use."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    app = QApplication.instance()
    for old in getattr(app, "_py_annotate_translators", []):
        app.removeTranslator(old)
    app._py_annotate_translators = []
    code = interface.code()
    QLocale.setDefault(QLocale(code))
    if code == "en":
        return
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for name in ("qtbase", "qt"):
        t = QTranslator(app)
        if t.load(f"{name}_{code}", folder):
            app.installTranslator(t)
            app._py_annotate_translators.append(t)
            break


ACTIONS = Path(__file__).resolve().parent.parent / "icons" / "actions"


def icon(name: str) -> QIcon:
    """The icon NAME (a freedesktop name: document-open...) of the desktop's icon
    theme, so that it looks like the rest of the desktop; or else the program's own."""
    own = ACTIONS / f"{name}.svg"
    return QIcon.fromTheme(name, QIcon(str(own)) if own.is_file() else QIcon())


def tool_name(tool: str) -> str:
    return tr(TOOL_NAMES[tool]) if tool in TOOL_NAMES else tr(NAMES[tool])


class CommentEdit(QPlainTextEdit):
    """The comment of the annotation selected; what is typed is kept when the
    field is left (finished)."""

    finished = Signal()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self, state: dict | None = None):
        """STATE (from export_state) carries the document over when the window is
        built again, for instance in another language."""
        super().__init__()
        self.setAcceptDrops(True)
        self.settings = QSettings("py-annotate", "py-annotate")
        self.path: Path | None = None
        self.password = ""
        self.doc: pymupdf.Document | None = None  # (its pages without the annotations of the list: those are drawn)
        self.count = 0
        self.page = 0  # (0-based) the page shown
        self.annotations: list[Annotation] = []
        self.saved: list[Annotation] = []  # the annotations as they are in the file
        self.undo_stack: list[list[Annotation]] = []
        self.redo_stack: list[list[Annotation]] = []
        self.selected: list[int] = []  # indices in self.annotations
        self.prefs = settings.load()
        colors.set_palette(self.prefs.palette)
        self._have_conform = conform.available(self.prefs.pdfconform)  # (pdf2iso, for PDF/A and PDF/X)
        self._temp: Path | None = None  # the pages without the annotations, on disk, for rendering them elsewhere
        self._thumbs: dict[int, QImage] = {}  # page -> its picture, without the annotations
        self._thumb_shown: dict[int, tuple] = {}  # page -> the annotations its thumbnail shows
        self._by_page: list[list[Annotation]] = []
        self._marked: dict[tuple, str] = {}  # (page, quads) -> the text marked there
        self._rows: list[int] = []  # row of the table -> index of its annotation (those the filters let through)
        self._build()
        self._build_menus()
        self._restore()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.keep_recovery)
        self._start_autosave()
        self.refresh()
        if state:
            self.adopt_state(state)

    # ----------------------------------------------------------------- construction

    def _build(self):
        self.pages = QListWidget()
        self.pages.setViewMode(QListView.ViewMode.IconMode)
        self.pages.setFlow(QListView.Flow.TopToBottom)
        self.pages.setWrapping(False)
        self.pages.setMovement(QListView.Movement.Static)
        self.pages.setIconSize(THUMB)
        self.pages.setGridSize(QSize(THUMB.width() + 28, THUMB.height() + 30))
        self.pages.setUniformItemSizes(True)
        self.pages.setMinimumWidth(THUMB.width() + 50)
        self.pages.setToolTip(tr("The pages; the number after ● is how many annotations a page has"))
        self.pages.currentRowChanged.connect(lambda row: self.show_page(row) if row >= 0 else None)
        self.thumb_timer = QTimer(self, interval=0)
        self.thumb_timer.timeout.connect(self._draw_thumbnails)

        self.canvas = PageCanvas()
        self.canvas.factory = self.new_annotation
        self.canvas.drawn.connect(self.add_drawn)
        self.canvas.edited.connect(self.replace)
        self.canvas.erased.connect(self.erase)
        self.canvas.nudged.connect(self.nudge)
        self.canvas.picked.connect(self.pick)
        self.canvas.text_chosen.connect(self.add_markup)
        self.canvas.double_clicked.connect(self.double_clicked)
        self.canvas.menu_asked.connect(self.annotation_menu)
        self.canvas.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z * 100:.0f} %"))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setPrefix(tr("Page "))
        self.page_spin.valueChanged.connect(lambda v: self.show_page(v - 1))
        self.zoom_label = QLabel("")
        top = QHBoxLayout()
        top.addWidget(self.page_spin)
        top.addStretch(1)
        top.addWidget(self.zoom_label)
        center = QWidget()
        lay = QVBoxLayout(center)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(top)
        lay.addWidget(self.canvas, 1)
        hint = QLabel(tr("Choose a tool in the toolbar: drag over text to mark it, drag on the page to draw, or "
                         "click to add a note. Drag an annotation to move it or resize it; double-click it for its "
                         "properties, right-click it for more. Right-click a tool to set it up."))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(placeholder-text);")
        lay.addWidget(hint)

        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search the annotations…"))
        self.search.setClearButtonEnabled(True)
        self.search.setToolTip(tr("Their comments and texts, the text they mark, their authors and kinds"))
        self.search.textChanged.connect(lambda _: self._filter_changed())
        self.f_kind, self.f_author, self.f_color = QComboBox(), QComboBox(), QComboBox()
        for box, tip in ((self.f_kind, tr("Only annotations of this kind")),
                         (self.f_author, tr("Only annotations by this author")),
                         (self.f_color, tr("Only annotations of this colour"))):
            box.setToolTip(tip)
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(6)
            box.activated.connect(lambda _: self._filter_changed())
        self.sort = QComboBox()
        for key, name in SORTS.items():
            self.sort.addItem(tr(name), key)
        self.sort.activated.connect(lambda _: self._fill_table())
        filters = QHBoxLayout()
        filters.addWidget(self.f_kind, 1)
        filters.addWidget(self.f_author, 1)
        filters.addWidget(self.f_color, 1)
        self.listed = QLabel()
        self.listed.setStyleSheet("color: palette(placeholder-text);")
        sort_row = QHBoxLayout()
        sort_row.addWidget(self.listed, 1)
        sort_row.addWidget(self.sort)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([tr("Page"), tr("Kind"), tr("Author"), tr("Changed"), tr("Text")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._table_selected)
        self.table.itemDoubleClicked.connect(lambda _: self.properties_dialog())

        self.panel_title = QLabel()
        self.panel_title.setWordWrap(True)
        self.color_button = QToolButton()
        self.color_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.color_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.color_button.setMenu(QMenu(self.color_button))
        self.color_button.menu().aboutToShow.connect(self._color_menu)
        self.comment = CommentEdit()
        self.comment.setMinimumHeight(90)
        self.comment.finished.connect(self.keep_comment)
        self.b_props = QPushButton(tr("Properties…"))
        self.b_props.clicked.connect(self.properties_dialog)
        self.b_delete = QPushButton(tr("Delete"))
        self.b_delete.clicked.connect(self.delete_selected)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Colour:")))
        row.addWidget(self.color_button, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.b_props)
        buttons.addWidget(self.b_delete)
        right = QWidget()
        lay = QVBoxLayout(right)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.search)
        lay.addLayout(filters)
        lay.addLayout(sort_row)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.panel_title)
        lay.addLayout(row)
        self.comment_label = QLabel(tr("Comment:"))
        lay.addWidget(self.comment_label)
        lay.addWidget(self.comment)
        lay.addLayout(buttons)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.pages)
        self.splitter.addWidget(center)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([150, 800])
        self.setCentralWidget(self.splitter)
        # the list of the annotations, with their authors, and the one selected: a panel on the right that
        # can be hidden (View, or its close button), moved to the left, or taken out of the window
        self.panel = QDockWidget(tr("Annotations"), self)
        self.panel.setObjectName("annotations")
        self.panel.setWidget(right)
        self.panel.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        right.setMinimumWidth(300)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.panel)
        self.resizeDocks([self.panel], [500], Qt.Orientation.Horizontal)

    def _action(self, menu: QMenu | None, text: str, triggered, shortcut=None, tip: str = "") -> QAction:
        act = QAction(text, self, triggered=triggered)
        if shortcut is not None:
            act.setShortcuts(shortcut if isinstance(shortcut, list) else [QKeySequence(shortcut)])
        if tip:
            act.setToolTip(tip)
            act.setStatusTip(tip)
        if menu is not None:
            menu.addAction(act)
        return act

    def _build_menus(self):
        m = self.menuBar().addMenu(tr("&File"))
        m.setToolTipsVisible(True)
        self.a_open = self._action(m, tr("Open…"), self.open_dialog, QKeySequence.StandardKey.Open)
        self.m_recent = m.addMenu(tr("Open recent"))
        self._recent_menu()
        self.a_save = self._action(m, tr("Save"), self.save, QKeySequence.StandardKey.Save,
                                   tr("Write the annotations in the document"))
        self.a_save_as = self._action(m, tr("Save as…"), self.save_as_dialog, QKeySequence.StandardKey.SaveAs,
                                      tr("Write a copy of the document with the annotations, and go on with it"))
        sub = m.addMenu(tr("Save a copy"))
        sub.setToolTipsVisible(True)
        self.a_flat = self._action(sub, tr("Flattened…"), self.save_flattened_dialog,
                                   tip=tr("The annotations become part of the pages: they are seen and printed "
                                          "everywhere, but can no longer be edited or removed"))
        self.a_bare = self._action(sub, tr("Without annotations…"), self.save_without_dialog,
                                   tip=tr("The document as it is without any annotation (links and form fields "
                                          "stay)"))
        sub.addSeparator()
        self.standard_actions: dict[str, QAction] = {}
        for value, name in conform.STANDARDS:
            act = self._action(sub, tr(name) + "…", lambda _=False, v=value: self.save_standard_dialog(v))
            self.standard_actions[value] = act
        m.addSeparator()
        sub = m.addMenu(tr("Export the annotations"))
        self.a_export_md = self._action(sub, tr("As a report (Markdown)…"), lambda: self.export_dialog("md"))
        self.a_export_csv = self._action(sub, tr("As a table (CSV)…"), lambda: self.export_dialog("csv"))
        self.a_export_json = self._action(sub, tr("As data, to import them again (JSON)…"),
                                          lambda: self.export_dialog("json"))
        sub = m.addMenu(tr("Import annotations"))
        self.a_import_json = self._action(sub, tr("From a file of annotations (JSON)…"),
                                          lambda: self.import_dialog("json"))
        self.a_import_pdf = self._action(sub, tr("From another copy of the PDF…"), lambda: self.import_dialog("pdf"),
                                         tip=tr("Bring in the annotations of another copy of this document, such as "
                                                "one annotated by someone else; those already here are left out"))
        sub.setToolTipsVisible(True)
        m.addSeparator()
        self._action(m, tr("Quit"), self.close, QKeySequence.StandardKey.Quit)

        m = self.menuBar().addMenu(tr("&Edit"))
        self.a_undo = self._action(m, tr("Undo"), self.undo, QKeySequence.StandardKey.Undo)
        self.a_redo = self._action(m, tr("Redo"), self.redo, QKeySequence.StandardKey.Redo)
        m.addSeparator()
        self.a_copy = self._action(m, tr("Copy"), self.copy_selected)
        self.a_paste = self._action(m, tr("Paste"), self.paste)
        self.a_duplicate = self._action(m, tr("Duplicate"), self.duplicate)
        m.addSeparator()
        self.a_props = self._action(m, tr("Properties…"), self.properties_dialog)
        self.a_comment = self._action(m, tr("Comment on the annotation selected"), self.comment_action,
                                      tip=tr("Write the comment of the annotation selected; with none, add a note"))
        self.a_lock = self._action(m, tr("Lock"), self.toggle_lock)
        self.a_delete = self._action(m, tr("Delete the selected annotations"), self.delete_selected,
                                     [QKeySequence(QKeySequence.StandardKey.Delete), QKeySequence("Backspace")])
        m.addSeparator()
        self.a_select_all = self._action(m, tr("Select the annotations of this page"), self.select_page,
                                         QKeySequence.StandardKey.SelectAll)
        self.a_select_kind = self._action(m, tr("Select those of the same kind on this page"), self.select_kind)
        self._action(m, tr("Select none"), lambda: self.pick([], False), "Escape")
        self.m_align = m.addMenu(tr("Align"))
        for key, name in (("left", N_("Left sides")), ("hcenter", N_("Centres, across")),
                          ("right", N_("Right sides")), ("top", N_("Tops")), ("vcenter", N_("Middles, up and down")),
                          ("bottom", N_("Bottoms")), ("", ""), ("across", N_("Spread evenly across")),
                          ("down", N_("Spread evenly up and down")), ("size", N_("Make them the same size"))):
            if key:
                self._action(self.m_align, tr(name), lambda _=False, k=key: self.align(k))
            else:
                self.m_align.addSeparator()
        m.addSeparator()
        self.a_clear_page = self._action(m, tr("Delete the annotations of this page"), self.delete_page)
        self.a_clear_all = self._action(m, tr("Delete all the annotations"), self.delete_all)
        m.aboutToShow.connect(self._edit_menu)

        m = self.menuBar().addMenu(tr("&Tools"))
        m.setToolTipsVisible(True)
        group = QActionGroup(self)
        self.tool_actions: dict[str, QAction] = {}
        for tools in TOOLS:
            for tool, icon_name, tip in tools:
                act = self._action(m, tool_name(tool), lambda _=False, t=tool: self.set_tool(t), tip=tr(tip))
                act.setCheckable(True)
                act.setIcon(icon(icon_name))
                group.addAction(act)
                self.tool_actions[tool] = act
            m.addSeparator()
        self.tool_actions["select"].setChecked(True)
        self._action(m, tr("Properties of the tool…"), lambda: self.tool_dialog(self.canvas.mode))

        m = self.menuBar().addMenu(tr("&View"))
        self.a_show = QAction(tr("Show the annotations"), self, checkable=True, checked=True)
        self.a_show.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.a_show.setToolTip(tr("Hide them to see the document as it is without them"))
        self.a_show.toggled.connect(lambda _: self.refresh(table=False))
        m.addAction(self.a_show)
        self.a_only_listed = QAction(tr("Only those the list shows"), self, checkable=True)
        self.a_only_listed.setToolTip(tr("On the page, only the annotations that the search and filters of the list "
                                         "let through"))
        self.a_only_listed.toggled.connect(lambda _: self.refresh(table=False))
        m.addAction(self.a_only_listed)
        self.a_panel = self.panel.toggleViewAction()
        self.a_panel.setText(tr("The panel of the annotations"))
        self.a_panel.setShortcut(QKeySequence("F4"))
        self.a_panel.setToolTip(tr("The list of the annotations, with their authors, on the right of the window"))
        m.addAction(self.a_panel)
        m.addSeparator()
        self.a_next_annot = self._action(m, tr("Next annotation"), lambda: self.go_annotation(1))
        self.a_prev_annot = self._action(m, tr("Previous annotation"), lambda: self.go_annotation(-1))
        m.addSeparator()
        self.a_prev = self._action(m, tr("Previous page"), lambda: self.show_page(self.page - 1),
                                   [QKeySequence("PgUp")])
        self.a_next = self._action(m, tr("Next page"), lambda: self.show_page(self.page + 1),
                                   [QKeySequence("PgDown")])
        self.a_first = self._action(m, tr("First page"), lambda: self.show_page(0), "Ctrl+Home")
        self.a_last = self._action(m, tr("Last page"), lambda: self.show_page(self.count - 1), "Ctrl+End")
        m.addSeparator()
        self.a_fit = self._action(m, tr("Fit the page"), lambda: self._fit("page"), "Ctrl+0")
        self.a_fit_width = self._action(m, tr("Fit the width"), lambda: self._fit("width"), "Ctrl+9")
        self.a_zoom_in = self._action(m, tr("Zoom in"), lambda: self.canvas.zoom_by(1.25),
                                      [QKeySequence(QKeySequence.StandardKey.ZoomIn), QKeySequence("Ctrl+=")])
        self.a_zoom_out = self._action(m, tr("Zoom out"), lambda: self.canvas.zoom_by(1 / 1.25),
                                       QKeySequence.StandardKey.ZoomOut)

        m = self.menuBar().addMenu(tr("&Settings"))
        self._action(m, tr("Settings…"), self.settings_dialog, [QKeySequence("Ctrl+,")])
        self.a_labels = QAction(tr("Labels in the toolbar"), self, checkable=True)
        self.a_labels.toggled.connect(self.show_labels)
        m.addAction(self.a_labels)
        lang = m.addMenu(tr("Language"))
        group = QActionGroup(self)
        for code, name in interface.names().items():
            act = QAction(name, self, checkable=True)
            act.setChecked(code == interface.code())
            act.triggered.connect(lambda _=False, c=code: self.change_language(c))
            group.addAction(act)
            lang.addAction(act)
        m = self.menuBar().addMenu(tr("&Help"))
        self._action(m, tr("About"), self.about)

        for act, name in ((self.a_open, "document-open"), (self.a_save, "document-save"),
                          (self.a_save_as, "document-save-as"), (self.a_undo, "edit-undo"),
                          (self.a_redo, "edit-redo"), (self.a_delete, "edit-delete"), (self.a_prev, "go-previous"),
                          (self.a_next, "go-next"), (self.a_fit, "zoom-fit-best"),
                          (self.a_fit_width, "zoom-fit-width"), (self.a_zoom_out, "zoom-out"),
                          (self.a_zoom_in, "zoom-in"), (self.a_copy, "edit-copy"), (self.a_paste, "edit-paste")):
            act.setIcon(icon(name))
        bar = QToolBar(tr("Document"))
        self.toolbar = bar
        bar.setObjectName("document")
        bar.setIconSize(QSize(22, 22))
        for act in (self.a_open, self.a_save, None, self.a_undo, self.a_redo, self.a_delete, None, self.a_prev,
                    self.a_next, None, self.a_fit, self.a_fit_width, self.a_zoom_out, self.a_zoom_in):
            if act is None:
                bar.addSeparator()
            else:
                bar.addAction(act)
        self.addToolBar(bar)
        tools = QToolBar(tr("Tools"))
        self.tools_bar = tools
        tools.setObjectName("tools")
        tools.setIconSize(QSize(22, 22))
        for i, group_ in enumerate(TOOLS):
            if i:
                tools.addSeparator()
            for tool, _, _ in group_:
                tools.addAction(self.tool_actions[tool])
                button = tools.widgetForAction(self.tool_actions[tool])
                button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                button.customContextMenuRequested.connect(
                    lambda pos, t=tool, b=button: self.tool_menu(t, b.mapToGlobal(pos)))
        self.addToolBarBreak()
        self.addToolBar(tools)
        self.apply_shortcuts()
        self.show_labels(self.settings.value("toolbar_labels", "false") == "true")

    def apply_shortcuts(self):
        """The keys of the settings, given to the actions."""
        actions = dict(self.tool_actions)
        actions.update({"comment": self.a_comment, "next": self.a_next_annot, "previous": self.a_prev_annot,
                        "copy": self.a_copy, "paste": self.a_paste, "duplicate": self.a_duplicate,
                        "properties": self.a_props})
        for name, act in actions.items():
            act.setShortcut(QKeySequence(self.prefs.shortcut(name)))
        self._toolbar_tips()

    # ----------------------------------------------------------------- settings

    def _restore(self):
        geo = self.settings.value("geometry")
        if isinstance(geo, QByteArray):
            self.restoreGeometry(geo)
        else:
            self.resize(1360, 900)
        split = self.settings.value("splitter2")
        if isinstance(split, QByteArray):
            self.splitter.restoreState(split)
        bars = self.settings.value("toolbars")
        if isinstance(bars, QByteArray):
            self.restoreState(bars)

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter2", self.splitter.saveState())
        self.settings.setValue("toolbars", self.saveState())
        self.settings.sync()

    def closeEvent(self, event):
        self.keep_comment()
        if not self.maybe_discard():
            event.ignore()
            return
        if self.path is not None:
            recovery.discard(self.path)
        self.save_settings()
        self._drop_temp()
        super().closeEvent(event)

    def export_state(self) -> dict:
        """What a new window needs to carry on with the same document."""
        self.keep_comment()
        return {"path": self.path, "password": self.password, "annotations": self.annotations,
                "saved": self.saved, "undo": self.undo_stack, "redo": self.redo_stack, "page": self.page,
                "tool": self.canvas.mode}

    def adopt_state(self, state: dict):
        self.set_tool(state["tool"])
        if state["path"] is None or self._load(state["path"], state["password"]) is None:
            self.refresh()
            return
        self.annotations, self.saved = list(state["annotations"]), list(state["saved"])
        self.undo_stack, self.redo_stack = list(state["undo"]), list(state["redo"])
        self.refresh()
        self.show_page(state["page"])

    def last_dir(self) -> str:
        return self.settings.value("last_dir", str(Path.home()))

    # ----------------------------------------------------------------- language

    def change_language(self, code: str):
        """Use CODE for the interface, keep it in the configuration file, and
        build the window again in that language."""
        if code == interface.code():
            return
        if not interface.use(code):
            self.warn(tr("Language"), tr("The language of the interface could not be changed: {error}",
                                         error=interface.error()))
            interface.use(config.get("interface"))
            return
        try:
            config.set("interface", code)
        except OSError as e:
            self.status(tr("Could not keep the setting: {error}", error=e), error=True)
        install_qt_translations()
        self.save_settings()
        new = MainWindow(self.export_state())
        new.restoreGeometry(self.saveGeometry())
        new.show()
        _WINDOWS.append(new)
        self.annotations = self.saved = []  # (nothing to ask about: the new window has it)
        self.path = None  # (nor a recovery copy to remove: it is the new window's)
        self._temp = None  # (the new window uses it, if there is one)
        self.hide()
        self.deleteLater()
        if self in _WINDOWS:
            _WINDOWS.remove(self)

    # ----------------------------------------------------------------- documents

    def open_dialog(self):
        name, _ = QFileDialog.getOpenFileName(self, tr("Open PDF"), self.last_dir(), tr("PDF files (*.pdf)"))
        if name:
            self.open_path(Path(name))

    def open_path(self, path: Path) -> bool:
        self.keep_comment()
        if not path.is_file():
            self.status(tr("{path} not found", path=path), error=True)
            return False
        if not self.maybe_discard():
            return False
        if self.path is not None:
            recovery.discard(self.path)
        password = ""
        while True:
            try:
                annots.open_pdf(path, password).close()
                break
            except PasswordError:
                password = self.ask_password(path, again=bool(password))
                if password is None:
                    self.status(tr("{path} is protected by a password", path=path), error=True)
                    return False
            except AnnotateError as e:
                self.status(str(e), error=True)
                return False
        found = self._load(path, password)
        if found is None:
            return False
        self.settings.setValue("last_dir", str(path.parent))
        self.add_recent(path)
        self.annotations, self.saved = list(found), list(found)
        self.undo_stack, self.redo_stack, self.selected = [], [], []
        self.search.clear()
        self.refresh()
        self.show_page(0)
        self.status(tr("Opened {path}", path=path) + " (" + ntr("{count} page", "{count} pages", self.count) + ", "
                    + ntr("{count} annotation", "{count} annotations", len(found)) + ")")
        kept = recovery.find(path)
        if kept is not None and kept[1] != found:
            when, annotations = kept
            if self.ask_recover(when.replace("T", " ")[:16]):
                self.change([a for a in annotations if 0 <= a.page < self.count], [])
                self.status(tr("The annotations not saved before were brought back"))
            else:
                recovery.discard(path)
        return True

    def ask_recover(self, when: str) -> bool:
        return QMessageBox.question(
            self, tr("Annotations not saved"),
            tr("This document has annotations that were not saved, kept at {when} (the program stopped before they "
               "were saved). Bring them back?", when=when)) == QMessageBox.StandardButton.Yes

    def ask_password(self, path: Path, again: bool = False) -> str | None:
        text = tr("That password is not right. The password of {name}:", name=path.name) if again \
            else tr("{name} is protected. Its password:", name=path.name)
        password, ok = QInputDialog.getText(self, tr("Password"), text, QLineEdit.EchoMode.Password)
        return password if ok and password else None

    def _load(self, path: Path, password: str) -> list[Annotation] | None:
        """Open PATH: its pages are shown without the annotations that can be
        edited, which are returned (None if it can't be opened)."""
        try:
            doc = annots.open_pdf(path, password)
            found = annots.read(doc)
            annots.remove_editable(doc)
        except (AnnotateError, RuntimeError, ValueError) as e:
            self.status(str(e), error=True)
            return None
        self._close_doc()
        self.doc, self.path, self.password, self.count = doc, path, password, doc.page_count
        self.page = 0
        self._thumbs, self._thumb_shown, self._marked = {}, {}, {}
        self._by_page = [[] for _ in range(self.count)]
        self.canvas.clear_cache()
        self.canvas.source = self._source(doc, path, password, bool(found))
        self._fill_pages()
        return found

    def _source(self, doc: pymupdf.Document, path: Path, password: str, changed: bool):
        """What the other processes render the pages from (see renderer.py): the
        file itself; or, if annotations were taken out of the pages, a copy
        without them (not for a document with a password, which would be
        written there without it: its pages are rendered here)."""
        try:
            if not changed:
                st = path.stat()
                return str(path.resolve()), password, (st.st_mtime_ns, st.st_size)
            if password:
                return None
            fd, name = tempfile.mkstemp(prefix="py-annotate-", suffix=".pdf")
            with os.fdopen(fd, "wb") as f:
                f.write(doc.tobytes())
            self._temp = Path(name)
            st = self._temp.stat()
            return name, "", (st.st_mtime_ns, st.st_size)
        except (OSError, RuntimeError, ValueError):
            return None

    def _drop_temp(self):
        if self._temp is not None:
            self._temp.unlink(missing_ok=True)
            self._temp = None

    def _close_doc(self):
        """Close the document shown (its pages are no longer shown)."""
        self.thumb_timer.stop()
        self.canvas.show_page(None, [], [])
        self.canvas.clear_cache()
        if self.doc is not None:
            self.doc.close()
            self.doc = None
        self._drop_temp()

    def _ask_target(self, title: str, suffix: str, ext: str = "pdf") -> Path | None:
        default = Path(self.last_dir()) / f"{self.path.stem}{suffix}.{ext}"
        filters = {"pdf": tr("PDF files (*.pdf)"), "json": tr("Annotations (*.json)"),
                   "md": tr("Markdown (*.md)"), "csv": tr("Tables (*.csv)")}
        name, _ = QFileDialog.getSaveFileName(self, title, str(default), filters[ext])
        if not name:
            return None
        target = Path(name)
        return target if target.suffix.lower() == f".{ext}" else target.with_suffix(f".{ext}")

    def save(self) -> bool:
        if self.path is None:
            return False
        return self.save_to(self.path)

    def save_as_dialog(self) -> bool:
        if self.path is None:
            return False
        target = self._ask_target(tr("Save as"), "-annotated")
        return self.save_to(target) if target is not None else False

    def save_to(self, target: Path) -> bool:
        """Write the document with the annotations as TARGET (which may be the
        document itself), and go on with TARGET."""
        self.keep_comment()
        source, page = self.path, self.page
        replacing = target.resolve() == source.resolve()
        if replacing:  # (the file is about to change under the open document)
            self._close_doc()
        try:
            written = annots.write(source, self.annotations, target, self.password)
        except AnnotateError as e:
            if replacing:
                self._load(source, self.password)
                self.refresh()
                self.show_page(page)
            self.status(str(e), error=True)
            return False
        recovery.discard(source)
        found = self._load(target, self.password)
        if found is None:
            return False
        # (the annotations as they are in the file now, with their xrefs: the undo history had others)
        self.annotations, self.saved = list(found), list(found)
        self.undo_stack, self.redo_stack, self.selected = [], [], []
        self.settings.setValue("last_dir", str(target.parent))
        self.add_recent(target)
        self.refresh()
        self.show_page(page)
        self.status(tr("Saved {path}", path=target) + " — "
                    + ntr("{count} annotation written", "{count} annotations written", written))
        return True

    def _same_file(self, target: Path) -> bool:
        if target.resolve() == self.path.resolve():
            self.status(tr("Choose another name: the document stays open"), error=True)
            return True
        return False

    def save_flattened_dialog(self) -> bool:
        if self.path is None:
            return False
        target = self._ask_target(tr("Save a flattened copy"), "-flattened")
        if target is None or self._same_file(target):
            return False
        self.keep_comment()
        try:
            exchange.save_flattened(self.path, self.annotations, target, self.password)
        except AnnotateError as e:
            self.status(str(e), error=True)
            return False
        self.status(tr("Saved {path}, with the annotations made part of the pages", path=target))
        return True

    def save_without_dialog(self) -> bool:
        if self.path is None:
            return False
        target = self._ask_target(tr("Save a copy without annotations"), "-clean")
        if target is None or self._same_file(target):
            return False
        try:
            count = exchange.save_without(self.path, target, self.password)
        except AnnotateError as e:
            self.status(str(e), error=True)
            return False
        self.status(tr("Saved {path}", path=target) + " — "
                    + ntr("{count} annotation taken out", "{count} annotations taken out", count))
        return True

    def save_standard_dialog(self, standard: str) -> bool:
        """Save a copy with the annotations as STANDARD ('a-2b', 'x-4'...), made by pdf2iso."""
        if self.path is None:
            return False
        if not conform.available():
            self.warn(conform.label(standard), tr("{command} is not installed (or not where Settings say)",
                                                  command=conform.COMMAND))
            return False
        target = self._ask_target(tr("Save a copy as {standard}", standard=conform.label(standard)),
                                  "-pdfx" if standard.startswith("x") else "-pdfa")
        if target is None or self._same_file(target):
            return False
        return self.save_standard(target, standard)

    def save_standard(self, target: Path, standard: str, flatten: set[str] = frozenset()) -> bool:
        """Write TARGET: a copy with the annotations (those of the kinds FLATTEN, made part of the
        pages), made STANDARD by pdf2iso. If Ghostscript leaves out annotations of some kinds,
        offer to do it again with those flattened."""
        self.keep_comment()
        fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
        os.close(fd)
        tmp = Path(tmp)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.status(tr("Making {standard} with {command}…", standard=conform.label(standard),
                       command=conform.COMMAND))
        QApplication.processEvents()
        try:
            if flatten:
                exchange.save_partly_flattened(self.path, self.annotations, tmp, self.password, set(flatten))
            else:
                annots.write(self.path, self.annotations, tmp, self.password)
            check = conform.convert(tmp, target, standard, self.password)
            kept = [a for a in self.annotations if a.kind not in flatten]
            lost = exchange.kinds_lost(kept, target)
        except (AnnotateError, conform.ConformError) as e:
            QApplication.restoreOverrideCursor()
            self.status("", error=False)
            self.warn(conform.label(standard), tr("The copy could not be made {standard}:\n\n{error}",
                                                  standard=conform.label(standard), error=e))
            return False
        finally:
            tmp.unlink(missing_ok=True)
        QApplication.restoreOverrideCursor()
        if lost:
            names = ", ".join(f"{tool_name(kind).lower()} ({count})" for kind, count in lost.items())
            if self.ask_flatten_lost(conform.label(standard), names):
                kinds = set(lost) | ({"cloud"} if "polygon" in lost else set())
                return self.save_standard(target, standard, set(flatten) | kinds)
        message = tr("Saved {path} as {standard}", path=target, standard=conform.label(standard))
        if check:
            message += f" ({check})"
        if flatten:
            message += " — " + tr("some annotations were made part of the pages")
        elif lost:
            message += " — " + ntr("{count} annotation was left out", "{count} annotations were left out",
                                   sum(lost.values()))
        if self.password:
            message += " — " + tr("PDF/A and PDF/X can't be protected: the copy has no password")
        self.status(message)
        return True

    def ask_flatten_lost(self, standard: str, names: str) -> bool:
        """Whether to make part of the pages the annotations (NAMES: their kinds and how many) that
        Ghostscript could not keep in STANDARD."""
        box = QMessageBox(QMessageBox.Icon.Warning, standard,
                          tr("Ghostscript could not keep these annotations in {standard}, and left them out: "
                             "{kinds}.\n\nThey can be made part of the pages instead: they will be seen and "
                             "printed, but no longer edited. The other annotations stay as they are.",
                             standard=standard, kinds=names), QMessageBox.StandardButton.NoButton, self)
        flatten = box.addButton(tr("Make them part of the pages"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Leave them out"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(flatten)
        box.exec()
        return box.clickedButton() is flatten

    def export_dialog(self, kind: str) -> bool:
        """Export the annotations the list shows (all, if nothing is filtered) as KIND: 'json', 'md' or 'csv'."""
        if self.doc is None:
            return False
        self.keep_comment()
        chosen = [self.annotations[i] for i in self._rows]
        if not chosen:
            self.status(tr("There are no annotations to export"), error=True)
            return False
        target = self._ask_target(tr("Export the annotations"), "-annotations", kind)
        if target is None:
            return False
        try:
            if kind == "json":
                exchange.export_json(self.doc, self.path, chosen, target)
            elif kind == "csv":
                exchange.export_csv(self.doc, chosen, target, colors.color_meaning)
            else:
                exchange.export_markdown(self.doc, self.path, chosen, target, color_name)
        except OSError as e:
            self.status(tr("{path} cannot be written: {error}", path=target, error=e), error=True)
            return False
        self.status(ntr("{count} annotation exported to {path}", "{count} annotations exported to {path}",
                        len(chosen), path=target))
        return True

    def import_dialog(self, kind: str) -> bool:
        """Bring in annotations from a JSON file (KIND 'json') or another PDF ('pdf')."""
        if self.doc is None:
            return False
        title = tr("Import annotations")
        filters = tr("Annotations (*.json)") if kind == "json" else tr("PDF files (*.pdf)")
        name, _ = QFileDialog.getOpenFileName(self, title, self.last_dir(), filters)
        if not name:
            return False
        return self.import_from(Path(name), kind)

    def import_from(self, source: Path, kind: str) -> bool:
        try:
            if kind == "json":
                found = exchange.import_json(source)
            else:
                password = ""
                while True:
                    try:
                        found = exchange.import_pdf(source, password)
                        break
                    except PasswordError:
                        password = self.ask_password(source, again=bool(password))
                        if password is None:
                            raise
        except AnnotateError as e:
            self.status(str(e), error=True)
            return False
        found = [a for a in found if 0 <= a.page < self.count]
        new = exchange.merged(self.annotations, found)
        if new:
            self.change(self.annotations + new, list(range(len(self.annotations), len(self.annotations) + len(new))))
        self.status(ntr("{count} annotation imported", "{count} annotations imported", len(new))
                    + (" — " + ntr("{count} was here already", "{count} were here already", len(found) - len(new))
                       if len(found) > len(new) else ""))
        return True

    # ----------------------------------------------------------------- recovery copies

    def _start_autosave(self):
        minutes = self.prefs.autosave
        if minutes:
            self.autosave_timer.start(minutes * 60_000)
        else:
            self.autosave_timer.stop()

    def keep_recovery(self):
        """Keep a recovery copy of the annotations, if they have changed since the document was saved."""
        if self.path is None or not self.is_modified():
            return
        try:
            recovery.keep(self.path, self.annotations)
        except OSError as e:
            self.status(tr("The recovery copy could not be kept: {error}", error=e), error=True)

    # ----------------------------------------------------------------- the toolbar

    def show_labels(self, on: bool):
        """Icons with their names under them in the toolbars, or (by default) only icons."""
        for bar in (self.toolbar, self.tools_bar):
            bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon if on
                                   else Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.a_labels.blockSignals(True)
        self.a_labels.setChecked(on)
        self.a_labels.blockSignals(False)
        self.settings.setValue("toolbar_labels", "true" if on else "false")

    def _toolbar_tips(self):
        """The tooltip of each button of the toolbars: what it does, and its shortcut."""
        for bar in (self.toolbar, getattr(self, "tools_bar", None)):
            if bar is None:
                continue
            for act in bar.actions():
                if act.isSeparator():
                    continue
                text = act.text().replace("&&", "\0").replace("&", "").replace("\0", "&")
                keys = act.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
                tip = f"<b>{text}</b>" + (f" &nbsp;<span style='color:gray'>{keys}</span>" if keys else "")
                if act.statusTip():
                    tip += f"<br>{act.statusTip()}"
                for button in bar.findChildren(QToolButton):
                    if button.defaultAction() is act:
                        button.setToolTip(tip)

    def tool_menu(self, tool: str, where):
        """The menu of a tool (right-click on its button): its colour, its stamp, its properties."""
        menu = QMenu(self)
        menu.addSection(tool_name(tool))
        if tool in KINDS:
            style = self.prefs.style(tool)
            for value, name in swatches():
                act = menu.addAction(swatch(value), name, lambda v=value: self.set_tool_color(tool, v))
                act.setCheckable(True)
                act.setChecked(value == style.color)
            menu.addAction(tr("Other colour…"), lambda: self.choose_tool_color(tool))
            if tool == "stamp":
                menu.addSeparator()
                stamps = menu.addMenu(tr("Stamp"))
                for key, name in STAMPS.items():
                    act = stamps.addAction(tr(name), lambda k=key: self.set_stamp(k))
                    act.setCheckable(True)
                    act.setChecked(style.stamp == key)
                custom = style.stamp[5:] if style.stamp.startswith("text:") else ""
                act = menu.addAction(tr("A stamp of my own ({text})…", text=custom) if custom
                                     else tr("A stamp of my own…"), self.ask_stamp)
                act.setCheckable(True)
                act.setChecked(bool(custom))
            menu.addSeparator()
            menu.addAction(tr("Properties of the tool…"), lambda: self.tool_dialog(tool))
        self.set_tool(tool)
        self.show_menu(menu, where)

    def set_tool_color(self, tool: str, color: str):
        self.set_prefs(self.prefs.with_style(tool, dataclasses.replace(self.prefs.style(tool), color=color)))
        self.status(tr("New annotations ({kind}) will be {color}", kind=tool_name(tool).lower(),
                       color=color_name(color)))

    def choose_tool_color(self, tool: str):
        chosen = QColorDialog.getColor(QColor(self.prefs.style(tool).color), self, tr("Colour"))
        if chosen.isValid():
            self.set_tool_color(tool, chosen.name())

    def set_stamp(self, stamp: str):
        self.set_prefs(self.prefs.with_style("stamp", dataclasses.replace(self.prefs.style("stamp"), stamp=stamp)))
        self.set_tool("stamp")

    def ask_stamp(self):
        current = self.prefs.style("stamp").stamp
        text, ok = QInputDialog.getText(self, tr("A stamp of my own"), tr("What the stamp says:"),
                                        QLineEdit.EchoMode.Normal, current[5:] if current.startswith("text:") else "")
        text = " ".join(text.split())[:60]
        if ok and text:
            self.set_stamp("text:" + text)

    def tool_dialog(self, tool: str):
        """The properties of TOOL: how the annotations it makes look, and how it behaves."""
        if tool not in KINDS:
            return
        style = self.prefs.style(tool)
        dialog = PropertiesDialog([self.new_annotation(tool, 0, (0, 0, 10, 10))], self, tool=style)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_prefs(self.prefs.with_style(tool, dialog.style()))

    # ----------------------------------------------------------------- recent files

    def recent_files(self) -> list[Path]:
        try:
            names = json.loads(self.settings.value("recent", "[]"))
        except (TypeError, ValueError):
            names = []
        return [Path(n) for n in names if isinstance(n, str)][:RECENT]

    def _set_recent(self, paths: list[Path]):
        self.settings.setValue("recent", json.dumps([str(p) for p in paths[:RECENT]]))
        self._recent_menu()

    def add_recent(self, path: Path):
        path = path.resolve()
        self._set_recent([path] + [p for p in self.recent_files() if p != path])

    def clear_recent(self):
        self._set_recent([])

    def _recent_menu(self):
        m = self.m_recent
        m.clear()
        paths = self.recent_files()
        for i, path in enumerate(paths, 1):
            key = f"&{i}" if i < 10 else "1&0"
            act = m.addAction(f"{key} " + path.name.replace("&", "&&"), lambda p=path: self.open_path(p))
            act.setToolTip(str(path))
            act.setStatusTip(str(path))
        if paths:
            m.addSeparator()
        m.addAction(tr("Clear the list"), self.clear_recent).setEnabled(bool(paths))
        m.setToolTipsVisible(True)

    # ----------------------------------------------------------------- changing the annotations

    def change(self, annotations: list[Annotation], selected: list[int] | None = None):
        """Make ANNOTATIONS the annotations (so that it can be undone), selecting SELECTED."""
        if annotations == self.annotations:
            return
        self.undo_stack.append(self.annotations)
        self.redo_stack.clear()
        self.annotations = annotations
        self.selected = [i for i in (selected or []) if i < len(annotations)]
        self.refresh()

    def new_annotation(self, kind: str, page: int, rect: Rect, paths: tuple = (), quads: tuple = ()) -> Annotation:
        """An annotation with the style of new ones of its KIND (Settings, or Properties); a
        stamp, of its usual size where RECT has none."""
        style = self.prefs.style(kind)
        a = Annotation(kind, page, rect, style.color, fill=style.fill if kind in FILLED else "",
                       opacity=style.opacity, width=style.width, author=self.prefs.author,
                       font_size=style.font_size, font=style.font, align=style.align, icon=style.icon,
                       ends=(style.start, style.end), dashed=style.dashed, quads=quads, paths=paths)
        if kind == "stamp":
            a = self._stamp(a, style)
        return a

    def _stamp(self, a: Annotation, style: settings.Style) -> Annotation:
        if style.stamp.startswith("text:"):
            text = style.stamp[5:]
            image, (w, h) = text_stamp(text, style.color, self.prefs.author if style.stamp_date else "",
                                       style.stamp_date)
            a = dataclasses.replace(a, stamp="", image=image, contents=text)
        else:
            name = style.stamp if style.stamp in STAMPS else "Approved"
            image, (w, h) = annots.standard_stamp(name)
            a = dataclasses.replace(a, stamp=name, image=image, contents=tr(STAMPS[name]))
        x0, y0, x1, _ = a.rect
        if x1 - x0 > 5:  # (dragged: as wide as that, with its proportions)
            h, w = h * (x1 - x0) / w, x1 - x0
        else:  # (clicked: centred there)
            x0, y0 = x0 - w / 2, y0 - h / 2
        if self.doc is not None and 0 <= a.page < self.count:
            r = self.doc[a.page].rect
            x0, y0 = max(min(x0, r.width - w), 0), max(min(y0, r.height - h), 0)
        return dataclasses.replace(a, rect=(round(x0, 2), round(y0, 2), round(x0 + w, 2), round(y0 + h, 2)))

    def add(self, annotation: Annotation):
        self.change(self.annotations + [annotation], [len(self.annotations)])
        self._after_making(annotation.kind)

    def _after_making(self, kind: str):
        """What the tool does once it has made an annotation: open something, and go back to Select."""
        style = self.prefs.style(kind)
        if style.show == "properties":
            self.properties_dialog()
        elif style.show == "comment" or (style.show == "text" and kind in MARKUP):
            self.comment.setFocus()
        if not style.sticky and self.canvas.mode == kind:
            self.set_tool("select")

    def add_drawn(self, annotation: Annotation):
        """An annotation drawn on the page; a note or a text box asks for its text first, if its tool says so."""
        if annotation.kind in ("note", "freetext", "callout", "caret") \
                and self.prefs.style(annotation.kind).show == "text":
            text = self.ask_text(annotation)
            if text is None or (annotation.kind in ("freetext", "callout") and not text.strip()):
                return
            annotation = dataclasses.replace(annotation, contents=text)
        self.add(annotation)

    def ask_text(self, annotation: Annotation) -> str | None:
        """The text of a new note, text box or caret (None if the user gives up)."""
        title, label = {
            "note": (tr("New note"), tr("The text of the note:")),
            "caret": (tr("Insert text"), tr("The text to insert:")),
        }.get(annotation.kind, (tr("New text box"), tr("The text to write on the page:")))
        text, ok = QInputDialog.getMultiLineText(self, title, label, "")
        return text.strip("\n") if ok else None

    def add_markup(self, rects: list[Rect], kind: str | None = None):
        """A highlight (or the kind of markup of the tool) over the lines of text RECTS."""
        kind = kind or (self.canvas.mode if self.canvas.mode in MARKUP else "highlight")
        self.add(self.new_annotation(kind, self.page, annots.union(rects), quads=tuple(rects)))

    def double_clicked(self, index: int, point: tuple):
        """An annotation: its properties. A word, with a markup tool: that word marked."""
        if index >= 0:
            self.properties_dialog()
            return
        if self.canvas.mode not in MARKUP or self.doc is None:
            return
        found = annots.words(self.doc[self.page])
        i = annots.nearest_word(found, *point)
        if i is not None:
            x0, y0, x1, y1 = found[i][0]
            if x0 - 2 <= point[0] <= x1 + 2 and y0 - 2 <= point[1] <= y1 + 2:
                self.add_markup(annots.text_rects(found, i, i))

    def set_tool(self, tool: str):
        self.canvas.set_mode(tool)
        self.tool_actions[tool].setChecked(True)
        self._show_panel()
        if tool in ("polygon", "polyline"):
            self.status(tr("Click each point; double-click, press Enter or click the first point to end; Escape "
                           "gives it up"))

    def replace(self, index: int, annotation: Annotation):
        """ANNOTATION in the place of the one at INDEX (moved, resized...)."""
        annotations = list(self.annotations)
        annotations[index] = annotation
        self.change(annotations, self.selected if index in self.selected else [index])

    def erase(self, changes: dict):
        """What the eraser did: {index: the annotation as it is left, or None if it is gone}."""
        annotations = []
        for i, a in enumerate(self.annotations):
            if i not in changes:
                annotations.append(a)
            elif changes[i] is not None:
                annotations.append(changes[i])
        self.change(annotations, [])

    def _movable(self) -> list[int]:
        return [i for i in self.selected if self.annotations[i].kind not in MARKUP and not self.annotations[i].locked]

    def nudge(self, dx: float, dy: float):
        """The selected annotations moved by (DX, DY) points, kept on the page."""
        chosen = self._movable()
        if not chosen or self.doc is None:
            return
        page = self.doc[self.page].rect
        annotations = list(self.annotations)
        for i in chosen:
            a = annotations[i]
            x0, y0, x1, y1 = a.rect
            mx = max(-x0, min(dx, page.width - x1))
            my = max(-y0, min(dy, page.height - y1))
            annotations[i] = annots.moved(a, mx, my)
        self.change(annotations, self.selected)

    def align(self, how: str):
        """Line up the selected annotations (that can be moved): see the Align menu."""
        chosen = self._movable()
        if len(chosen) < 2 or (how in ("across", "down") and len(chosen) < 3):
            self.status(tr("Select at least two annotations that can be moved (three, to spread them)"), error=True)
            return
        rects = {i: self.annotations[i].rect for i in chosen}
        annotations = list(self.annotations)
        if how in ("across", "down"):
            axis = 0 if how == "across" else 1
            order = sorted(chosen, key=lambda i: rects[i][axis])
            first, last = rects[order[0]], rects[order[-1]]
            sizes = sum(rects[i][axis + 2] - rects[i][axis] for i in order)
            gap = (last[axis + 2] - first[axis] - sizes) / (len(order) - 1)
            at = first[axis]
            for i in order:
                r = rects[i]
                shift = at - r[axis]
                annotations[i] = annots.moved(annotations[i], shift if axis == 0 else 0, shift if axis == 1 else 0)
                at += r[axis + 2] - r[axis] + gap
        else:
            ref = rects[self.selected[0]] if self.selected[0] in rects else rects[chosen[0]]
            for i in chosen:
                x0, y0, x1, y1 = rects[i]
                w, h = x1 - x0, y1 - y0
                if how == "size":
                    if self.annotations[i].kind in annots.RESIZABLE:
                        annotations[i] = annots.fitted(annotations[i], (x0, y0, x0 + ref[2] - ref[0],
                                                                         y0 + ref[3] - ref[1]))
                    continue
                dx = {"left": ref[0] - x0, "right": ref[2] - x1,
                      "hcenter": (ref[0] + ref[2]) / 2 - (x0 + w / 2)}.get(how, 0)
                dy = {"top": ref[1] - y0, "bottom": ref[3] - y1,
                      "vcenter": (ref[1] + ref[3]) / 2 - (y0 + h / 2)}.get(how, 0)
                annotations[i] = annots.moved(annotations[i], dx, dy)
        self.change(annotations, self.selected)

    def _change_selected(self, **changes):
        annotations = list(self.annotations)
        for i in self.selected:
            fields = {k: v for k, v in changes.items() if k != "fill" or annotations[i].kind in FILLED}
            annotations[i] = dataclasses.replace(annotations[i], **fields)
        self.change(annotations, self.selected)

    def _remove(self, keep) -> None:
        """Remove the annotations for which KEEP(annotation) is false (locked ones are always kept)."""
        annotations = [a for a in self.annotations if keep(a) or a.locked]
        if len(annotations) != len(self.annotations):
            self.change(annotations, [])

    def delete_selected(self):
        chosen = {i for i in self.selected if not self.annotations[i].locked}
        locked = len(self.selected) - len(chosen)
        if chosen:
            self.change([a for i, a in enumerate(self.annotations) if i not in chosen], [])
        if locked:
            self.status(ntr("{count} annotation is locked, and was kept", "{count} annotations are locked, and "
                            "were kept", locked), error=not chosen)

    def toggle_lock(self):
        if self.selected:
            self._change_selected(locked=not all(self.annotations[i].locked for i in self.selected))

    def delete_page(self):
        self._remove(lambda a: a.page != self.page)

    def delete_all(self):
        if self.annotations and QMessageBox.question(
                self, tr("Delete all the annotations"),
                ntr("Delete the {count} annotation of the document?", "Delete the {count} annotations of the "
                    "document?", len(self.annotations))) == QMessageBox.StandardButton.Yes:
            self._remove(lambda a: False)

    def copy_selected(self):
        if not self.selected:
            return
        self.keep_comment()
        _CLIPBOARD[:] = [self.annotations[i] for i in sorted(self.selected)]
        texts = [self.marked_text(a) or a.contents for a in _CLIPBOARD]
        QApplication.clipboard().setText("\n".join(t for t in texts if t))
        self.status(ntr("{count} annotation copied", "{count} annotations copied", len(_CLIPBOARD)))

    def paste(self, offset: float | None = None):
        """The annotations copied, on the page shown: a little apart from where they were if
        that is this page (marks over text, in the same place)."""
        if not _CLIPBOARD or self.doc is None:
            return
        page = self.doc[self.page].rect
        new = []
        for a in _CLIPBOARD:
            shift = (10.0 if a.page == self.page else 0.0) if offset is None else offset
            if a.kind in MARKUP:
                shift = 0.0
            b = dataclasses.replace(a, page=self.page, xref=0, created="", modified="", locked=False)
            x0, y0, x1, y1 = b.rect
            dx = max(-x0, min(shift, page.width - x1))
            dy = max(-y0, min(shift, page.height - y1))
            new.append(annots.moved(b, dx, dy) if dx or dy else b)
        self.change(self.annotations + new, list(range(len(self.annotations), len(self.annotations) + len(new))))

    def duplicate(self):
        if self.selected:
            self.copy_selected()
            self.paste()

    def comment_action(self):
        """The comment of the annotation selected, to write; with none, the note tool."""
        if len(self.selected) == 1:
            self.comment.setFocus()
        else:
            self.set_tool("note")

    def properties_dialog(self):
        self.keep_comment()
        if not self.selected:
            return
        chosen = [self.annotations[i] for i in self.selected]
        dialog = PropertiesDialog(chosen, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        annotations = list(self.annotations)
        for i in self.selected:
            annotations[i] = dialog.apply(annotations[i])
        self.change(annotations, self.selected)
        if dialog.as_default.isChecked() and len({a.kind for a in chosen}) == 1:
            self.use_style(annotations[self.selected[0]])

    def use_style(self, a: Annotation):
        """Make new annotations of A's kind look like A."""
        old = self.prefs.style(a.kind)
        style = dataclasses.replace(old, color=a.color, fill=a.fill, opacity=a.opacity, width=a.width,
                                    font_size=a.font_size, font=a.font, align=a.align, icon=a.icon,
                                    start=a.ends[0], end=a.ends[1], dashed=a.dashed)
        self.set_prefs(self.prefs.with_style(a.kind, style))
        self.status(tr("New annotations of this kind will look like this one"))

    def set_color(self, color: str):
        """The colour of the selected annotations; with none selected, that of new
        annotations of the tool chosen."""
        if self.selected:
            self._change_selected(color=color)
        elif self.canvas.mode in KINDS:
            self.set_tool_color(self.canvas.mode, color)

    def choose_color(self):
        if self.selected:
            current = self.annotations[self.selected[0]].color
        elif self.canvas.mode in KINDS:
            current = self.prefs.style(self.canvas.mode).color
        else:
            return
        chosen = QColorDialog.getColor(QColor(current), self, tr("Colour"))
        if chosen.isValid():
            self.set_color(chosen.name())

    def _color_menu(self):
        menu = self.color_button.menu()
        menu.clear()
        for value, name in swatches():
            menu.addAction(swatch(value), name, lambda v=value: self.set_color(v))
        menu.addSeparator()
        menu.addAction(tr("Other colour…"), self.choose_color)

    def keep_comment(self):
        """The comment typed in the panel, given to the annotation selected."""
        if len(self.selected) != 1 or not self.comment.isEnabled():
            return
        i = self.selected[0]
        if i >= len(self.annotations):
            return
        text = self.comment.toPlainText().strip("\n")
        if text != self.annotations[i].contents:
            self.replace(i, dataclasses.replace(self.annotations[i], contents=text))

    # ----------------------------------------------------------------- settings

    def set_prefs(self, prefs: settings.Settings):
        """Use PREFS, and keep them in the configuration file."""
        self.prefs = prefs
        try:
            settings.save(prefs)
        except (OSError, ValueError) as e:
            self.status(tr("Could not keep the setting: {error}", error=e), error=True)
        colors.set_palette(prefs.palette)
        self._have_conform = conform.available(prefs.pdfconform)
        self.apply_shortcuts()
        self._start_autosave()
        self._show_panel()

    def settings_dialog(self):
        dialog = SettingsDialog(self.prefs, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_prefs(dialog.settings())
            self.refresh()

    # ----------------------------------------------------------------- the menu of an annotation

    def _colors_menu(self, menu: QMenu, title: str, current: str | None, choose) -> QMenu:
        """A menu of colours (CURRENT ticked), each given to CHOOSE."""
        sub = menu.addMenu(swatch(current) if current else QIcon(), title)
        group = QActionGroup(sub)
        values = []
        for value, name in swatches():
            act = sub.addAction(swatch(value), name, lambda v=value: choose(v))
            act.setCheckable(True)
            act.setChecked(value == current)
            group.addAction(act)
            values.append(value)
        sub.addSeparator()
        other = sub.addAction(tr("Other colour…"), self.choose_color)
        if current and current not in values:
            other.setText(tr("Other colour ({color})…", color=current))
            other.setIcon(swatch(current))
        return sub

    def annotation_menu(self, index: int, where, point=None):
        """The right-click menu: of the annotations selected (INDEX: the one clicked),
        or of the page (INDEX -1)."""
        self.keep_comment()
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        if index >= 0 and self.selected:
            chosen = [self.annotations[i] for i in self.selected]
            if len(chosen) == 1:
                menu.addSection(chosen[0].name())
            else:
                menu.addSection(ntr("{count} annotation", "{count} annotations", len(chosen)))
            colors_ = {a.color for a in chosen}
            self._colors_menu(menu, tr("Colour"), colors_.pop() if len(colors_) == 1 else None,
                              lambda v: self._change_selected(color=v))
            if all(a.kind in MARKUP for a in chosen):
                change = menu.addMenu(tr("Change to"))
                for kind in MARKUP:
                    act = change.addAction(tool_name(kind), lambda k=kind: self._change_selected(kind=k))
                    act.setEnabled(any(a.kind != kind for a in chosen))
            if len(chosen) == 1 and chosen[0].kind in MARKUP:
                text = self.marked_text(chosen[0])
                if text:
                    menu.addAction(tr("Copy the text marked"), lambda: QApplication.clipboard().setText(text))
                    act = menu.addAction(tr("Copy it as a quotation"), lambda: QApplication.clipboard().setText(
                        exchange.quotation(self.doc, chosen[0], self.path.name if self.path else "")))
                    act.setToolTip(tr("The text marked, in quotation marks, with the document and its page"))
            menu.addSeparator()
            menu.addAction(self.a_copy)
            menu.addAction(self.a_duplicate)
            if len({a.kind for a in chosen}) == 1:
                menu.addAction(tr("Use its style for new annotations"), lambda: self.use_style(chosen[0]))
            if len(self._movable()) > 1:
                menu.addMenu(self.m_align)
            menu.addSeparator()
            menu.addAction(tr("Properties…"), self.properties_dialog)
            all_locked = all(a.locked for a in chosen)
            menu.addAction(tr("Unlock") if all_locked else tr("Lock"), self.toggle_lock)
            act = menu.addAction(icon("edit-delete"), ntr("Delete the annotation", "Delete the {count} annotations",
                                                          len(chosen)), self.delete_selected)
            act.setEnabled(not all_locked)
        else:
            if point is not None and self.doc is not None:
                x = min(point.x(), self.doc[self.page].rect.width - annots.NOTE_SIZE)
                y = min(point.y(), self.doc[self.page].rect.height - annots.NOTE_SIZE)
                rect = (round(x, 2), round(y, 2), round(x + annots.NOTE_SIZE, 2), round(y + annots.NOTE_SIZE, 2))
                menu.addAction(icon("note"), tr("Add a note here…"),
                               lambda: self.add_drawn(self.new_annotation("note", self.page, rect)))
                if _CLIPBOARD:
                    menu.addAction(self.a_paste)
                menu.addSeparator()
            for tool in ("select", "highlight", "note", "freetext", "rect", "ink", "eraser"):
                menu.addAction(self.tool_actions[tool])
            here = [i for i, a in enumerate(self.annotations) if a.page == self.page]
            if here:
                menu.addSeparator()
                menu.addAction(ntr("Select the annotation of this page", "Select the {count} annotations of this "
                                   "page", len(here)), self.select_page)
                menu.addAction(self.a_clear_page)
        self.show_menu(menu, where)

    def show_menu(self, menu: QMenu, where):
        menu.exec(where)

    def _edit_menu(self):
        """The Edit menu, as things are when it opens."""
        n = len(self.selected)
        self.a_delete.setText(ntr("Delete the selected annotation", "Delete the {count} selected annotations", n)
                              if n else tr("Delete the selected annotations"))
        here = self.doc is not None and any(a.page == self.page for a in self.annotations)
        self.a_select_all.setEnabled(here)
        self.a_select_kind.setEnabled(bool(self.selected))
        self.a_clear_page.setEnabled(here)
        self.a_lock.setText(tr("Unlock") if self.selected and all(self.annotations[i].locked for i in self.selected)
                            else tr("Lock"))
        self.m_align.setEnabled(len(self._movable()) > 1)
        self.a_undo.setText(tr("Undo") if not self.undo_stack else tr("Undo ({count})", count=len(self.undo_stack)))

    def undo(self):
        self.keep_comment()
        if self.undo_stack:
            self.redo_stack.append(self.annotations)
            self.annotations = self.undo_stack.pop()
            self.selected = []
            self.refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.annotations)
            self.annotations = self.redo_stack.pop()
            self.selected = []
            self.refresh()

    # ----------------------------------------------------------------- selection and the list

    def pick(self, indices: list[int], add: bool):
        self.keep_comment()
        if add:
            chosen = list(self.selected)
            for i in indices:
                if i in chosen:
                    chosen.remove(i)
                else:
                    chosen.append(i)
        else:
            chosen = list(indices)
        if chosen != self.selected:
            self.selected = chosen
            self.refresh(pages=False)

    def select_page(self):
        self.pick([i for i, a in enumerate(self.annotations) if a.page == self.page], False)

    def select_kind(self):
        kinds = {self.annotations[i].kind for i in self.selected}
        self.pick([i for i, a in enumerate(self.annotations) if a.page == self.page and a.kind in kinds], False)

    def _table_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        chosen = [self._rows[r] for r in rows if r < len(self._rows)]
        if chosen == self.selected:
            return
        self.keep_comment()
        self.selected = chosen
        if chosen and all(self.annotations[i].page != self.page for i in chosen):
            self.show_page(self.annotations[chosen[0]].page)
        else:
            self.refresh(pages=False, table=False)
        if len(chosen) == 1:
            self.canvas.flash(self.annotations[chosen[0]].rect)

    def go_annotation(self, step: int):
        """The next (STEP 1) or previous (-1) annotation of the list, as it is sorted and filtered."""
        if not self._rows:
            return
        current = self._rows.index(self.selected[0]) if self.selected and self.selected[0] in self._rows else None
        if current is None:  # (from the page shown)
            after = [r for r, i in enumerate(self._rows) if self.annotations[i].page >= self.page]
            row = (after[0] if after else 0) if step > 0 else (max(after[0] - 1, 0) if after else len(self._rows) - 1)
        else:
            row = (current + step) % len(self._rows)
        i = self._rows[row]
        self.keep_comment()
        self.selected = [i]
        if self.annotations[i].page != self.page:
            self.show_page(self.annotations[i].page)
        self.refresh(pages=False, table=False)
        self.canvas.flash(self.annotations[i].rect)

    def _filter_changed(self):
        self._fill_table()
        if self.a_only_listed.isChecked():
            self.refresh(table=False)

    def _passes(self, a: Annotation) -> bool:
        """Whether A is let through by the search and filters of the list."""
        kind, author, color = self.f_kind.currentData(), self.f_author.currentData(), self.f_color.currentData()
        if kind and a.kind != kind or author is not None and a.author != author or color and a.color != color:
            return False
        words = self.search.text().lower().split()
        if words:
            text = " ".join((a.contents, a.author, a.name(), self.marked_text(a))).lower()
            return all(w in text for w in words)
        return True

    def _fill_filters(self):
        """The choices of the filters: the kinds, authors (with how many annotations each has) and
        colours there are."""
        by_author = Counter(a.author for a in self.annotations)
        for box, everything, values in (
                (self.f_kind, tr("All kinds"), sorted({a.kind for a in self.annotations},
                                                      key=lambda k: KINDS.index(k))),
                (self.f_author, tr("All authors"), sorted({a.author for a in self.annotations})),
                (self.f_color, tr("All colours"), sorted({a.color for a in self.annotations}))):
            current = box.currentData()
            box.blockSignals(True)
            box.clear()
            box.addItem(everything, None if box is self.f_author else "")
            for value in values:
                if box is self.f_kind:
                    box.addItem(tool_name(value), value)
                elif box is self.f_author:
                    box.addItem(f"{value or tr('(no author)')} ({by_author[value]})", value)
                else:
                    box.addItem(swatch(value), color_name(value), value)
            index = box.findData(current) if current is not None else 0
            box.setCurrentIndex(max(index, 0))
            box.blockSignals(False)

    # ----------------------------------------------------------------- showing

    def refresh(self, pages: bool = True, table: bool = True):
        """Show the annotations again, after a change."""
        if table:
            self._fill_filters()
            self._fill_table()
        if pages:
            self._label_pages()
        self.show_page(self.page, keep_view=True)
        self._show_panel()
        self._enable()
        self._update_title()

    def shown(self) -> list[int]:
        """The annotations to show on the pages: all, none, or those the list lets through."""
        if not self.a_show.isChecked():
            return []
        if self.a_only_listed.isChecked():
            return sorted(self._rows)
        return list(range(len(self.annotations)))

    def show_page(self, page: int, keep_view: bool = False):
        if self.doc is None:
            self.canvas.show_page(None, [], [])
            return
        page = max(0, min(page, self.count - 1))
        keep_view = keep_view or page == self.page
        if page != self.page:
            self.keep_comment()
            self.selected = [i for i in self.selected if self.annotations[i].page == page]
            self.page = page
            self._show_panel()
            self._select_rows()
            self._enable()
        here = [(i, self.annotations[i]) for i in self.shown() if self.annotations[i].page == page]
        self.canvas.editable = self.a_show.isChecked()
        self.canvas.placeholder = self._thumbs.get(page)
        self.canvas.show_page(self.doc[page], here, self.selected, keep_view=keep_view)
        self.canvas.render_ahead([self.doc[n] for n in (page + 1, page - 1) if 0 <= n < self.count])
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page + 1)
        self.page_spin.blockSignals(False)
        self.pages.blockSignals(True)
        self.pages.setCurrentRow(page)
        self.pages.blockSignals(False)

    def _fit(self, how: str):
        self.canvas.fit = how
        self.canvas.apply_fit()

    def _fill_pages(self):
        self.pages.clear()
        blank = QPixmap(THUMB)
        blank.fill(QColor(0, 0, 0, 0))
        for n in range(self.count):
            item = QListWidgetItem(QIcon(blank), str(n + 1))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.pages.addItem(item)
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(self.count, 1))
        self.page_spin.setSuffix(f" / {self.count}")
        self.page_spin.blockSignals(False)
        self.thumb_timer.start()

    def _draw_thumbnails(self):
        """Draw one thumbnail at each turn of the event loop, those in view first,
        so that the window answers between them."""
        if self.doc is None:
            self.thumb_timer.stop()
            return
        top = self.pages.indexAt(QPoint(10, 10)).row()
        start = max(top, 0)
        n = next((m for m in [*range(start, self.count), *range(start)] if m not in self._thumbs), None)
        if n is None:
            self.thumb_timer.stop()
            return
        page = self.doc[n]
        scale = min(THUMB.width() / page.rect.width, THUMB.height() / page.rect.height)
        remote = renderer()
        if self.canvas.source is not None and remote.available():
            # (in another process: the timer waits until it is drawn, then goes on with the next)
            self.thumb_timer.stop()
            source = self.canvas.source
            remote.request("thumbs", source, n, round(scale, 4),
                           lambda image: self._thumb_arrived(source, n, scale, image))
            return
        self._thumbs[n] = page_image(page, scale)
        self._thumb(n)

    def _thumb_arrived(self, source, n: int, scale: float, image: QImage | None):
        if self.doc is None or source != self.canvas.source:
            return  # (of a document no longer open)
        self._thumbs[n] = image if image is not None else page_image(self.doc[n], scale)
        self._thumb(n)
        self.thumb_timer.start()

    def _thumb(self, n: int):
        """The thumbnail of page N, with its annotations (drawn again only if they changed)."""
        image = self._thumbs.get(n)
        if image is None or n >= self.pages.count():
            return
        shown = tuple(self._by_page[n]) if n < len(self._by_page) else ()
        if self._thumb_shown.get(n) == shown:
            return
        self._thumb_shown[n] = shown
        pixmap = QPixmap(THUMB)
        pixmap.fill(QColor(0, 0, 0, 0))
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y = (THUMB.width() - image.width()) // 2, THUMB.height() - image.height()
        p.drawImage(x, y, image)
        p.save()
        p.translate(x, y)
        scale = image.width() / self.doc[n].rect.width
        p.scale(scale, scale)
        for a in shown:
            paint(p, a, thumbnail=True)
        p.restore()
        p.setPen(QPen(QColor(128, 128, 128)))
        p.drawRect(x, y, image.width() - 1, image.height() - 1)
        p.end()
        self.pages.item(n).setIcon(QIcon(pixmap))

    def _label_pages(self):
        if self.doc is None:
            return
        self._by_page = [[] for _ in range(self.count)]
        shown = set(self.shown())
        for i, a in enumerate(self.annotations):
            if 0 <= a.page < self.count and i in shown:
                self._by_page[a.page].append(a)
        for n in range(min(self.count, self.pages.count())):
            item = self.pages.item(n)
            count = len(self._by_page[n])
            text = f"{n + 1}  ● {count}" if count else str(n + 1)
            if item.text() != text:
                item.setText(text)
            self._thumb(n)

    def marked_text(self, a: Annotation) -> str:
        """The text under a highlight (or another markup), kept once found."""
        if a.kind not in MARKUP:
            return ""
        key = (a.page, a.quads)
        if key not in self._marked and self.doc is not None and 0 <= a.page < self.count:
            self._marked[key] = annots.text_under(self.doc[a.page], list(a.quads))
        return self._marked.get(key, "")

    def _fill_table(self):
        sort = self.sort.currentData()
        keys = {
            "page": lambda i: (self.annotations[i].page, self.annotations[i].rect[1], self.annotations[i].rect[0]),
            "changed": lambda i: (self._age(self.annotations[i]), self.annotations[i].page),
            "kind": lambda i: (KINDS.index(self.annotations[i].kind), self.annotations[i].page),
            "author": lambda i: (self.annotations[i].author.lower(), self.annotations[i].page),
        }
        order = sorted((i for i, a in enumerate(self.annotations) if self._passes(a)), key=keys.get(sort, keys["page"]))
        self._rows = order
        self.table.blockSignals(True)
        self.table.setRowCount(len(order))
        for row, i in enumerate(order):
            a = self.annotations[i]
            text = " ".join(a.contents.split())
            cell = QTableWidgetItem(text)
            if not text and a.kind in MARKUP:  # (the text marked, in italics)
                marked = self.marked_text(a)
                cell = QTableWidgetItem(f"“{marked}”" if marked else "")
                font = cell.font()
                font.setItalic(True)
                cell.setFont(font)
            if a.contents:
                cell.setToolTip(a.contents)
            kind = QTableWidgetItem(swatch(a.color), a.name() + (" 🔒" if a.locked else ""))
            kind.setToolTip(color_name(a.color))
            changed = QTableWidgetItem(date_text(a.modified or a.created)[2:] if a.modified or a.created else "")
            if a.created:
                changed.setToolTip(tr("Made: {made}; changed: {changed}", made=date_text(a.created),
                                      changed=date_text(a.modified) or "—"))
            cells = [QTableWidgetItem(str(a.page + 1)), kind, QTableWidgetItem(a.author), changed, cell]
            for col, c in enumerate(cells):
                self.table.setItem(row, col, c)
        for col in range(4):
            self.table.resizeColumnToContents(col)
        self.table.blockSignals(False)
        self.listed.setText(tr("{shown} of {count}", shown=len(order), count=len(self.annotations))
                            if len(order) != len(self.annotations) else
                            ntr("{count} annotation", "{count} annotations", len(order)))
        self._select_rows()

    @staticmethod
    def _age(a: Annotation) -> float:
        """For sorting the last changed first (those never saved, before all)."""
        when = annots.date_value(a.modified or a.created)
        return -when.timestamp() if when else float("-inf")

    def _select_rows(self):
        """Select in the list the rows of the annotations selected, all at once."""
        chosen = set(self.selected)
        model = self.table.model()
        last = self.table.columnCount() - 1
        selection = QItemSelection()
        start = None
        for row, i in enumerate(self._rows + [None]):
            if i is not None and i in chosen:
                if start is None:
                    start = row
            elif start is not None:  # (a run of selected rows ends: one range for all of it)
                selection.select(model.index(start, 0), model.index(row - 1, last))
                start = None
        self.table.blockSignals(True)
        self.table.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.table.blockSignals(False)
        rows = [r for r, i in enumerate(self._rows) if i in chosen]
        if len(rows) == 1:
            self.table.scrollToItem(self.table.item(rows[0], 0))

    def _show_panel(self):
        """The colour and comment of the selected annotations, or the colour of new ones of the tool."""
        chosen = [self.annotations[i] for i in self.selected if i < len(self.annotations)]
        if chosen:
            if len(chosen) == 1:
                title = tr("{kind}, on page {page}", kind=chosen[0].name(), page=chosen[0].page + 1)
                if chosen[0].author:
                    title += " — " + chosen[0].author
                self.panel_title.setText("<b>" + title + "</b>")
            else:
                self.panel_title.setText("<b>" + ntr("{count} annotation selected", "{count} annotations selected",
                                                     len(chosen)) + "</b>")
            colors_ = {a.color for a in chosen}
        elif self.canvas.mode in KINDS:
            self.panel_title.setText("<b>" + tr("New annotations: {kind}", kind=tool_name(self.canvas.mode).lower())
                                     + "</b>")
            colors_ = {self.prefs.style(self.canvas.mode).color}
        else:
            self.panel_title.setText("<b>" + tr("No annotation selected") + "</b>")
            colors_ = set()
        color = colors_.pop() if len(colors_) == 1 else None
        self.color_button.setIcon(swatch(color) if color else QIcon())
        self.color_button.setText(color_name(color) if color else (tr("(several)") if chosen else "—"))
        self.color_button.setEnabled(self.doc is not None and (bool(chosen) or self.canvas.mode in KINDS))
        one = len(chosen) == 1
        self.comment.blockSignals(True)
        self.comment.setEnabled(one)
        text = chosen[0].contents if one else ""
        if self.comment.toPlainText() != text:
            self.comment.setPlainText(text)
        self.comment.setPlaceholderText(tr("A comment on this annotation") if one
                                        else tr("Select an annotation to see its comment here"))
        self.comment.blockSignals(False)
        self.comment_label.setText(tr("Text:") if one and chosen[0].kind in ("note", "freetext", "callout", "caret")
                                   else tr("Comment:"))

    def _enable(self):
        has = self.doc is not None
        for w in (self.a_save_as, self.a_first, self.a_last, self.a_fit, self.a_fit_width, self.a_zoom_in,
                  self.a_zoom_out, self.page_spin, self.a_flat, self.a_bare, self.a_import_json, self.a_import_pdf,
                  *self.tool_actions.values()):
            w.setEnabled(has)
        for act in self.standard_actions.values():
            act.setEnabled(has and self._have_conform)
            act.setToolTip("" if self._have_conform else tr("Needs {command}: install it, or say where it is in "
                                                            "Settings", command=conform.COMMAND))
        for w in (self.a_export_md, self.a_export_csv, self.a_export_json, self.a_next_annot, self.a_prev_annot):
            w.setEnabled(has and bool(self._rows))
        self.a_save.setEnabled(has and self.is_modified())
        self.a_clear_all.setEnabled(bool(self.annotations))
        self.a_paste.setEnabled(has and bool(_CLIPBOARD))
        for w in (self.a_delete, self.b_delete, self.a_props, self.b_props, self.a_copy, self.a_duplicate,
                  self.a_lock):
            w.setEnabled(bool(self.selected))

    # ----------------------------------------------------------------- unsaved changes

    def is_modified(self) -> bool:
        return self.annotations != self.saved

    def _update_title(self):
        name = f"{self.path.name}[*] — py-annotate" if self.path else "py-annotate"
        self.setWindowTitle(name)
        self.setWindowModified(self.is_modified())

    def ask_unsaved(self) -> QMessageBox.StandardButton:
        box = QMessageBox(QMessageBox.Icon.Warning, tr("Unsaved annotations"),
                          tr("The annotations have changed since the document was last saved. Save them before "
                             "going on?"),
                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                          | QMessageBox.StandardButton.Cancel, self)
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())

    def maybe_discard(self) -> bool:
        """True if it is all right to go on (nothing unsaved, saved now, or discarded)."""
        if not self.is_modified():
            return True
        answer = self.ask_unsaved()
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        if answer == QMessageBox.StandardButton.Discard:
            if self.path is not None:
                recovery.discard(self.path)
            return True
        return False

    # ----------------------------------------------------------------- drag and drop

    def dragEnterEvent(self, event):
        if any(u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for u in event.mimeData().urls():
            if u.toLocalFile().lower().endswith(".pdf"):
                self.open_path(Path(u.toLocalFile()))
                break

    # ----------------------------------------------------------------- messages

    def warn(self, title: str, text: str):
        """A warning the user must see (a modal message box)."""
        QMessageBox.warning(self, title, text)

    def status(self, text: str, error: bool = False):
        self.statusBar().setStyleSheet("color: #c0392b;" if error else "")
        self.statusBar().showMessage(text, 0 if error else 8000)

    def about(self):
        QMessageBox.about(self, tr("About py-annotate"),
                          tr("<b>py-annotate {version}</b><p>Adds annotations to PDF documents: highlights, notes, "
                             "text boxes, shapes, stamps and drawings, which any PDF viewer shows and can edit.</p>"
                             "<p>By {author}.</p><p>Licensed under the GNU General Public License, version 3 or "
                             "later.</p>", version=__version__, author=AUTHOR))

