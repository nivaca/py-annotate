"""Annotations exported, imported, kept for recovery; flattened copies and copies without them; the settings."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pymupdf
from test_annots import one_of_each

from py_annotate import annots, exchange, recovery, settings
from py_annotate.annots import Annotation


def test_json_round_trip(sample, tmp_path):
    wanted = one_of_each(sample, 0)
    doc = annots.open_pdf(sample)
    target = tmp_path / "out.json"
    exchange.export_json(doc, sample, wanted, target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["document"]["pages"] == 3 and data["annotations"][0]["marked_text"] == "First line of page 1"
    assert exchange.import_json(target) == wanted


def test_import_from_another_copy(sample, tmp_path):
    other = tmp_path / "other.pdf"
    annots.write(sample, [Annotation("rect", 1, (10, 10, 60, 60), "#000000", author="Reviewer B")], other)
    found = exchange.import_pdf(other)
    assert [(a.kind, a.author, a.xref) for a in found] == [("rect", "Reviewer B", 0)]
    assert exchange.merged(found, exchange.import_pdf(other)) == []  # (already there)


def test_report_and_csv(sample, tmp_path):
    wanted = one_of_each(sample, 0)
    doc = annots.open_pdf(sample)
    text = exchange.report(doc, sample, wanted)
    assert text.startswith("# Annotations of sample.pdf") and "> First line of page 1" in text
    assert "* Highlight: 1" in text
    exchange.export_csv(doc, wanted, tmp_path / "out.csv")
    rows = list(csv.reader((tmp_path / "out.csv").open(encoding="utf-8")))
    assert rows[0][0] == "page" and len(rows) == len(wanted) + 1
    assert exchange.quotation(doc, wanted[0], "sample.pdf") == "“First line of page 1” (sample.pdf, p. 1)"


def test_flattened_and_without(sample, tmp_path):
    flat = tmp_path / "flat.pdf"
    exchange.save_flattened(sample, [Annotation("rect", 0, (10, 10, 60, 60), "#ff0000", width=4)], flat)
    doc = pymupdf.open(flat)
    assert list(doc[0].annots()) == [] and doc[0].get_drawings()  # (drawn on the page now)
    annotated = tmp_path / "annotated.pdf"
    annots.write(sample, one_of_each(sample, 0), annotated)
    assert exchange.save_without(annotated, tmp_path / "bare.pdf") >= len(one_of_each(sample, 0))
    assert list(pymupdf.open(tmp_path / "bare.pdf")[0].annots()) == []


def test_recovery(sample):
    kept = [Annotation("rect", 0, (10, 10, 60, 60), "#000000", xref=12)]
    recovery.keep(sample, kept)
    when, found = recovery.find(sample)
    assert found == kept and when
    sample.write_bytes(sample.read_bytes() + b"\n")  # (the file changed: the copy is of no use)
    assert recovery.find(sample) is None
    recovery.discard(sample)


def test_settings_round_trip():
    prefs = settings.load()
    assert prefs == settings.DEFAULTS
    style = settings.Style("#123456", fill="#abcdef", width=3.0, font="tiro", start="Circle", end="ClosedArrow",
                           dashed=True, sticky=False, show="properties")
    prefs = prefs.with_style("line", style)
    prefs = settings.Settings(author="Me", styles=prefs.styles, palette=(("#ffeb3b", "Key ideas"),)
                              + prefs.palette[1:], shortcuts=tuple((k, "Ctrl+Alt+H" if k == "highlight" else v) for k, v in prefs.shortcuts),
                              autosave=5)
    settings.save(prefs)
    again = settings.load()
    line = again.style("line")
    # (what a line has no use for is not kept: its fill and font)
    assert (line.color, line.width, line.start, line.end, line.dashed, line.sticky, line.show) == \
        ("#123456", 3.0, "Circle", "ClosedArrow", True, False, "properties")
    assert line.fill == "" and line.font == "helv"
    assert again.author == "Me" and again.autosave == 5 and again.palette[0] == ("#ffeb3b", "Key ideas")
    assert again.shortcut("highlight") == "Ctrl+Alt+H"


def test_conform_missing(sample, tmp_path, monkeypatch):
    from py_annotate import conform

    monkeypatch.setattr(conform, "command", lambda path=None: None)
    import pytest

    with pytest.raises(conform.ConformError):
        conform.convert(sample, tmp_path / "x.pdf", "a-2b")


def test_finding_pdfconform(tmp_path, monkeypatch):
    from py_annotate import conform

    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # (the home folder on Windows)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")  # (as a session started from the desktop menu may have it)
    assert conform.find() is None and not conform.available()
    script = home / "bin" / "pdf2iso"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    # (on Windows a script is run by Python: every file there seems executable)
    assert conform.find() == script and conform.command()[-1] == str(script)
    assert sys.platform == "win32" or conform.command() == [str(script)]
    other = tmp_path / "elsewhere.py"  # (a script that can't be run by itself: run with python3)
    other.write_text("print()\n")
    settings.save(settings.Settings(pdfconform=str(other)))
    cmd = conform.command()
    assert cmd[-1] == str(other) and Path(cmd[0]).stem.startswith(("python", "py"))
    settings.save(settings.Settings(pdfconform=str(tmp_path / "missing")))
    assert conform.command() is None


def test_partly_flattened(sample, tmp_path):
    tri = ((60.0, 500.0), (160.0, 520.0), (110.0, 580.0))
    wanted = [Annotation("polygon", 0, annots.frame("polygon", (tri,), 1.5), "#000000", paths=(tri,)),
              Annotation("rect", 0, (10, 10, 60, 60), "#ff0000")]
    target = tmp_path / "out.pdf"
    exchange.save_partly_flattened(sample, wanted, target, kinds={"polygon"})
    doc = annots.open_pdf(target)
    assert [a.kind for a in annots.read(doc)] == ["rect"] and doc[0].get_drawings()
    assert exchange.kinds_lost(wanted, target) == {"polygon": 1}


import dataclasses  # noqa: E402

import pytest  # noqa: E402


@pytest.mark.parametrize("page", [0, 2])
def test_xfdf_round_trip(sample, tmp_path, page):
    wanted = one_of_each(sample, page)
    wanted[0] = dataclasses.replace(wanted[0], replies=(annots.Reply("B", "Why?"),
                                                        annots.Reply("C", "Agreed", state="Accepted")))
    doc = annots.open_pdf(sample)
    target = tmp_path / "out.xfdf"
    exchange.export_xfdf(doc, sample, wanted, target)
    text = target.read_text(encoding="utf-8")
    assert text.startswith('<?xml') and "<highlight" in text and 'inreplyto="py-annotate-1"' in text
    got = exchange.import_xfdf(doc, target)
    assert [a.kind for a in got] == [a.kind for a in wanted]
    for w, g in zip(wanted, got):
        assert annots.same(dataclasses.replace(w, image=b""), dataclasses.replace(g, image=b""), tolerance=1.5), \
            (w.kind, w, g)
    assert [(r.author, r.contents, r.state) for r in got[0].replies] == [("B", "Why?", ""),
                                                                         ("C", "Agreed", "Accepted")]


def test_summary(sample, tmp_path):
    wanted = one_of_each(sample, 0)[:3] + [Annotation("note", 1, (300, 200, 316, 216), "#ffd54f",
                                                      contents="See page two", author="B")]
    target = tmp_path / "summary.pdf"
    pages = exchange.save_summary(sample, wanted, target)
    doc = pymupdf.open(target)
    assert pages == doc.page_count == 2
    text = doc[0].get_text()
    assert "Page 1" in text and "1. Highlight" in text and "First line of page 1" in text and "look" in text
    assert "See page two" in doc[1].get_text() and doc[0].rect.width > 595
