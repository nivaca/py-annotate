"""The window, driven as the user would: annotations made, moved and resized with the mouse, and saved."""

from __future__ import annotations

import dataclasses

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from py_annotate import annots, settings
from py_annotate.gui.window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, sample, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))  # (QSettings)
    w = MainWindow()

    def warn(title, text):  # (a message box would wait for a click for ever)
        raise AssertionError(f"warning shown: {title}: {text}")

    w.warn = warn
    w.typed = "Typed text"  # (what is "written on the page" for a new text box, note...: None gives up)

    def edit_text(annotation, index=-1):
        if w.typed is not None:
            w.canvas.text_done.emit(index, dataclasses.replace(annotation, contents=w.typed))

    w.canvas.edit_text = edit_text

    def ask_recover(when):  # (likewise)
        raise AssertionError("recovery offered")

    w.ask_recover = ask_recover
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    assert w.open_path(sample)
    app.processEvents()
    yield w
    w.annotations = w.saved = []
    w.close()


def mouse(w, kind, point, button=Qt.MouseButton.LeftButton, mods=Qt.KeyboardModifier.NoModifier, page=None):
    """A mouse event at POINT (in points) of PAGE (the page in view, if None)."""
    c = w.canvas
    item = c.pages[w.page if page is None else page]
    pos = c.mapFromScene(item.mapToScene(QPointF(*point)))
    handler = {QEvent.Type.MouseButtonPress: c.mousePressEvent, QEvent.Type.MouseMove: c.mouseMoveEvent,
               QEvent.Type.MouseButtonRelease: c.mouseReleaseEvent,
               QEvent.Type.MouseButtonDblClick: c.mouseDoubleClickEvent}[kind]
    buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else button
    handler(QMouseEvent(kind, QPointF(pos), QPointF(c.viewport().mapToGlobal(pos)), buttons, button, mods))


def drag(w, *points, mods=Qt.KeyboardModifier.NoModifier, page=None):
    """Drag with the mouse on the page (PAGE, or the one in view), through POINTS (in points)."""
    mouse(w, QEvent.Type.MouseButtonPress, points[0], mods=mods, page=page)
    for p in points[1:]:
        mouse(w, QEvent.Type.MouseMove, p, mods=mods, page=page)
    mouse(w, QEvent.Type.MouseButtonRelease, points[-1], mods=mods, page=page)
    QApplication.processEvents()


def click(w, point):
    drag(w, point)


def close(a, b, tolerance=2.0):
    return all(abs(x - y) <= tolerance for x, y in zip(a, b, strict=True))


def test_highlight_text(window):
    window.set_tool("highlight")
    drag(window, (75, 95), (200, 125))  # (from the first line to the second)
    assert len(window.annotations) == 1
    a = window.annotations[0]
    assert a.kind == "highlight" and len(a.quads) == 2 and a.color == settings.STYLES["highlight"].color
    assert "First line" in window.marked_text(a)
    window.set_tool("underline")
    mouse(window, QEvent.Type.MouseButtonDblClick, (80, 125))  # (a word: "A")
    assert window.annotations[-1].kind == "underline" and len(window.annotations[-1].quads) == 1


def test_draw_move_resize(window):
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    assert len(window.annotations) == 1 and window.selected == [0]
    assert close(window.annotations[0].rect, (100, 300, 250, 400))
    drag(window, (150, 350), (170, 360))  # (inside: moves it)
    assert close(window.annotations[0].rect, (120, 310, 270, 410))
    drag(window, (270, 410), (300, 450))  # (its corner: resizes it)
    assert close(window.annotations[0].rect, (120, 310, 300, 450))
    window.undo()
    window.undo()
    assert close(window.annotations[0].rect, (100, 300, 250, 400))
    window.redo()
    assert close(window.annotations[0].rect, (120, 310, 270, 410))


