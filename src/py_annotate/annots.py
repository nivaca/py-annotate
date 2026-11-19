"""Annotations: what py-annotate adds to the pages of a PDF, read from it and
written to it.

An annotation is kept as an Annotation, measured in points from the top left
corner of the page as it is shown (that is, with the page's rotation
applied), like everything the window shows. The kinds are:

* text markup, over lines of text: ``highlight``, ``underline``,
  ``strikeout``, ``squiggly`` (one rectangle in ``quads`` for each line),
  and ``caret``, a mark where text is to be inserted;
* ``note``: a sticky note, an icon whose text opens in the viewer;
* ``freetext``: a text written on the page, in a box; ``callout``: the same,
  with a line pointing at a place (``paths``: that place);
* shapes: ``area`` (a highlight over a region, not over text), ``rect``,
  ``ellipse``, ``polygon``, ``cloud`` (a polygon with a cloudy border),
  ``line``, ``arrow``, ``polyline``, and ``ink`` (drawn by hand; its strokes
  in ``paths``);
* ``stamp``: a rubber stamp, standard (``stamp``: its name) or of an image
  (``image``, which also keeps the look of every stamp, for showing it).

The annotations of these kinds that a document already has are read into
the list too (all but replies to other annotations), and can be changed or
deleted. Saving rewrites only those that changed (a stamp is changed where
it is); an annotation left as it was is not touched, nor are those of other
kinds (links, file attachments, sounds, form fields...).
"""

from __future__ import annotations

import dataclasses
import datetime
import os
import re
import tempfile
from pathlib import Path

import pymupdf

from .interface import N_, tr

Rect = tuple[float, float, float, float]  # x0, y0, x1, y1
Point = tuple[float, float]

KINDS = ("highlight", "underline", "strikeout", "squiggly", "caret", "note", "freetext", "callout", "area", "rect",
         "ellipse", "polygon", "cloud", "line", "arrow", "polyline", "ink", "stamp")
NAMES = {"highlight": N_("Highlight"), "underline": N_("Underline"), "strikeout": N_("Strikeout"),
         "squiggly": N_("Squiggly underline"), "caret": N_("Insert text"), "note": N_("Note"),
         "freetext": N_("Text box"), "callout": N_("Callout"), "area": N_("Area highlight"),
         "rect": N_("Rectangle"), "ellipse": N_("Ellipse"), "polygon": N_("Polygon"), "cloud": N_("Cloud"),
         "line": N_("Line"), "arrow": N_("Arrow"), "polyline": N_("Polyline"), "ink": N_("Freehand"),
         "stamp": N_("Stamp")}
MARKUP = ("highlight", "underline", "strikeout", "squiggly")  # (over text: neither moved nor resized)
FIXED = ("note", "caret")  # (of a size of their own: moved, not resized)
TEXTUAL = ("freetext", "callout")  # (with a font)
FILLED = ("freetext", "callout", "area", "rect", "ellipse", "polygon", "cloud")  # (those with a fill)
STROKED = ("freetext", "callout", "rect", "ellipse", "polygon", "cloud", "line", "arrow", "polyline", "ink")
DASHABLE = ("freetext", "callout", "rect", "ellipse", "polygon", "line", "arrow", "polyline")
ENDED = ("line", "arrow", "polyline", "callout")  # (with ends: arrowheads...)
VERTICES = ("polygon", "cloud", "polyline", "line", "arrow")  # (whose points can be dragged one by one)
RESIZABLE = ("freetext", "callout", "area", "rect", "ellipse", "polygon", "cloud", "line", "arrow", "polyline",
             "ink", "stamp")
NOTE_SIZE = 16.0  # points: the side of a note's icon (MuPDF makes them all of this size)
CARET_SIZE = (20.0, 14.0)  # points: the size of a caret's mark (MuPDF's)

FONTS = {"helv": N_("Helvetica (sans serif)"), "tiro": N_("Times (serif)"), "cour": N_("Courier (monospaced)")}
_DA_FONTS = {"helv": "helv", "tiro": "tiro", "times": "tiro", "cour": "cour", "courier": "cour"}
ALIGNS = {"left": N_("Left"), "center": N_("Centre"), "right": N_("Right")}
ICONS = {"Note": N_("Note"), "Comment": N_("Comment"), "Key": N_("Key"), "Help": N_("Help"),
         "NewParagraph": N_("New paragraph"), "Paragraph": N_("Paragraph"), "Insert": N_("Insert")}
