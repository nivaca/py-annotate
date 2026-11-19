"""Finding text on the pages, for Find and highlight: a word, a phrase or a
regular expression, found across line breaks however it is spaced; each place
found is given with a rectangle for each of its lines, as the page is shown
(what a highlight over it needs)."""

from __future__ import annotations

import dataclasses
import re

import pymupdf

from .annots import Rect


@dataclasses.dataclass(frozen=True)
class Match:
    page: int  # 0-based
    rects: tuple[Rect, ...]  # one for each line of the text found
    text: str  # what was found
    context: str  # with some words around it, the text found in [brackets]


def _shown(page: pymupdf.Page, rect) -> pymupdf.Rect:
    return (pymupdf.Rect(rect) * page.rotation_matrix).normalize()


def page_chars(page: pymupdf.Page) -> tuple[str, list]:
    """The text of PAGE, and for each of its characters (block, line, rectangle as the page
    is shown), or None for a space put between two lines. Runs of spaces are one space."""
    text, where = [], []
    raw = page.get_text("rawdict", flags=pymupdf.TEXTFLAGS_SEARCH & ~pymupdf.TEXT_PRESERVE_IMAGES)
    for b, block in enumerate(raw.get("blocks", [])):
        for n, line in enumerate(block.get("lines", [])):
            if text and text[-1] != " ":
                text.append(" ")
                where.append(None)
            for span in line.get("spans", []):
                for ch in span.get("chars", []):
                    c = ch["c"]
                    if c.isspace():
                        if text and text[-1] == " ":
                            continue
                        c = " "
                    text.append(c)
                    where.append((b, n, _shown(page, ch["bbox"])))
    return "".join(text), where


def compile_query(query: str, case: bool = False, whole_words: bool = False, regex: bool = False) -> re.Pattern:
    """QUERY as a regular expression (raises re.error if REGEX and it is wrong)."""
    pattern = query if regex else r"\s+".join(re.escape(w) for w in query.split())
    if whole_words:
        pattern = rf"(?<!\w)(?:{pattern})(?!\w)"
    return re.compile(pattern, 0 if case else re.IGNORECASE)


def find_text(doc: pymupdf.Document, query: str, pages: list[int] | None = None, case: bool = False,
              whole_words: bool = False, regex: bool = False, progress=None) -> list[Match]:
    """Where QUERY is on PAGES (0-based; all if None) of DOC, in page order. PROGRESS, if
    given, is called after each page with (pages done, pages in all); if it returns False,
    the search stops there, with what it found so far."""
    if not query.strip():
        return []
    found_re = compile_query(query, case, whole_words, regex)
    numbers = list(range(doc.page_count) if pages is None else pages)
    out = []
    for done, number in enumerate(numbers, 1):
        text, where = page_chars(doc[number])
        for m in found_re.finditer(text):
            start, end = m.span()
            chosen = [i for i in range(start, end) if where[i] is not None and not text[i].isspace()]
            if not chosen:
                continue
            lines: dict[tuple[int, int], pymupdf.Rect] = {}
            for i in chosen:
                b, n, r = where[i]
                lines[(b, n)] = lines[(b, n)] | r if (b, n) in lines else pymupdf.Rect(r)
            rects = tuple((round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)) for r in lines.values())
            before = text[max(start - 40, 0):start].split(" ", 1)[-1] if start > 40 else text[:start]
            after = text[end:end + 40].rsplit(" ", 1)[0] if len(text) > end + 40 else text[end:]
            snippet = m.group(0).strip()
            context = " ".join(p for p in (before.strip(), f"[{snippet}]", after.strip()) if p)
            out.append(Match(number, rects, snippet, context))
        if progress is not None and progress(done, len(numbers)) is False:
            break
    return out
