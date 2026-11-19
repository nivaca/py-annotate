"""Annotations exported, imported, kept for recovery; flattened copies and copies without them; the settings."""

from __future__ import annotations

import csv
import json

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