ENDS = {"None": N_("None"), "OpenArrow": N_("Open arrow"), "ClosedArrow": N_("Closed arrow"),
        "Circle": N_("Circle"), "Square": N_("Square"), "Diamond": N_("Diamond"), "Butt": N_("Bar"),
        "Slash": N_("Slash"), "ROpenArrow": N_("Reversed open arrow"), "RClosedArrow": N_("Reversed closed arrow")}
_END_CODES = {"None": pymupdf.PDF_ANNOT_LE_NONE, "OpenArrow": pymupdf.PDF_ANNOT_LE_OPEN_ARROW,
              "ClosedArrow": pymupdf.PDF_ANNOT_LE_CLOSED_ARROW, "Circle": pymupdf.PDF_ANNOT_LE_CIRCLE,
              "Square": pymupdf.PDF_ANNOT_LE_SQUARE, "Diamond": pymupdf.PDF_ANNOT_LE_DIAMOND,
              "Butt": pymupdf.PDF_ANNOT_LE_BUTT, "Slash": pymupdf.PDF_ANNOT_LE_SLASH,
              "ROpenArrow": pymupdf.PDF_ANNOT_LE_R_OPEN_ARROW, "RClosedArrow": pymupdf.PDF_ANNOT_LE_R_CLOSED_ARROW}
_END_NAMES = {code: name for name, code in _END_CODES.items()}
STAMPS = {"Approved": N_("Approved"), "AsIs": N_("As is"), "Confidential": N_("Confidential"),
          "Departmental": N_("Departmental"), "Experimental": N_("Experimental"), "Expired": N_("Expired"),
          "Final": N_("Final"), "ForComment": N_("For comment"), "ForPublicRelease": N_("For public release"),
          "NotApproved": N_("Not approved"), "NotForPublicRelease": N_("Not for public release"),
          "Sold": N_("Sold"), "TopSecret": N_("Top secret"), "Draft": N_("Draft")}  # (in MuPDF's order)
AREA_SUBJECT = "Area highlight"  # (the /Subj that tells an area highlight from a rectangle)
DASHES = (3, 3)

_TYPES = {pymupdf.PDF_ANNOT_HIGHLIGHT: "highlight", pymupdf.PDF_ANNOT_UNDERLINE: "underline",
          pymupdf.PDF_ANNOT_STRIKE_OUT: "strikeout", pymupdf.PDF_ANNOT_SQUIGGLY: "squiggly",
          pymupdf.PDF_ANNOT_CARET: "caret", pymupdf.PDF_ANNOT_TEXT: "note",
          pymupdf.PDF_ANNOT_FREE_TEXT: "freetext", pymupdf.PDF_ANNOT_SQUARE: "rect",
          pymupdf.PDF_ANNOT_CIRCLE: "ellipse", pymupdf.PDF_ANNOT_POLYGON: "polygon",
          pymupdf.PDF_ANNOT_POLY_LINE: "polyline", pymupdf.PDF_ANNOT_LINE: "line", pymupdf.PDF_ANNOT_INK: "ink",
          pymupdf.PDF_ANNOT_STAMP: "stamp"}


@dataclasses.dataclass(frozen=True)
class Annotation:
    kind: str
    page: int  # 0-based
    rect: Rect  # where it is: its frame (of a callout, its box), which moving and resizing change
    color: str = "#ffeb3b"  # of the mark, the line, the note, or the text of a text box
    fill: str = ""  # of the inside of a shape or a text box; '' for none
    opacity: float = 1.0  # from 0 to 1
    width: float = 1.5  # of the line of a shape, or the border of a text box (0: none), in points
    contents: str = ""  # the comment, or the text of a note or a text box
    author: str = ""
    font_size: float = 12.0  # of a text box
    quads: tuple[Rect, ...] = ()  # text markup: a rectangle for each line
    # line, arrow, polyline, polygon and cloud: one path of their points; ink: its strokes;
    # callout: one path of one point, where it points
    paths: tuple[tuple[Point, ...], ...] = ()
    font: str = "helv"  # of a text box: see FONTS
    align: str = "left"  # of the text of a text box
    icon: str = "Note"  # of a note: see ICONS
    ends: tuple[str, str] = ("None", "None")  # of a line (or callout: its second, at the place pointed): see ENDS
    dashed: bool = False
    locked: bool = False  # (the PDF's flag: neither moved, resized nor deleted)
    stamp: str = ""  # a standard stamp (see STAMPS); '' for one of an image
    image: bytes = b""  # a stamp's look, as a PNG
    created: str = ""  # PDF dates (D:20261119...): '' if unknown, or not yet written
    modified: str = ""
    xref: int = 0  # of the annotation in the document it was read from; 0 if new

    def name(self) -> str:
        return tr(NAMES[self.kind])