def test_lines_and_drawings(window):
    window.set_tool("arrow")
    drag(window, (100, 500), (300, 500))
    arrow = window.annotations[0]
    assert arrow.kind == "arrow" and close(arrow.paths[0][0] + arrow.paths[0][1], (100, 500, 300, 500))
    drag(window, (300, 500), (300, 600))  # (its end: moves only that end)
    assert close(window.annotations[0].paths[0][1], (300, 600))
    window.set_tool("ink")
    drag(window, (100, 650), (120, 670), (150, 660), (180, 690))
    ink = window.annotations[1]
    assert ink.kind == "ink" and len(ink.paths[0]) == 4
    window.set_tool("rect")
    drag(window, (400, 700), (401, 701))  # (a click: draws nothing)
    assert len(window.annotations) == 2


def test_note_and_text_box(window):
    window.set_tool("note")
    click(window, (400, 200))
    note = window.annotations[0]
    assert note.kind == "note" and note.contents == "Typed text"
    assert close(note.rect, (400, 200, 400 + annots.NOTE_SIZE, 200 + annots.NOTE_SIZE))
    window.set_tool("freetext")
    click(window, (300, 300))  # (a click: a box of the usual size)
    box = window.annotations[1]
    assert box.kind == "freetext" and box.contents == "Typed text"
    assert close(box.rect[:2], (300, 300))
    window.typed = None  # (given up: nothing is made)
    click(window, (100, 700))
    assert len(window.annotations) == 2


def test_comment_in_the_panel(window):
    window.set_tool("ellipse")
    drag(window, (100, 300), (250, 400))
    window.comment.setPlainText("Look at this")
    window.keep_comment()
    assert window.annotations[0].contents == "Look at this"
    window.undo()
    assert window.annotations[0].contents == ""


def test_new_colour_is_kept(window):
    window.set_tool("highlight")
    window.set_color("#43a047")
    assert settings.load().style("highlight").color == "#43a047"
    drag(window, (75, 95), (200, 100))
    assert window.annotations[0].color == "#43a047"
    window.set_color("#e53935")  # (selected: only it changes)
    assert window.annotations[0].color == "#e53935" and settings.load().style("highlight").color == "#43a047"


def test_save_and_open_again(window, sample):
    window.set_tool("highlight")
    drag(window, (75, 95), (200, 100))
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    window.show_page(2)  # (the turned page)
    window.set_tool("note")
    click(window, (100, 100))
    assert window.is_modified() and window.save()
    assert not window.is_modified() and len(window.undo_stack) == 3  # (what was done can still be undone)
    kinds = [a.kind for a in annots.read(annots.open_pdf(sample))]
    assert sorted(kinds) == ["highlight", "note", "rect"]
    # the window shows the annotations of the file now, and can delete one of them
    assert all(a.xref for a in window.annotations)
    window.show_page(0)
    rect = next(a for a in window.annotations if a.kind == "rect")
    window.pick([window.annotations.index(rect)], False)
    window.delete_selected()
    before = sample.read_bytes()
    assert window.save()
    assert sample.read_bytes().startswith(before)  # (saved incrementally: added at the end)
    assert sorted(a.kind for a in annots.read(annots.open_pdf(sample))) == ["highlight", "note"]
    # undone after saving, and saved again: the rectangle is back
    window.undo()
    assert sorted(a.kind for a in window.annotations) == ["highlight", "note", "rect"]
    assert window.save()
    assert sorted(a.kind for a in annots.read(annots.open_pdf(sample))) == ["highlight", "note", "rect"]
    window.undo()  # (and the note, made before the first save, goes)
    assert window.save()
    assert sorted(a.kind for a in annots.read(annots.open_pdf(sample))) == ["highlight", "rect"]


def test_save_as(window, tmp_path, sample):
    window.set_tool("line")
    drag(window, (100, 300), (250, 400))
    target = tmp_path / "copy.pdf"
    assert window.save_to(target)
    assert window.path == target
    assert [a.kind for a in annots.read(annots.open_pdf(target))] == ["line"]
    assert annots.read(annots.open_pdf(sample)) == []


