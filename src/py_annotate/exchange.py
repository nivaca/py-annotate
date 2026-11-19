"""Annotations out of the document and into it: exported as JSON (all they
hold, to import them again), as a report in Markdown, or as a table (CSV);
imported from such a JSON file or from another copy of the PDF; and copies
of the document flattened (the annotations made part of the pages) or
without annotations.

The JSON file:

    {"format": "py-annotate", "version": 1,
     "document": {"file": "book.pdf", "pages": 120, "title": "...", "author": "..."},
     "annotations": [{"kind": "highlight", "page": 3, "rect": [...], "color": "#ffeb3b",
                      ..., "page_label": "iv", "marked_text": "..."}, ...]}

holds each annotation with the fields of annots.Annotation (pages from 0;
the image of a stamp in base64), and, to be read by people, the label of its
page and the text it marks.
"""

from __future__ import annotations

import base64
import csv
import dataclasses
import io
import json
import os
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import pymupdf

from . import annots
from .annots import KINDS, MARKUP, AnnotateError, Annotation
from .interface import ntr, tr

FORMAT = "py-annotate"
VERSION = 1


# --------------------------------------------------------------------- annotations as data

def to_data(a: Annotation) -> dict:
    data = dataclasses.asdict(a)
    data.pop("xref")
    data["image"] = base64.b64encode(a.image).decode("ascii") if a.image else ""
    return data


def from_data(data: dict, keep_xref: bool = False) -> Annotation | None:
    """The annotation of DATA (None if it isn't one). Its xref is kept only if KEEP_XREF."""
    if not isinstance(data, dict) or data.get("kind") not in KINDS:
        return None
    fields = {f.name: f for f in dataclasses.fields(Annotation)}
    values = {}
    try:
        for name, value in data.items():
            if name not in fields or (name == "xref" and not keep_xref):
                continue
            if name == "image":
                value = base64.b64decode(value) if value else b""
            elif name == "rect":
                value = tuple(float(v) for v in value)
                if len(value) != 4:
                    return None
            elif name == "quads":
                value = tuple(tuple(float(v) for v in q) for q in value)
            elif name == "paths":
                value = tuple(tuple((float(p[0]), float(p[1])) for p in path) for path in value)
            elif name == "ends":
                value = (str(value[0]), str(value[1]))
            elif name in ("opacity", "width", "font_size"):
                value = float(value)
            elif name in ("page", "xref"):
                value = int(value)
            elif name in ("dashed", "locked"):
                value = bool(value)
            else:
                value = str(value)
            values[name] = value
        return Annotation(**values)
    except (TypeError, ValueError, IndexError, KeyError):
        return None


def same_place(a: Annotation, b: Annotation) -> bool:
    """Whether A and B are the same annotation, made twice (or brought from two copies)."""
    return (a.kind, a.page, a.contents) == (b.kind, b.page, b.contents) and \
        all(abs(x - y) < 1.0 for x, y in zip(a.rect, b.rect))


def merged(have: list[Annotation], new: list[Annotation]) -> list[Annotation]:
    """Those of NEW that aren't in HAVE already."""
    out = []
    for a in new:
        if not any(same_place(a, b) for b in have + out):
            out.append(a)
    return out


# --------------------------------------------------------------------- what the document says of them

def page_label(doc: pymupdf.Document, page: int) -> str:
    """The label of PAGE (its printed number: iv, 12...), or its number from 1 if it has none."""
    try:
        label = doc[page].get_label()
    except (RuntimeError, ValueError, IndexError):
        label = ""
    return label or str(page + 1)


def marked_text(doc: pymupdf.Document, a: Annotation) -> str:
    if a.kind not in MARKUP or not 0 <= a.page < doc.page_count:
        return ""
    return annots.text_under(doc[a.page], list(a.quads))


def quotation(doc: pymupdf.Document, a: Annotation, name: str = "") -> str:
    """The text marked by A as a quotation, with where it is: “...” (book.pdf, p. 12)."""
    where = tr("p. {page}", page=page_label(doc, a.page))
    return f"“{marked_text(doc, a)}” ({name + ', ' if name else ''}{where})"


def _document_info(doc: pymupdf.Document, path: Path) -> dict:
    meta = doc.metadata or {}
    return {"file": path.name, "pages": doc.page_count, "title": meta.get("title", "") or "",
            "author": meta.get("author", "") or ""}


# --------------------------------------------------------------------- export