class AnnotateError(Exception):
    """A document that cannot be read or written."""


class PasswordError(AnnotateError):
    """A document whose password is missing or wrong."""


# --------------------------------------------------------------------- geometry

def normalized(rect: Rect) -> Rect:
    x0, y0, x1, y1 = rect
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def bounds(points: list[Point], pad: float = 0.0) -> Rect:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def union(rects) -> Rect:
    rects = list(rects)
    return (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects),
            max(r[3] for r in rects))


def _r(value: float) -> float:
    return round(value, 2)


def frame(kind: str, paths, width: float) -> Rect:
    """The frame of a line, an arrow, a polygon or a drawing: around its points, with room for the line."""
    pad = max(width, 2.0) + {"arrow": 4.0, "cloud": 6.0}.get(kind, 0.0)
    return tuple(_r(v) for v in bounds([p for path in paths for p in path], pad))


def fitted(a: Annotation, rect: Rect) -> Annotation:
    """A, moved and stretched so that its frame becomes RECT."""
    x0, y0, x1, y1 = a.rect
    n0, m0, n1, m1 = normalized(rect)
    sx = (n1 - n0) / (x1 - x0) if x1 - x0 > 1e-6 else 1.0
    sy = (m1 - m0) / (y1 - y0) if y1 - y0 > 1e-6 else 1.0

    def point(p: Point) -> Point:
        return _r(n0 + (p[0] - x0) * sx), _r(m0 + (p[1] - y0) * sy)

    def box(r: Rect) -> Rect:
        return point((r[0], r[1])) + point((r[2], r[3]))

    paths = a.paths if a.kind == "callout" and (sx, sy) != (1.0, 1.0) else \
        tuple(tuple(point(p) for p in path) for path in a.paths)
    return dataclasses.replace(a, rect=(_r(n0), _r(m0), _r(n1), _r(m1)), quads=tuple(box(q) for q in a.quads),
                               paths=paths)


def moved(a: Annotation, dx: float, dy: float) -> Annotation:
    x0, y0, x1, y1 = a.rect
    return fitted(a, (x0 + dx, y0 + dy, x1 + dx, y1 + dy))


def with_vertex(a: Annotation, index: int, point: Point) -> Annotation:
    """A with its point INDEX (of its first path) at POINT; for a callout, the place it points at."""
    path = list(a.paths[0])
    path[index] = (_r(point[0]), _r(point[1]))
    paths = (tuple(path),) + a.paths[1:]
    if a.kind == "callout":
        return dataclasses.replace(a, paths=paths)
    return dataclasses.replace(a, paths=paths, rect=frame(a.kind, paths, a.width))


def shown_size(rotation: int, size: tuple[float, float]) -> tuple[float, float]:
    """SIZE (of a caret, made by MuPDF along the page), as a page turned ROTATION degrees shows it."""
    return (size[1], size[0]) if rotation % 180 else size