def test_pages_rendered_elsewhere(app, sample, tmp_path, monkeypatch):
    """With the pages rendered in other processes, a document with annotations is shown without them."""
    from py_annotate.gui import renderer

    monkeypatch.setattr(renderer, "ENABLED", True)
    monkeypatch.setenv("HOME", str(tmp_path))
    annots.write(sample, [annots.Annotation("rect", 0, (10, 10, 50, 50), "#000000")], sample)
    w = MainWindow()
    assert w.open_path(sample)
    temp = w._temp
    assert temp is not None and temp.is_file() and w.canvas.source[0] == str(temp)
    assert annots.read(annots.open_pdf(temp)) == []
    w.close()
    assert not temp.exists()


def test_language(window, sample):
    window.change_language("es")
    from py_annotate.gui.window import _WINDOWS

    new = _WINDOWS[-1]
    assert new.menuBar().actions()[0].text() == "&Archivo" and new.path == sample
    new.change_language("en")
    _WINDOWS[-1].close()


def test_new_tools(window):
    window.set_tool("area")
    drag(window, (100, 300), (200, 360))
    window.set_tool("cloud")
    drag(window, (300, 300), (400, 360))
    window.set_tool("callout")
    drag(window, (100, 500), (250, 420))  # (from the place pointed at, to where the box goes)
    window.set_tool("caret")
    click(window, (150, 600))
    window.set_tool("stamp")
    click(window, (300, 700))
    kinds = [a.kind for a in window.annotations]
    assert kinds == ["area", "cloud", "callout", "caret", "stamp"]
    area, cloud, callout, caret, stamp = window.annotations
    assert area.opacity == settings.STYLES["area"].opacity and len(cloud.paths[0]) == 4
    assert close(callout.paths[0][0], (100, 500)) and callout.contents == "Typed text"
    assert stamp.stamp == "Approved" and stamp.image and close(((stamp.rect[0] + stamp.rect[2]) / 2,), (300,))
    assert window.save()
    assert [a.kind for a in annots.read(annots.open_pdf(window.path))] == kinds


def test_polygon_by_clicks(window):
    window.set_tool("polygon")
    for p in ((100, 300), (200, 300), (150, 380)):
        click(window, p)
    window.canvas.finish_polygon()
    assert window.annotations[0].kind == "polygon" and len(window.annotations[0].paths[0]) == 3
    window.set_tool("select")
    drag(window, (100, 300), (90, 290))  # (a point of the polygon, selected: moves only that point)
    assert close(window.annotations[0].paths[0][0], (90, 290)) and close(window.annotations[0].paths[0][1], (200, 300))


def test_eraser(window):
    window.set_tool("ink")
    drag(window, (100, 650), (150, 650), (200, 650), (250, 650), (300, 650))
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    window.set_tool("eraser")
    drag(window, (200, 640), (200, 660))  # (across the middle of the stroke: it is cut in two)
    ink = window.annotations[0]
    assert ink.kind == "ink" and len(ink.paths) == 2
    drag(window, (100, 350), (110, 350))  # (on the rectangle: it goes)
    assert [a.kind for a in window.annotations] == ["ink"]
    window.undo()
    assert len(window.annotations) == 2


def test_select_by_frame_copy_paste_align(window):
    window.set_tool("rect")
    drag(window, (100, 300), (150, 340))
    drag(window, (200, 320), (260, 380))
    window.set_tool("select")
    drag(window, (80, 280), (300, 400))  # (a frame around both)
    assert sorted(window.selected) == [0, 1]
    window.align("top")
    assert window.annotations[0].rect[1] == window.annotations[1].rect[1]
    window.copy_selected()
    window.show_page(1)
    window.paste()
    assert [a.page for a in window.annotations] == [0, 0, 1, 1]
    assert window.annotations[2].rect == window.annotations[0].rect  # (another page: in the same place)
    window.duplicate()
    assert len(window.annotations) == 6 and close(window.annotations[4].rect[:2],
                                                  [v + 10 for v in window.annotations[2].rect[:2]])