def _write_text(target: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(suffix=target.suffix, dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def export_json(doc: pymupdf.Document, path: Path, annotations: list[Annotation], target: Path) -> None:
    items = []
    for a in annotations:
        data = to_data(a)
        data["page_label"] = page_label(doc, a.page)
        data["marked_text"] = marked_text(doc, a)
        items.append(data)
    _write_text(target, json.dumps({"format": FORMAT, "version": VERSION, "document": _document_info(doc, path),
                                    "annotations": items}, ensure_ascii=False, indent=1) + "\n")


def import_json(source: Path) -> list[Annotation]:
    """The annotations of a JSON file of py-annotate (raises AnnotateError)."""
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise AnnotateError(tr("{path} cannot be read: {error}", path=source, error=e)) from None
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("annotations"), list):
        raise AnnotateError(tr("{path} is not a file of annotations of py-annotate", path=source))
    return [a for a in (from_data(d) for d in data["annotations"]) if a is not None]


def import_pdf(source: Path, password: str = "") -> list[Annotation]:
    """The annotations of another PDF (another copy of the document, annotated by someone else)."""
    doc = annots.open_pdf(source, password)
    try:
        return [dataclasses.replace(a, xref=0) for a in annots.read(doc)]
    finally:
        doc.close()


CSV_COLUMNS = ("page", "page_label", "kind", "color", "meaning", "author", "created", "modified", "marked_text",
               "contents")


def export_csv(doc: pymupdf.Document, annotations: list[Annotation], target: Path,
               meaning: Callable[[str], str] = lambda color: "") -> None:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CSV_COLUMNS)
    for a in sorted(annotations, key=lambda a: (a.page, a.rect[1], a.rect[0])):
        w.writerow([a.page + 1, page_label(doc, a.page), a.name(), a.color, meaning(a.color), a.author,
                    annots.date_text(a.created), annots.date_text(a.modified), marked_text(doc, a), a.contents])
    _write_text(target, out.getvalue())


def report(doc: pymupdf.Document, path: Path, annotations: list[Annotation],
           color_name: Callable[[str], str] = lambda color: color) -> str:
    """A report of ANNOTATIONS, in Markdown: how many there are of each kind,
    colour and author, then each of them, page by page, with the text it
    marks and its comment."""
    info = _document_info(doc, path)
    lines = ["# " + tr("Annotations of {name}", name=info["title"] or path.name), ""]
    pages = len({a.page for a in annotations})
    lines += [ntr("{count} annotation", "{count} annotations", len(annotations)) + ", "
              + ntr("on {count} page", "on {count} pages", pages) + ".", ""]
    for title, counter in ((tr("By kind"), Counter(a.name() for a in annotations)),
                           (tr("By colour"), Counter(color_name(a.color) for a in annotations)),
                           (tr("By author"), Counter(a.author or tr("(no author)") for a in annotations))):
        if not counter:
            continue
        lines += [f"## {title}", ""]
        lines += [f"* {name}: {count}" for name, count in counter.most_common()]
        lines.append("")
    page = None
    for a in sorted(annotations, key=lambda a: (a.page, a.rect[1], a.rect[0])):
        if a.page != page:
            page = a.page
            label = page_label(doc, page)
            heading = tr("Page {page}", page=page + 1) + (f" ({label})" if label != str(page + 1) else "")
            lines += [f"## {heading}", ""]
        head = f"* **{a.name()}** ({color_name(a.color)})"
        if a.author:
            head += ", " + tr("by {author}", author=a.author)
        when = annots.date_text(a.modified or a.created)
        if when:
            head += f", {when}"
        lines.append(head)
        text = marked_text(doc, a)
        if text:
            lines += ["", f"  > {text}"]
        if a.contents.strip():
            lines += [""] + ["  " + line for line in a.contents.strip().splitlines()]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def export_markdown(doc: pymupdf.Document, path: Path, annotations: list[Annotation], target: Path,
                    color_name: Callable[[str], str] = lambda color: color) -> None:
    _write_text(target, report(doc, path, annotations, color_name))


# --------------------------------------------------------------------- copies of the document

def save_flattened(source: Path, annotations: list[Annotation], target: Path, password: str = "") -> None:
    """A copy of SOURCE with ANNOTATIONS made part of its pages: they are seen,
    and printed, but are no longer annotations (raises AnnotateError)."""
    doc = annots.open_pdf(source, password)
    try:
        annots.apply(doc, annotations)
        doc.bake(annots=True, widgets=False)
        annots.save_doc(doc, target)
    except (OSError, RuntimeError, ValueError) as e:
        raise AnnotateError(tr("{path} cannot be written: {error}", path=target, error=e)) from None
    finally:
        doc.close()


def save_without(source: Path, target: Path, password: str = "") -> int:
    """A copy of SOURCE without any annotation (links and form fields stay).
    Returns how many were taken out (raises AnnotateError)."""
    doc = annots.open_pdf(source, password)
    try:
        count = 0
        for page in doc:
            for xref in [a.xref for a in page.annots() or [] if a.type[0] != pymupdf.PDF_ANNOT_POPUP]:
                page.delete_annot(page.load_annot(xref))
                count += 1
        annots.save_doc(doc, target)
    except (OSError, RuntimeError, ValueError) as e:
        raise AnnotateError(tr("{path} cannot be written: {error}", path=target, error=e)) from None
    finally:
        doc.close()
    return count