def anchor(box: Rect, point: Point) -> Point:
    """Where a callout's line leaves its BOX, going to POINT: the middle of the side nearest to it."""
    x0, y0, x1, y1 = box
    sides = [((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1), (x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)]
    return min(sides, key=lambda s: (s[0] - point[0]) ** 2 + (s[1] - point[1]) ** 2)


# --------------------------------------------------------------------- colours and dates

def rgb(color: str) -> tuple[float, float, float]:
    """'#rrggbb' as PyMuPDF's (r, g, b), each from 0 to 1."""
    c = color.lstrip("#")
    if len(c) != 6:
        raise ValueError(color)
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def hex_color(values) -> str:
    """A colour of a PDF (grey, RGB or CMYK, from 0 to 1) as '#rrggbb'; '' for none."""
    values = [min(max(float(v), 0.0), 1.0) for v in values or []]
    if len(values) == 1:
        values = values * 3
    elif len(values) == 4:
        c, m, y, k = values
        values = [(1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)]
    elif len(values) != 3:
        return ""
    return "#" + "".join(f"{round(v * 255):02x}" for v in values)


PDF_DATE = re.compile(r"D?:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?")


def now() -> str:
    """The time of now, as a PDF date."""
    return pymupdf.get_pdf_now()


def date_value(date: str) -> datetime.datetime | None:
    """A PDF date (D:20261119143000...) as a datetime (local, without its zone); None if it isn't one."""
    m = PDF_DATE.match(date.strip()) if date else None
    if not m:
        return None
    parts = [int(g) if g else d for g, d in zip(m.groups(), (0, 1, 1, 0, 0, 0))]
    try:
        return datetime.datetime(*parts)
    except ValueError:
        return None


def date_text(date: str) -> str:
    """A PDF date as 2026-11-19 14:30 ('' if there is none)."""
    value = date_value(date)
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


# --------------------------------------------------------------------- documents

def open_pdf(path: Path, password: str = "") -> pymupdf.Document:
    """The PDF at PATH, opened with PASSWORD if it needs one (raises AnnotateError)."""
    try:
        doc = pymupdf.open(path)
    except (pymupdf.FileNotFoundError, pymupdf.FileDataError, RuntimeError) as e:
        raise AnnotateError(tr("{path} cannot be read as a PDF: {error}", path=path, error=e)) from None
    if not doc.is_pdf:
        doc.close()
        raise AnnotateError(tr("{path} is not a PDF", path=path))
    if doc.needs_pass and not doc.authenticate(password):
        doc.close()
        raise PasswordError(tr("{path} is protected by a password", path=path))
    return doc


def kind_of(doc: pymupdf.Document, annot: pymupdf.Annot) -> str | None:
    """The kind of ANNOT, if py-annotate can edit it (None for the others, and for replies)."""
    kind = _TYPES.get(annot.type[0])
    if kind is None or doc.xref_get_key(annot.xref, "IRT")[0] != "null":
        return None
    if kind == "line" and any(_END_NAMES.get(end, "").endswith("Arrow") for end in annot.line_ends or ()):
        return "arrow"
    if kind == "freetext" and doc.xref_get_key(annot.xref, "IT")[1] == "/FreeTextCallout":
        return "callout"
    if kind == "rect" and (annot.info or {}).get("subject") == AREA_SUBJECT:
        return "area"
    if kind == "polygon" and ((annot.border or {}).get("clouds") or 0) > 0:
        return "cloud"
    return kind


def _shown_rect(page: pymupdf.Page, rect) -> Rect:
    r = (pymupdf.Rect(rect) * page.rotation_matrix).normalize()
    return _r(r.x0), _r(r.y0), _r(r.x1), _r(r.y1)


def _shown_point(page: pymupdf.Page, point) -> Point:
    p = pymupdf.Point(point) * page.rotation_matrix
    return _r(p.x), _r(p.y)


def _real_rect(page: pymupdf.Page, rect: Rect) -> pymupdf.Rect:
    return (pymupdf.Rect(normalized(rect)) * page.derotation_matrix).normalize()


def _real_point(page: pymupdf.Page, point: Point) -> pymupdf.Point:
    return pymupdf.Point(point) * page.derotation_matrix


DA_SIZE = re.compile(r"([\d.]+)\s+Tf")
DA_FONT = re.compile(r"/([A-Za-z]+)")
DA_COLOR = re.compile(r"((?:[\d.]+\s+){1,4})(g|rg|k)\b")


def _text_style(doc: pymupdf.Document, xref: int) -> tuple[str, float, str]:
    """The colour, the size and the font of the text of a text box, from its /DA."""
    kind, da = doc.xref_get_key(xref, "DA")
    if kind != "string":
        return "#000000", 12.0, "helv"
    size = DA_SIZE.search(da)
    color = DA_COLOR.search(da)
    font = DA_FONT.search(da)
    return ((hex_color(color[1].split()) if color else "#000000") or "#000000",
            (float(size[1]) or 12.0) if size else 12.0,
            _DA_FONTS.get(font[1].lower(), "helv") if font else "helv")


def _stamp_image(annot: pymupdf.Annot) -> bytes:
    """How the stamp ANNOT looks, as a PNG (for showing it: the window draws it)."""
    try:
        return annot.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=True).tobytes("png")
    except (RuntimeError, ValueError):
        return b""


