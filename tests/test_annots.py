"""Annotations written to a PDF and read back from it."""

from __future__ import annotations

import dataclasses

import pymupdf
import pytest

from py_annotate import annots
from py_annotate.annots import Annotation


def lines(path, page: int) -> list[annots.Rect]:
    """The two lines of text of PAGE of the sample, as the page is shown."""
    found = annots.words(pymupdf.open(path)[page])
    return annots.text_rects(found, 0, len(found) - 1)


def one_of_each(path, page: int) -> list[Annotation]:
    first, second = lines(path, page)
    tri = ((60.0, 500.0), (160.0, 520.0), (110.0, 580.0))
    zig = ((300.0, 760.0), (340.0, 780.0), (380.0, 760.0))
    cloud = ((420.0, 600.0), (520.0, 600.0), (520.0, 680.0), (420.0, 680.0))
    return [
        Annotation("highlight", page, first, quads=(first,), contents="look"),
        Annotation("underline", page, second, "#1e88e5", quads=(second,)),
        Annotation("strikeout", page, first, "#e53935", quads=(first,)),
        Annotation("squiggly", page, annots.union([first, second]), "#43a047", quads=(first, second)),
        Annotation("caret", page, (500, 150) + tuple(map(sum, zip((500, 150), annots.shown_size(90 if page == 2 else 0, annots.CARET_SIZE)))),
                   "#1e88e5", contents="insert this"),
        Annotation("note", page, (300, 200, 316, 216), "#ffd54f", contents="A note", author="Me", icon="Key"),
        Annotation("freetext", page, (300, 300, 480, 340), "#0000ff", fill="#ffff00", contents="Some text",
                   font_size=14, width=0, font="tiro", align="center"),
        Annotation("freetext", page, (300, 250, 480, 290), "#000000", contents="Bordered", width=1, dashed=True,
                   font="cour"),
        Annotation("callout", page, (380, 350, 540, 390), "#000000", fill="#ffffff", contents="Look here", width=0,
                   paths=(((320.0, 420.0),),), ends=("None", "ClosedArrow")),
        Annotation("area", page, (60, 440, 200, 480), "#ffeb3b", fill="#ffeb3b", opacity=0.4, width=0),
        Annotation("rect", page, (100, 400, 200, 430), "#ff0000", fill="#00ff00", width=2, opacity=0.5,
                   dashed=True, locked=True),
        Annotation("ellipse", page, (250, 400, 350, 460), "#ff0000", width=3),
        Annotation("polygon", page, annots.frame("polygon", (tri,), 1.5), "#000000", fill="#c0c0c0", paths=(tri,)),
        Annotation("cloud", page, annots.frame("cloud", (cloud,), 1.5), "#e53935", paths=(cloud,)),
        Annotation("line", page, annots.frame("line", (((100, 600), (300, 650)),), 2), "#000000", width=2,
                   paths=(((100, 600), (300, 650)),), ends=("Circle", "Square")),
        Annotation("arrow", page, annots.frame("arrow", (((100, 700), (300, 700)),), 2), "#000000", width=2,
                   paths=(((100, 700), (300, 700)),), ends=("OpenArrow", "OpenArrow")),
        Annotation("polyline", page, annots.frame("polyline", (zig,), 1.5), "#000000", paths=(zig,),
                   ends=("None", "ClosedArrow")),
        Annotation("ink", page, annots.frame("ink", (((100, 740), (120, 760), (150, 730)),), 1.5), "#1e88e5",
                   paths=(((100, 740), (120, 760), (150, 730)),)),
        Annotation("stamp", page, (300, 480, 460, 520), "#000000", stamp="Approved", contents="ok"),
    ]


def close(a, b, tolerance=1.5):
    return all(abs(x - y) <= tolerance for x, y in zip(a, b, strict=True))