def test_lock(window):
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    window.toggle_lock()
    assert window.annotations[0].locked
    window.set_tool("select")
    drag(window, (150, 350), (170, 360))  # (locked: it stays)
    assert close(window.annotations[0].rect, (100, 300, 250, 400))
    window.delete_selected()
    assert len(window.annotations) == 1


def test_filters_and_navigation(window):
    window.set_tool("highlight")
    drag(window, (75, 95), (200, 100))
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    window.replace(1, dataclasses.replace(window.annotations[1], contents="about justice", author="B"))
    window.search.setText("justice")
    window.search_timer.timeout.emit()  # (the pause after typing)
    assert window._rows == [1]
    window.search.clear()
    window.f_author.setCurrentIndex(window.f_author.findData("B"))
    window._filter_changed()
    assert window._rows == [1]
    window.f_author.setCurrentIndex(0)
    window._filter_changed()
    window.selected = []
    window.go_annotation(1)
    assert window.selected == [0]
    window.go_annotation(1)
    assert window.selected == [1]
    window.a_show.setChecked(False)
    assert window.canvas.items_ == []


def test_tool_behaviour(window):
    prefs = window.prefs.with_style("rect", dataclasses.replace(window.prefs.style("rect"), sticky=False))
    window.set_prefs(prefs)
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    assert window.canvas.mode == "select"  # (not sticky: back to Select)
    window.set_tool("note")
    window.typed = None  # (its text asked for, and given up: no note)
    click(window, (400, 200))
    assert len(window.annotations) == 1


def test_recovery(window, sample, app):
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    window.keep_recovery()
    kept = list(window.annotations)
    window.annotations = window.saved = []  # (as if the program had stopped)
    other = MainWindow()
    other.ask_recover = lambda when: True
    assert other.open_path(sample)
    assert other.annotations == kept and other.is_modified()
    assert other.save()
    other.close()


def test_export_import(window, tmp_path):
    window.set_tool("highlight")
    drag(window, (75, 95), (200, 100))
    window._ask_target = lambda title, suffix, ext="pdf": tmp_path / f"out.{ext}"
    for kind in ("json", "md", "csv"):
        assert window.export_dialog(kind)
    assert "First line" in (tmp_path / "out.md").read_text(encoding="utf-8")
    window.annotations = []
    window.refresh()
    assert window.import_from(tmp_path / "out.json", "json")
    assert [a.kind for a in window.annotations] == ["highlight"]
    assert window.import_from(tmp_path / "out.json", "json") and len(window.annotations) == 1  # (already there)
    assert window.save_flattened_dialog()
    flat = annots.open_pdf(tmp_path / "out.pdf")
    assert list(flat[0].annots()) == [] and window.path != tmp_path / "out.pdf"


def test_settings_dialog(window):
    from PySide6.QtGui import QKeySequence

    from py_annotate.gui.prefs import SettingsDialog

    dialog = SettingsDialog(window.prefs, window)
    dialog.author.setText("  N.   V. ")
    dialog.palette_rows[0][1].setText("Key ideas")
    dialog.key_edits["rect"].setKeySequence(QKeySequence("H"))
    assert dialog.conflicts() == [("H", "highlight", "rect")]
    dialog.key_edits["rect"].setKeySequence(QKeySequence("Ctrl+Alt+R"))
    assert dialog.conflicts() == []
    window.set_prefs(dialog.settings())
    assert window.prefs.author == "N. V." and window.prefs.palette[0] == ("#ffeb3b", "Key ideas")
    assert window.tool_actions["rect"].shortcut().toString() == "Ctrl+Alt+R"
    from py_annotate.gui.colors import color_name

    assert color_name("#ffeb3b") == "Yellow — Key ideas"