_STANDARD: dict[str, tuple[bytes, tuple[float, float]]] = {}


def standard_stamp(name: str) -> tuple[bytes, tuple[float, float]]:
    """How the standard stamp NAME looks (a PNG), and its usual size in points."""
    if name not in _STANDARD:
        doc = pymupdf.open()
        page = doc.new_page()
        annot = page.add_stamp_annot(pymupdf.Rect(0, 0, 160, 50), stamp=list(STAMPS).index(name))
        _STANDARD[name] = _stamp_image(annot), (_r(annot.rect.width), _r(annot.rect.height))
        doc.close()
    return _STANDARD[name]


def read_annotation(doc: pymupdf.Document, page: pymupdf.Page, annot: pymupdf.Annot) -> Annotation | None:
    kind = kind_of(doc, annot)
    if kind is None:
        return None
    colors = annot.colors or {}
    stroke, fill = hex_color(colors.get("stroke")), hex_color(colors.get("fill"))
    border = annot.border or {}
    width = border.get("width", -1)
    width = width if width is not None and width >= 0 else 1.0
    opacity = annot.opacity if annot.opacity is not None and 0 <= annot.opacity <= 1 else 1.0
    info = annot.info or {}
    ends = tuple(_END_NAMES.get(e, "None") for e in (annot.line_ends or (0, 0)))
    fields = {"kind": kind, "page": page.number, "opacity": round(opacity, 3), "width": _r(width),
              "contents": info.get("content", "") or "", "author": info.get("title", "") or "",
              "created": info.get("creationDate", "") or "", "modified": info.get("modDate", "") or "",
              "locked": bool(annot.flags & pymupdf.PDF_ANNOT_IS_LOCKED),
              "dashed": bool(border.get("dashes")) or border.get("style") == "D", "xref": annot.xref}
    vertices = annot.vertices or []
    if kind in MARKUP:
        quads = [_shown_rect(page, bounds(vertices[i:i + 4])) for i in range(0, len(vertices) - 3, 4)]
        if not quads:
            quads = [_shown_rect(page, annot.rect)]
        return Annotation(rect=union(quads), color=stroke or "#ffeb3b", quads=tuple(quads), **fields)
    if kind in TEXTUAL:
        color, size, font = _text_style(doc, annot.xref)
        r = pymupdf.Rect(annot.rect)
        rd = doc.xref_get_key(annot.xref, "RD")
        delta = [float(v) for v in rd[1].strip("[]").split()] if rd[0] == "array" else []
        if len(delta) == 4 and any(delta):
            # (the box, inside the rectangle that holds the box and the line; MuPDF's /RD gives
            # what is left out on the left, below, on the right and above the box)
            box = pymupdf.Rect(r.x0 + delta[0], r.y0 + delta[3], r.x1 - delta[2], r.y1 - delta[1])
            r = box if not box.is_empty else r
        elif width:  # (the rectangle holds the border, half of it outside the box)
            r = pymupdf.Rect(r.x0 + width / 2, r.y0 + width / 2, r.x1 - width / 2, r.y1 - width / 2)
        q = doc.xref_get_key(annot.xref, "Q")
        align = {"1": "center", "2": "right"}.get(q[1], "left") if q[0] == "int" else "left"
        paths = ()
        if kind == "callout":
            le = doc.xref_get_key(annot.xref, "LE")[1].lstrip("/")
            ends = ("None", le if le in _END_CODES else "None")
            if vertices:
                paths = ((_shown_point(page, vertices[0]),),)
            else:
                kind, fields["kind"] = "freetext", "freetext"
        # (a text box keeps its fill in /C, which PyMuPDF gives as its 'stroke')
        return Annotation(rect=_shown_rect(page, r), color=color, fill=stroke, font_size=_r(size), font=font,
                          align=align, paths=paths, ends=ends if kind == "callout" else ("None", "None"),
                          **fields)
    if kind in ("rect", "ellipse", "area"):  # (its rectangle holds the line, half of it outside the shape)
        r = pymupdf.Rect(annot.rect)
        half = width / 2
        if r.width > 2 * half and r.height > 2 * half:
            r = pymupdf.Rect(r.x0 + half, r.y0 + half, r.x1 - half, r.y1 - half)
        return Annotation(rect=_shown_rect(page, r), color=stroke or "#000000", fill=fill, **fields)
    if kind in ("line", "arrow", "polyline", "polygon", "cloud", "ink"):
        if kind == "ink":
            paths = tuple(tuple(_shown_point(page, p) for p in stroke_) for stroke_ in vertices if stroke_)
        elif kind in ("line", "arrow"):
            paths = (tuple(_shown_point(page, p) for p in vertices[:2]),)
        else:
            paths = (tuple(_shown_point(page, p) for p in vertices),)
        if not paths or len(paths[0]) < (1 if kind == "ink" else 2):
            return None
        return Annotation(rect=frame(kind, paths, width), color=stroke or "#000000", fill=fill, paths=paths,
                          ends=ends if kind in ENDED else ("None", "None"), **fields)
    if kind == "stamp":
        name = doc.xref_get_key(annot.xref, "Name")[1].lstrip("/")
        return Annotation(rect=_shown_rect(page, annot.rect), color=stroke or "#000000",
                          stamp=name if name in STAMPS else "", image=_stamp_image(annot), **fields)
    # (a note, or a caret)
    icon = info.get("name", "") or "Note"
    return Annotation(rect=_shown_rect(page, annot.rect), color=stroke or ("#ffd54f" if kind == "note" else "#1e88e5"),
                      icon=icon if icon in ICONS else "Note", **fields)