@pytest.mark.parametrize("page", [0, 2])  # (page 3 is turned)
def test_round_trip(sample, tmp_path, page):
    wanted = one_of_each(sample, page)
    target = tmp_path / "out.pdf"
    assert annots.write(sample, wanted, target) == len(wanted)
    doc = annots.open_pdf(target)
    got = annots.read(doc)
    assert [a.kind for a in got] == [a.kind for a in wanted]
    for w, g in zip(wanted, got):
        assert g.page == page and g.xref and g.created and g.modified
        assert g.color == w.color or w.kind == "stamp", w.kind  # (a standard stamp has its own)
        assert g.fill == w.fill, w.kind
        assert g.contents == w.contents and g.author == w.author
        assert abs(g.opacity - w.opacity) < 0.01
        assert (g.dashed, g.locked, g.ends) == (w.dashed, w.locked, w.ends), w.kind
        if w.kind in annots.MARKUP:
            assert all(close(a, b) for a, b in zip(g.quads, w.quads))
        elif w.paths and w.kind != "callout":
            assert all(close(p, q, 0.5) for path_g, path_w in zip(g.paths, w.paths) for p, q in zip(path_g, path_w))
            assert g.width == w.width
        elif w.kind == "stamp":
            assert g.stamp == "Approved" and g.image.startswith(b"\x89PNG")
            # (MuPDF gives a standard stamp its own proportions, around the same centre)
            centre = lambda r: ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
            assert close(centre(g.rect), centre(w.rect), 3)
        else:
            assert close(g.rect, w.rect), (w.kind, g.rect, w.rect)
        if w.kind in annots.TEXTUAL:
            assert (g.font_size, g.font, g.align, g.width) == (w.font_size, w.font, w.align, w.width)
        if w.kind == "callout":
            assert close(g.paths[0][0], w.paths[0][0], 0.5)
        if w.kind == "note":
            assert g.icon == "Key"
    assert annots.text_under(doc[page], got[0].quads) == f"First line of page {page + 1}"


def test_only_changes_are_written(sample, tmp_path):
    first = tmp_path / "first.pdf"
    annots.write(sample, one_of_each(sample, 0), first)
    got = annots.read(annots.open_pdf(first))
    xrefs = {a.kind: a.xref for a in got}
    stamp = next(a for a in got if a.kind == "stamp")
    # the rectangle moved, the note deleted, a new ellipse; the rest as it was
    changed = [annots.moved(a, 10, 0) if a.kind in ("rect", "stamp") else a for a in got if a.kind != "note"]
    changed.append(Annotation("ellipse", 1, (10, 10, 50, 50), "#000000"))
    second = tmp_path / "second.pdf"
    assert annots.write(first, changed, second) == 3
    again = annots.read(annots.open_pdf(second))
    kinds = [a.kind for a in again]
    assert "note" not in kinds and kinds.count("ellipse") == 2
    assert {a.kind: a.xref for a in again if a.page == 0}["highlight"] == xrefs["highlight"]  # (untouched)
    rect = next(a for a in again if a.kind == "rect")
    assert close(rect.rect, (110, 400, 210, 430))
    moved_stamp = next(a for a in again if a.kind == "stamp")
    assert moved_stamp.xref == stamp.xref and close(moved_stamp.rect[:2], (stamp.rect[0] + 10, stamp.rect[1]))


def test_other_annotations_are_kept(sample, tmp_path):
    doc = pymupdf.open(sample)
    doc[0].add_file_annot((300, 300), b"data", "data.txt")
    doc.save(tmp_path / "stamped.pdf")
    annots.write(tmp_path / "stamped.pdf", [], tmp_path / "out.pdf")
    out = annots.open_pdf(tmp_path / "out.pdf")
    assert [a.type[1] for a in out[0].annots()] == ["FileAttachment"]
    assert annots.read(out) == []


def test_remove_editable(sample, tmp_path):
    annots.write(sample, one_of_each(sample, 0), tmp_path / "out.pdf")
    doc = annots.open_pdf(tmp_path / "out.pdf")
    annots.remove_editable(doc)
    assert list(doc[0].annots()) == []


def test_fitted():
    a = Annotation("ink", 0, (0, 0, 10, 10), paths=(((0, 0), (10, 10)),))
    b = annots.fitted(a, (10, 10, 30, 20))
    assert b.paths == (((10, 10), (30, 20)),) and b.rect == (10, 10, 30, 20)
    assert annots.moved(b, 5, -5).paths == (((15, 5), (35, 15)),)
    assert dataclasses.replace(b, xref=3) != b


def test_password(tmp_path):
    path = tmp_path / "locked.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="secret")
    with pytest.raises(annots.PasswordError):
        annots.open_pdf(path)
    annots.write(path, [Annotation("rect", 0, (10, 10, 50, 50), "#000000")], path, "secret")
    again = annots.open_pdf(path, "secret")
    assert again.needs_pass and [a.kind for a in annots.read(again)] == ["rect"]