def fake_pdf2iso(folder) -> str:
    """A pdf2iso that copies the file, leaving out polygons, as Ghostscript does."""
    import sys

    script = folder / "pdf2iso"
    script.write_text(f"""#!{sys.executable}
import sys, pymupdf
args = sys.argv[1:]
out = args[args.index("-o") + 1]
doc = pymupdf.open(args[-1])
if doc.needs_pass:
    doc.authenticate(args[args.index("-p") + 1])
for page in doc:
    for xref in [a.xref for a in page.annots() if a.type[1] == "Polygon"]:
        page.delete_annot(page.load_annot(xref))
doc.save(out)
print("OK  (veraPDF: PASS) in.pdf -> out.pdf [PDF/A-2b]")
""")
    script.chmod(0o755)
    return str(script)


def test_save_as_pdfa(window, tmp_path):
    window.set_prefs(dataclasses.replace(window.prefs, pdfconform=str(tmp_path / "missing")))
    assert not window.standard_actions["a-2b"].isEnabled()  # (no pdf2iso there)
    window.set_prefs(dataclasses.replace(window.prefs, pdfconform=fake_pdf2iso(tmp_path)))
    assert window.standard_actions["a-2b"].isEnabled()
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    window.set_tool("polygon")
    for p in ((300, 300), (400, 300), (350, 380)):
        click(window, p)
    window.canvas.finish_polygon()
    asked = []
    window.ask_flatten_lost = lambda standard, names: asked.append(names) or True
    target = tmp_path / "copy-pdfa.pdf"
    assert window.save_standard(target, "a-2b")
    assert asked == ["polygon (1)"]  # (left out by Ghostscript: made part of the pages instead)
    doc = annots.open_pdf(target)
    assert [a.kind for a in annots.read(doc)] == ["rect"] and doc[0].get_drawings()
    assert "veraPDF: PASS" in window.statusBar().currentMessage()
    assert window.path != target and window.is_modified()  # (a copy: the document stays as it was)


def test_panel_can_be_hidden(window):
    assert window.panel.isVisible()
    window.a_panel.trigger()
    assert not window.panel.isVisible()
    window.a_panel.trigger()
    assert window.panel.isVisible()
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    window.replace(0, dataclasses.replace(window.annotations[0], author="B"))
    assert window.f_author.itemText(window.f_author.findData("B")) == "B (1)"


def test_text_written_on_the_page(window):
    from py_annotate.gui.canvas import PageCanvas

    canvas = window.canvas
    del canvas.edit_text  # (the real one: an editor on the page)
    window.set_tool("freetext")
    click(window, (300, 300))
    assert canvas.editing() and window.annotations == []  # (made once its text is written)
    canvas.commit_text("Written here")
    assert [a.contents for a in window.annotations] == ["Written here"]
    # double-clicked: written again, where it is
    window.set_tool("select")
    mouse(window, QEvent.Type.MouseButtonDblClick, (310, 310))
    assert canvas.editing()
    canvas.commit_text("Written again")
    assert window.annotations[0].contents == "Written again" and len(window.undo_stack) == 2
    # a note: Escape gives it up
    window.set_tool("note")
    click(window, (100, 600))
    assert canvas.editing()
    canvas.cancel_text()
    assert len(window.annotations) == 1
    assert isinstance(canvas, PageCanvas)


def test_replies_status_and_tags_in_the_panel(window, sample):
    window.prefs = dataclasses.replace(window.prefs, author="Me")
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    window.listing.reply_edit.setText("Is this right?")
    window.add_reply()
    window.set_status("Accepted")
    a = window.annotations[0]
    assert [(r.author, r.contents, r.state) for r in a.replies] == [("Me", "Is this right?", ""),
                                                                    ("Me", "Status: Accepted", "Accepted")]
    assert a.status() == "Accepted" and window.listing.replies.count() == 2
    window.listing.tags.setText("Ethics, Aristotle")
    window.keep_tags()
    assert window.annotations[0].tags == ("Ethics", "Aristotle")
    window.toggle_category("Definitions")
    assert window.annotations[0].categories == ("Definitions",)
    # the filters: by status, tag, category; and the search finds replies
    window.f_status.setCurrentIndex(window.f_status.findData("Accepted"))
    window.f_tag.setCurrentIndex(window.f_tag.findData("Ethics"))
    window._filter_changed()
    assert window._rows == [0]
    window.f_status.setCurrentIndex(window.f_status.findData("-"))
    window._filter_changed()
    assert window._rows == []
    window.f_status.setCurrentIndex(0)
    window.f_tag.setCurrentIndex(0)
    window.search.setText("right?")
    window.search_timer.timeout.emit()
    assert window._rows == [0]
    window.search.clear()
    assert window.save()
    got = annots.read(annots.open_pdf(sample))[0]
    assert got.status() == "Accepted" and got.tags == ("Ethics", "Aristotle") and len(got.replies) == 2
    window.pick([0], False)
    window.delete_reply(0)
    assert [r.contents for r in window.annotations[0].replies] == ["Status: Accepted"]