def read(doc: pymupdf.Document) -> list[Annotation]:
    """The annotations of DOC that py-annotate can edit, page by page."""
    out = []
    for page in doc:
        for annot in page.annots() or []:
            a = read_annotation(doc, page, annot)
            if a is not None:
                out.append(a)
    return out


def remove_editable(doc: pymupdf.Document) -> None:
    """Take out of DOC the annotations that read() gives (for showing its pages
    without them: the window draws them itself)."""
    for page in doc:
        xrefs = [annot.xref for annot in page.annots() or [] if kind_of(doc, annot) is not None]
        for xref in xrefs:
            page.delete_annot(page.load_annot(xref))


def _placed(page: pymupdf.Page, make, rect: Rect, size: tuple[float, float]) -> pymupdf.Annot:
    """An annotation of a size of its own (a note, a caret), made by MAKE(point),
    with its top left corner where RECT's is, as the page is shown."""
    x0, y0 = rect[0], rect[1]
    w, h = shown_size(page.rotation, size)
    where = _real_rect(page, (x0, y0, x0 + w, y0 + h))
    annot = make(where.tl)
    shift = where.tl - annot.rect.tl
    if abs(shift.x) > 0.01 or abs(shift.y) > 0.01:  # (on a turned page, MuPDF puts it beside the point)
        page.delete_annot(annot)
        annot = make(where.tl + shift)
    return annot


def _flags(annot: pymupdf.Annot, locked: bool) -> None:
    flags = annot.flags | pymupdf.PDF_ANNOT_IS_PRINT
    flags = flags | pymupdf.PDF_ANNOT_IS_LOCKED if locked else flags & ~pymupdf.PDF_ANNOT_IS_LOCKED
    if flags != annot.flags:
        annot.set_flags(flags)


def _info(annot: pymupdf.Annot, a: Annotation, when: str, subject: str | None = None) -> None:
    info = {"content": a.contents, "title": a.author, "creationDate": a.created or when, "modDate": when}
    if subject is not None:
        info["subject"] = subject
    annot.set_info(**info)


def add(page: pymupdf.Page, a: Annotation, when: str | None = None) -> pymupdf.Annot:
    """Write A on PAGE, as a new annotation, made (if A has no date) and changed WHEN (a PDF date; now)."""
    when = when or now()
    stroke = rgb(a.color)
    fill = rgb(a.fill) if a.fill else None
    dashes = DASHES if a.dashed and a.kind in DASHABLE else None
    subject = None
    if a.kind in MARKUP:
        quads = [_real_rect(page, q).quad for q in (a.quads or (a.rect,))]
        method = {"highlight": page.add_highlight_annot, "underline": page.add_underline_annot,
                  "strikeout": page.add_strikeout_annot, "squiggly": page.add_squiggly_annot}[a.kind]
        annot = method(quads=quads)
        annot.set_colors(stroke=stroke)
    elif a.kind in TEXTUAL:
        box = _real_rect(page, a.rect)
        extra = {}
        if a.kind == "callout" and a.paths:
            tip = a.paths[0][0]
            extra = {"callout": [tuple(_real_point(page, tip)), tuple(_real_point(page, anchor(a.rect, tip)))],
                     "line_end": _END_CODES.get(a.ends[1], pymupdf.PDF_ANNOT_LE_OPEN_ARROW)}
        annot = page.add_freetext_annot(box, a.contents, fontsize=a.font_size, fontname=a.font, text_color=stroke,
                                        fill_color=fill, border_width=a.width, dashes=dashes,
                                        align={"center": 1, "right": 2}.get(a.align, 0), rotate=page.rotation,
                                        **extra)
    elif a.kind in ("rect", "ellipse", "area"):
        method = page.add_circle_annot if a.kind == "ellipse" else page.add_rect_annot
        annot = method(_real_rect(page, a.rect))
        annot.set_border(width=0 if a.kind == "area" else a.width, dashes=dashes or [])
        annot.set_colors(stroke=stroke, fill=fill)
        if a.kind == "area":
            subject = AREA_SUBJECT
    elif a.kind in ("line", "arrow"):
        p1, p2 = a.paths[0][0], a.paths[0][-1]
        annot = page.add_line_annot(_real_point(page, p1), _real_point(page, p2))
        annot.set_border(width=a.width, dashes=dashes or [])
        annot.set_colors(stroke=stroke)
        ends = a.ends if a.kind == "line" or a.ends != ("None", "None") else ("None", "OpenArrow")
        annot.set_line_ends(*(_END_CODES.get(e, 0) for e in ends))
    elif a.kind in ("polygon", "cloud", "polyline"):
        points = [tuple(_real_point(page, p)) for p in a.paths[0]]
        annot = page.add_polyline_annot(points) if a.kind == "polyline" else page.add_polygon_annot(points)
        annot.set_border(width=a.width, dashes=dashes or [], clouds=1 if a.kind == "cloud" else -1)
        annot.set_colors(stroke=stroke, fill=fill if a.kind != "polyline" else None)
        if a.kind == "polyline":
            annot.set_line_ends(*(_END_CODES.get(e, 0) for e in a.ends))
    elif a.kind == "ink":
        annot = page.add_ink_annot([[tuple(_real_point(page, p)) for p in path] for path in a.paths])
        annot.set_border(width=a.width)
        annot.set_colors(stroke=stroke)
    elif a.kind == "note":
        annot = _placed(page, lambda p: page.add_text_annot(p, a.contents, icon=a.icon), a.rect,
                        (NOTE_SIZE, NOTE_SIZE))
        annot.set_colors(stroke=stroke)
    elif a.kind == "caret":
        annot = _placed(page, page.add_caret_annot, a.rect, CARET_SIZE)
        annot.set_colors(stroke=stroke)
    elif a.kind == "stamp":
        stamps = list(STAMPS)
        annot = page.add_stamp_annot(_real_rect(page, a.rect),
                                     stamp=stamps.index(a.stamp) if a.stamp in stamps else a.image)
    else:
        raise ValueError(a.kind)
    _info(annot, a, when, subject)
    if a.opacity < 1:
        annot.set_opacity(a.opacity)
    _flags(annot, a.locked)
    if a.kind in TEXTUAL:  # (update() alone would forget the colour and size of its text)
        annot.update(fontsize=a.font_size, fontname=a.font, text_color=stroke, fill_color=fill, rotate=page.rotation)
        if a.kind == "freetext":  # (PyMuPDF gives every text box a callout line, of no length)
            page.parent.xref_set_key(annot.xref, "CL", "null")
    elif a.kind != "stamp" or a.stamp:  # (an image stamp's look would be lost)
        annot.update()
    return annot


def change_stamp(page: pymupdf.Page, annot: pymupdf.Annot, a: Annotation, when: str | None = None) -> None:
    """Change the stamp ANNOT where it is into A: its place, comment, author,
    opacity and lock (its image, which can't be made again, stays)."""
    annot.set_rect(_real_rect(page, a.rect))
    _info(annot, a, when or now())
    annot.set_opacity(a.opacity)
    _flags(annot, a.locked)
    if a.stamp:
        annot.update()