def test_find_and_highlight(window):
    window.find_dialog("line of")
    finder = window.finder
    finder.search()
    assert len(finder.matches) == 6
    finder.kind.setCurrentIndex(finder.kind.findData("underline"))
    finder._mark(finder.matches)
    assert [a.kind for a in window.annotations] == ["underline"] * 6
    assert window.marked_text(window.annotations[0]) == "line of"
    finder._mark(finder.matches)  # (not twice over the same place)
    assert len(window.annotations) == 6
    finder.regex.setChecked(True)
    finder.query.setText("page (")
    finder.search()
    assert finder.matches == [] and "not right" in finder.summary.text()
    finder.close()


def test_continuous_and_one_page(window):
    canvas = window.canvas
    assert canvas.continuous and sorted(canvas.pages) == [0, 1, 2]
    window.show_page(2)
    assert window.page == 2 and window.page_spin.value() == 3
    window.a_continuous.setChecked(False)
    assert list(canvas.pages) == [2]
    window.show_page(0)
    assert list(canvas.pages) == [0]
    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    assert window.annotations[0].page == 0
    window.a_continuous.setChecked(True)
    assert sorted(canvas.pages) == [0, 1, 2] and len(canvas.items_) == 1


def test_marker_and_pressure(window):
    from py_annotate.gui.canvas import PageCanvas

    window.set_tool("marker")
    drag(window, (100, 650), (150, 655), (200, 650))
    a = window.annotations[0]
    assert a.kind == "marker" and a.width == settings.STYLES["marker"].width and a.opacity < 1
    pressed = PageCanvas._pressed(dataclasses.replace(a, width=2), {"pressures": [1.0, 1.0]})
    assert pressed.width == 3.2  # (2 × (0.4 + 1.2))
    assert PageCanvas._pressed(a, {}) == a


def test_thumbnail_size(window):
    window.thumb_slider.setValue(200)
    assert window.thumb.height() == 200 and window.pages.iconSize().height() == 200
    QApplication.processEvents()


def test_print_and_exports(window, tmp_path, sample):
    from PySide6.QtGui import QPdfWriter

    from py_annotate.gui import printing

    window.set_tool("rect")
    drag(window, (100, 300), (250, 400))
    doc = printing.printable(sample, window.annotations)
    writer = QPdfWriter(str(tmp_path / "printed.pdf"))
    assert printing.render(writer, doc, [0, 1])
    import pymupdf

    assert pymupdf.open(tmp_path / "printed.pdf").page_count == 2
    window._ask_target = lambda title, suffix, ext="pdf": tmp_path / f"out{suffix}.{ext}"
    assert window.export_dialog("xfdf") and window.export_dialog("pdf")
    assert (tmp_path / "out-annotations.xfdf").read_text(encoding="utf-8").count("<square") == 1
    assert pymupdf.open(tmp_path / "out-summary.pdf").page_count == 1


def test_many_annotations_are_listed_at_once(window):
    import time

    many = [annots.Annotation("rect", i % 3, (10 + i % 50, 10, 30 + i % 50, 30), "#000000") for i in range(3000)]
    start = time.perf_counter()
    window.change(many)
    assert window.model.rowCount() == 3000 and time.perf_counter() - start < 5