def apply(doc: pymupdf.Document, annotations: list[Annotation], when: str | None = None) -> int:
    """Make the annotations of DOC that read() gives be ANNOTATIONS.

    Those of DOC are compared with ANNOTATIONS by their xref: those that are
    there and the same are left as they are; the others (changed, or deleted)
    are taken out, and what is new or changed is written (but stamps are
    changed where they are). Returns how many annotations were written."""
    when = when or now()
    original = {a.xref: a for a in read(doc)}
    kept = {a.xref for a in annotations if a.xref and original.get(a.xref) == a}
    stamps = {a.xref: a for a in annotations if a.kind == "stamp" and a.xref in original and a.xref not in kept
              and original[a.xref].kind == "stamp" and original[a.xref].page == a.page}
    written = 0
    for page in doc:
        for annot in list(page.annots() or []):
            if annot.xref in stamps:
                change_stamp(page, annot, stamps[annot.xref], when)
                written += 1
        gone = [annot.xref for annot in page.annots() or []
                if annot.xref in original and annot.xref not in kept and annot.xref not in stamps]
        for xref in gone:
            page.delete_annot(page.load_annot(xref))
    for a in annotations:
        if a.xref in kept or a.xref in stamps or not 0 <= a.page < doc.page_count:
            continue
        if a.kind == "stamp" and not a.stamp and not a.image:
            continue  # (an image stamp whose image is lost: nothing to write)
        add(doc[a.page], a, when)
        written += 1
    return written


def save_doc(doc: pymupdf.Document, target: Path) -> None:
    """Save DOC as TARGET, safely (through a file of its own, put in its place at the end)."""
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
    os.close(fd)
    try:
        doc.save(tmp, garbage=1, deflate=True,
                 encryption=pymupdf.PDF_ENCRYPT_KEEP if doc.needs_pass else pymupdf.PDF_ENCRYPT_NONE)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write(source: Path, annotations: list[Annotation], target: Path, password: str = "") -> int:
    """SOURCE with ANNOTATIONS (see apply), saved as TARGET (safely: TARGET may
    be SOURCE). Returns how many annotations were written."""
    doc = open_pdf(source, password)
    try:
        written = apply(doc, annotations)
        save_doc(doc, target)
    except (OSError, RuntimeError, ValueError) as e:
        raise AnnotateError(tr("{path} cannot be written: {error}", path=target, error=e)) from None
    finally:
        doc.close()
    return written


# --------------------------------------------------------------------- text

def words(page: pymupdf.Page) -> list[tuple[Rect, int, int]]:
    """The words of PAGE in reading order: (their rectangle as the page is
    shown, block number, line number)."""
    out = []
    for x0, y0, x1, y1, _text, block, line, _n in page.get_text("words", sort=False):
        r = (pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix).normalize()
        out.append(((r.x0, r.y0, r.x1, r.y1), block, line))
    return out


def nearest_word(found: list[tuple[Rect, int, int]], x: float, y: float) -> int | None:
    """The index of the word at (X, Y), or else of the nearest one; None if there are none."""
    if not found:
        return None

    def distance(i):
        x0, y0, x1, y1 = found[i][0]
        dx = max(x0 - x, 0, x - x1)
        dy = max(y0 - y, 0, y - y1)
        return dx * dx + 4 * dy * dy  # (the line it is on matters more)

    return min(range(len(found)), key=distance)


def text_rects(found: list[tuple[Rect, int, int]], first: int, last: int) -> list[Rect]:
    """The rectangles that cover the words FIRST to LAST (in either order) of
    FOUND: one for each line."""
    if first > last:
        first, last = last, first
    lines: dict[tuple[int, int], list[float]] = {}
    for (x0, y0, x1, y1), block, line in found[first:last + 1]:
        r = lines.setdefault((block, line), [x0, y0, x1, y1])
        r[0], r[1], r[2], r[3] = min(r[0], x0), min(r[1], y0), max(r[2], x1), max(r[3], y1)
    return [(_r(x0), _r(y0), _r(x1), _r(y1)) for x0, y0, x1, y1 in lines.values()]


def text_under(page: pymupdf.Page, rects: list[Rect]) -> str:
    """The text under RECTS (as the page is shown), a line for each."""
    out = []
    for r in rects:
        text = page.get_textbox(_real_rect(page, r))
        out.append(" ".join(text.split()))
    return " ".join(t for t in out if t)
