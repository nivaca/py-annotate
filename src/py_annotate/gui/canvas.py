"""The page being annotated, and its annotations: made with the tool chosen
(dragging over text, dragging a box, a line or a stroke, clicking the points
of a polygon, or clicking), moved by dragging them (or with the arrow keys),
resized by dragging their edges and corners, and reshaped by dragging their
points; selected by clicking them or by dragging a frame around them; and
erased with the eraser."""

from __future__ import annotations

import dataclasses
import math
from collections import OrderedDict
from collections.abc import Callable

import pymupdf
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from .. import annots
from ..annots import (
    CARET_SIZE,
    MARKUP,
    NOTE_SIZE,
    RESIZABLE,
    VERTICES,
    Annotation,
    Rect,
    nearest_word,
    text_rects,
    words,
)
from .paint import paint, qrect

SCENE_MARGIN = 12  # points around the page
MIN_SIZE = 3.0  # points: a smaller drag is a click
GRIP = 6  # pixels from an edge, or from a point of a line, where dragging resizes or reshapes
ERASER = 7  # pixels: the radius of the eraser
MAX_PIXELS = 40_000_000  # the largest rendering of a page
CACHED_PAGES = 6  # renderings kept, so that a page turned back needn't render again
SELECTED = QColor(42, 127, 255)
NEAR_TEXT = 3.0  # points: a drag that starts this close to a word selects text
FREETEXT_SIZE = (180.0, 40.0)  # points: a text box made by a click
BOXES = ("freetext", "area", "rect", "ellipse", "cloud")  # (tools that drag a box)
LINES = ("line", "arrow")
POLYGONS = ("polygon", "polyline")  # (tools that click point after point)
CLICKS = ("note", "caret", "stamp", "callout")


def page_image(page: pymupdf.Page, scale: float) -> QImage:
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    return QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()


def _distance(p: QPointF, a: QPointF, b: QPointF) -> float:
    """From P to the segment from A to B."""
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((p.x() - a.x()) * dx + (p.y() - a.y()) * dy) / length))
    return math.hypot(p.x() - a.x() - t * dx, p.y() - a.y() - t * dy)


def _near_path(point: QPointF, path, reach: float, closed: bool = False) -> bool:
    pts = [QPointF(*pt) for pt in path]
    if closed and len(pts) > 2:
        pts.append(pts[0])
    if len(pts) == 1:
        return math.hypot(point.x() - pts[0].x(), point.y() - pts[0].y()) <= reach
    return any(_distance(point, p, q) <= reach for p, q in zip(pts, pts[1:]))


def erase_ink(a: Annotation, centres: list[tuple[float, float]], radius: float) -> Annotation | None:
    """A, a drawing, without what lies within RADIUS of CENTRES: its strokes cut
    where they were erased (None if nothing is left of it)."""
    def gone(p) -> bool:
        return any((p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 <= radius * radius for c in centres)

    paths = []
    for path in a.paths:
        piece: list = []
        for p in path:
            if gone(p):
                if len(piece) > 1:
                    paths.append(tuple(piece))
                piece = []
            else:
                piece.append(p)
        if len(piece) > 1:
            paths.append(tuple(piece))
    if not paths:
        return None
    return dataclasses.replace(a, paths=tuple(paths), rect=annots.frame(a.kind, paths, a.width))


class AnnotItem(QGraphicsItem):
    """An annotation on the page, drawn as it will look; when selected, a blue
    frame around it, with handles where it can be resized or reshaped."""

    def __init__(self, index: int, annotation: Annotation, selected: bool):
        super().__init__()
        self.index = index
        self.annot = annotation
        self.chosen = selected
        self.setZValue(2 if selected else 1)
        tip = f"<b>{annotation.name()}</b>"
        if annotation.author:
            tip += f" — {annotation.author}"
        if annotation.contents:
            text = annotation.contents if len(annotation.contents) <= 300 else annotation.contents[:298] + "…"
            tip += "<br>" + text.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")
        self.setToolTip(tip)

    def set_annotation(self, annotation: Annotation):
        """Show ANNOTATION in its place (while it is dragged)."""
        self.prepareGeometryChange()
        self.annot = annotation
        self.update()

    def frame(self) -> QRectF:
        a = self.annot
        if a.kind in MARKUP:
            return qrect(annots.union(a.quads)) if a.quads else qrect(a.rect)
        if a.kind == "callout" and a.paths:
            tip = a.paths[0][0]
            return qrect(a.rect).united(QRectF(QPointF(*tip), QPointF(*tip)))
        return qrect(a.rect)

    def boundingRect(self) -> QRectF:
        pad = max(self.annot.width, 2) * 4 + 12
        return self.frame().adjusted(-pad, -pad, pad, pad)

    def handles(self) -> list[QPointF]:
        """The points that can be dragged one by one (of a line, a polygon; the place a callout points at)."""
        a = self.annot
        if (a.kind in VERTICES or a.kind == "callout") and a.paths:
            return [QPointF(*pt) for pt in a.paths[0]]
        return []

    def movable(self) -> bool:
        return self.annot.kind not in MARKUP and not self.annot.locked

    def hit(self, point: QPointF, grip: float) -> str | None:
        """What dragging at POINT does: None (it isn't there), '' (moves it), some of
        'l', 't', 'r', 'b' (resizes it by those edges), 'vN' (moves its point N)."""
        a = self.annot
        if a.kind in MARKUP:
            inside = any(qrect(q).adjusted(-grip, -grip, grip, grip).contains(point) for q in a.quads)
            return "" if inside else None
        if self.chosen and not a.locked:
            for i, h in enumerate(self.handles()):
                if math.hypot(point.x() - h.x(), point.y() - h.y()) <= grip * 1.5:
                    return f"v{i}"
        if a.kind in VERTICES and a.paths:
            reach = grip + a.width / 2
            if _near_path(point, a.paths[0], reach, closed=a.kind in ("polygon", "cloud")):
                return ""
            if a.kind in ("polygon", "cloud") and (a.fill or a.kind == "cloud") and \
                    qrect(a.rect).contains(point):
                return ""
            return None
        if a.kind == "callout" and a.paths and _near_path(point, (annots.anchor(a.rect, a.paths[0][0]),
                                                                  a.paths[0][0]), grip + 1):
            return ""
        r = qrect(a.rect)
        if a.kind == "ink" and not self.chosen:  # (only on its lines; once selected, its frame too)
            return "" if any(_near_path(point, path, grip + a.width / 2) for path in a.paths) else None
        if not r.adjusted(-grip, -grip, grip, grip).contains(point):
            return None
        edges = ""
        if a.kind in RESIZABLE and not a.locked and (self.chosen or a.kind != "ink"):
            if abs(point.x() - r.left()) <= grip:
                edges += "l"
            elif abs(point.x() - r.right()) <= grip:
                edges += "r"
            if abs(point.y() - r.top()) <= grip:
                edges += "t"
            elif abs(point.y() - r.bottom()) <= grip:
                edges += "b"
        if not edges and not r.contains(point):
            return None
        return edges

    def paint(self, painter, option, widget=None):
        paint(painter, self.annot)
        if not self.chosen:
            return
        scale = painter.worldTransform().m11() or 1
        a = self.annot
        frame = qrect(a.rect) if a.kind not in MARKUP else self.frame()
        pen = QPen(SELECTED, 1.2, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        side = 7 / scale
        handles = self.handles()
        if a.kind not in ("line", "arrow", "polyline"):
            painter.drawRect(frame.adjusted(-1 / scale, -1 / scale, 1 / scale, 1 / scale))
        if a.locked:  # (a small padlock in the corner)
            s = 9 / scale
            x, y = frame.right() - s - 2 / scale, frame.top() + 2 / scale
            painter.setPen(QPen(SELECTED, 1.2 / scale))
            painter.setBrush(QColor(255, 255, 255, 220))
            painter.drawRect(QRectF(x, y + s * 0.45, s, s * 0.55))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(x + s * 0.2, y, s * 0.6, s * 0.9), 0, 180 * 16)
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(SELECTED)
        corners = [] if a.kind not in RESIZABLE else \
            [frame.topLeft(), frame.topRight(), frame.bottomLeft(), frame.bottomRight()]
        if a.kind in ("line", "arrow", "polyline"):
            corners = []
        for corner in corners:
            painter.drawRect(QRectF(corner.x() - side / 2, corner.y() - side / 2, side, side))
        painter.setBrush(QColor("white"))
        painter.setPen(QPen(SELECTED, 1.5 / scale))
        for h in handles:
            painter.drawEllipse(h, side / 2, side / 2)


class PageCanvas(QGraphicsView):
    """A page and its annotations. The annotations are identified by their
    index in the window's list; what the user does is reported with the signals."""

    drawn = Signal(object)  # Annotation: a new one (made by FACTORY), drawn on the page
    edited = Signal(int, object)  # index, Annotation: one moved, resized or reshaped
    erased = Signal(object)  # {index: Annotation, or None to delete it}: what the eraser did
    nudged = Signal(float, float)  # the selected annotations moved with the arrow keys, by (dx, dy) points
    picked = Signal(list, bool)  # indices clicked (or framed); whether to add them to the selection
    zoom_changed = Signal(float)
    text_chosen = Signal(list)  # [Rect]: the lines of the text selected (with a markup tool)
    double_clicked = Signal(int, tuple)  # index of the annotation (-1: none), (x, y) on the page
    menu_asked = Signal(int, object, object)  # index of the annotation (-1: none), place on the screen, on the page

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setBackgroundBrush(self.palette().dark())
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page: pymupdf.Page | None = None
        self.page_size = QRectF()
        self.fit = "page"  # 'page', 'width' or '' (a zoom of its own)
        # 'select': selects, moves and resizes; 'hand': dragging scrolls; 'eraser': dragging erases;
        # else the kind of annotation that the tool makes: see annots.KINDS
        self.mode = "select"
        # makes the annotation of a kind, page, frame and paths with the style of new ones (the window's)
        self.factory: Callable[[str, int, Rect, tuple], Annotation] | None = None
        self.editable = True  # (False: the annotations are hidden, and nothing can be done to them)
        self._words: list | None = None  # (of the page, when first needed)
        self.pixmap_item: QGraphicsPixmapItem | None = None
        self.items_: list[AnnotItem] = []
        self._drag: dict | None = None
        self._poly: dict | None = None  # (a polygon being made: its points, and its picture)
        self._rendered = 0.0
        self.render_timer = QTimer(self, singleShot=True, interval=120)
        self.render_timer.timeout.connect(self._render)
        self._cache: OrderedDict = OrderedDict()  # (document, page number, scale) -> QPixmap
        self._ahead: list[pymupdf.Page] = []  # pages to render while the window is idle
        self.ahead_timer = QTimer(self, singleShot=True, interval=60)
        self.ahead_timer.timeout.connect(self._render_ahead)
        # (path, password, stamp) of the document on disk, if the pages can be rendered in
        # another process (see renderer.py); and a picture to show until the page arrives
        self.source = None
        self.placeholder: QImage | None = None
        self._wanted: tuple | None = None  # the key of the rendering awaited for the page shown

    # ----------------------------------------------------------------- page and annotations

    def show_page(self, page: pymupdf.Page | None, items: list[tuple[int, Annotation]], selected: list[int],
                  keep_view: bool = False):
        """PAGE, with ITEMS: (index, annotation)."""
        same = keep_view and page is not None and self.page is not None and QRectF(*page.rect) == self.page_size
        self.scene().clear()
        self.items_, self.pixmap_item, self._drag, self._poly = [], None, None, None
        if page is not self.page:
            self._words = None
            self._wanted = None
        self.page = page
        if page is None:
            self.page_size = QRectF()
            return
        self.page_size = QRectF(*page.rect)
        self.scene().setSceneRect(self.page_size.adjusted(-SCENE_MARGIN, -SCENE_MARGIN, SCENE_MARGIN, SCENE_MARGIN))
        self.scene().addRect(self.page_size, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))
        self.pixmap_item = QGraphicsPixmapItem()
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene().addItem(self.pixmap_item)
        self._rendered = 0.0
        for index, annotation in items:
            item = AnnotItem(index, annotation, index in selected)
            self.scene().addItem(item)
            self.items_.append(item)
        if not same:
            self.apply_fit()
        self._render()

    def zoom(self) -> float:
        return self.transform().m11()

    def _scale_for(self, page: pymupdf.Page) -> float:
        """The scale to render PAGE at, for the zoom and the screen."""
        scale = self.zoom() * self.devicePixelRatioF()
        w, h = page.rect.width * scale, page.rect.height * scale
        if w * h > MAX_PIXELS:
            scale *= (MAX_PIXELS / (w * h)) ** 0.5
        return round(scale, 3)

    def _pixmap(self, page: pymupdf.Page, scale: float) -> QPixmap:
        """PAGE rendered at SCALE, from the cache if it is there."""
        key = (id(page.parent), page.number, scale)
        pixmap = self._cache.get(key)
        if pixmap is None:
            pixmap = self._keep(key, page_image(page, scale))
        else:
            self._cache.move_to_end(key)
        return pixmap

    def clear_cache(self):
        """Forget the renderings (another document was opened, or this one changed on disk)."""
        self._cache.clear()
        self._ahead = []

    def _remote(self):
        """The renderer of other processes, if pages are rendered there."""
        from .renderer import renderer

        r = renderer()
        return r if self.source is not None and r.available() else None

    def render_ahead(self, pages: list[pymupdf.Page]):
        """Render PAGES (the next and previous ones) when the window is idle, so that
        turning to them is at once."""
        self._ahead = list(pages)
        remote = self._remote()
        if remote is None:
            self.ahead_timer.start()
            return
        shown = self.page.number if self.page is not None else -1
        remote.drop("view", keep=lambda path, number: number == shown)
        self._request_ahead(remote)

    def _request_ahead(self, remote):
        """Ask the other process for the pages to render ahead (at the zoom of now)."""
        for page in self._ahead:
            try:
                scale = self._scale_for(page)
            except (RuntimeError, ValueError):  # (the document was closed meanwhile)
                self._ahead = []
                return
            key = (id(page.parent), page.number, scale)
            if key not in self._cache:
                remote.request("view", self.source, page.number, scale,
                               lambda image, key=key: self._arrived(key, image))

    def _render_ahead(self):
        if not self._ahead:
            return
        page = self._ahead.pop(0)
        try:
            self._pixmap(page, self._scale_for(page))
        except (RuntimeError, ValueError):  # (the document was closed meanwhile)
            self._ahead = []
            return
        if self._ahead:
            self.ahead_timer.start()

    def _keep(self, key: tuple, image: QImage) -> QPixmap:
        pixmap = QPixmap.fromImage(image)
        self._cache[key] = pixmap
        while len(self._cache) > CACHED_PAGES:
            self._cache.popitem(last=False)
        return pixmap

    def _arrived(self, key: tuple, image: QImage | None):
        """A rendering from another process (None: it couldn't be made there)."""
        if image is not None:
            pixmap = self._keep(key, image)
        elif key == self._wanted and self.page is not None:
            pixmap = self._pixmap(self.page, key[2])  # (rendered here, then)
        else:
            return
        if key == self._wanted and self.pixmap_item is not None:
            self._wanted = None
            self.pixmap_item.setPixmap(pixmap)
            self.pixmap_item.setScale(1 / key[2])

    def _render(self):
        if self.page is None or self.pixmap_item is None:
            return
        scale = self._scale_for(self.page)
        if abs(scale - self._rendered) < 1e-3:
            return
        self._rendered = scale
        key = (id(self.page.parent), self.page.number, scale)
        remote = self._remote()
        if key in self._cache or remote is None:
            self._wanted = None
            self.pixmap_item.setPixmap(self._pixmap(self.page, scale))
            self.pixmap_item.setScale(1 / scale)
            return
        # (meanwhile, the page as it was, at another zoom, or its thumbnail made larger)
        if self.pixmap_item.pixmap().isNull():
            old = next((k for k in reversed(self._cache) if k[:2] == key[:2]), None)
            if old is not None:
                self.pixmap_item.setPixmap(self._cache[old])
                self.pixmap_item.setScale(1 / old[2])
            elif self.placeholder is not None and not self.placeholder.isNull():
                self.pixmap_item.setPixmap(QPixmap.fromImage(self.placeholder))
                self.pixmap_item.setScale(self.page_size.width() / self.placeholder.width())
        self._wanted = key
        remote.drop("view")  # (the pages next to one left behind, or at an older zoom)
        remote.request("view", self.source, self.page.number, scale, lambda image: self._arrived(key, image),
                       first=True)
        self._request_ahead(remote)

    # ----------------------------------------------------------------- zoom

    def set_zoom(self, factor: float, fit: str = ""):
        factor = max(0.05, min(factor, 16))
        self.fit = fit
        self.resetTransform()
        self.scale(factor, factor)
        self.render_timer.start()
        self.zoom_changed.emit(factor)

    def apply_fit(self):
        if self.page_size.isEmpty() or not self.fit:
            return
        room = self.viewport().size()
        margin = 2 * SCENE_MARGIN + 4  # (points around the page, and a few pixels)
        by_width = (room.width() - 4) / (self.page_size.width() + margin)
        by_height = (room.height() - 4) / (self.page_size.height() + margin)
        self.set_zoom(by_width if self.fit == "width" else min(by_width, by_height), self.fit)

    def zoom_by(self, factor: float):
        self.set_zoom(self.zoom() * factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_fit()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            z = max(0.05, min(self.zoom() * factor, 16))
            self.scale(z / self.zoom(), z / self.zoom())
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.fit = ""
            self.render_timer.start()
            self.zoom_changed.emit(z)
            event.accept()
        else:
            super().wheelEvent(event)

    # ----------------------------------------------------------------- the mouse and the keys

    def _hit(self, pos) -> tuple[AnnotItem | None, str]:
        """The annotation at POS (view coordinates), and what dragging it does (see AnnotItem.hit)."""
        point = self.mapToScene(pos)
        grip = GRIP / (self.zoom() or 1)
        # (the selected first, then those on top: the last drawn)
        for item in sorted(self.items_, key=lambda i: (-i.zValue(), -i.index)):
            edges = item.hit(point, grip)
            if edges is not None:
                return item, edges
        return None, ""

    @staticmethod
    def _cursor(edges: str, movable: bool) -> Qt.CursorShape:
        if not movable:
            return Qt.CursorShape.PointingHandCursor
        if edges in ("lt", "rb"):
            return Qt.CursorShape.SizeFDiagCursor
        if edges in ("rt", "lb"):
            return Qt.CursorShape.SizeBDiagCursor
        if edges in ("l", "r"):
            return Qt.CursorShape.SizeHorCursor
        if edges in ("t", "b"):
            return Qt.CursorShape.SizeVerCursor
        if edges.startswith("v"):
            return Qt.CursorShape.CrossCursor
        return Qt.CursorShape.SizeAllCursor

    def _clamp(self, point: QPointF) -> QPointF:
        r = self.page_size
        return QPointF(min(max(point.x(), r.left()), r.right()), min(max(point.y(), r.top()), r.bottom()))

    def contextMenuEvent(self, event):
        if self.page is None:
            return
        self.cancel_polygon()
        item, _ = self._hit(event.pos())
        if item is not None and not item.chosen:
            self.picked.emit([item.index], False)
        self.menu_asked.emit(item.index if item else -1, event.globalPos(), self.mapToScene(event.pos()))
        event.accept()

    def page_words(self) -> list:
        if self._words is None:
            self._words = words(self.page) if self.page is not None else []
        return self._words

    def _text_selection(self, start: QPointF, end: QPointF) -> list[Rect]:
        found = self.page_words()
        a = nearest_word(found, start.x(), start.y())
        b = nearest_word(found, end.x(), end.y())
        return [] if a is None else text_rects(found, a, b)

    def _show_text(self, rects: list[Rect]):
        for item in self._drag["marks"]:
            self.scene().removeItem(item)
        color = QColor(SELECTED)
        color.setAlpha(80)
        self._drag["marks"] = [self.scene().addRect(qrect(r), QPen(Qt.PenStyle.NoPen), QBrush(color)) for r in rects]
        for item in self._drag["marks"]:
            item.setZValue(3)

    def near_text(self, point: QPointF) -> bool:
        """Whether POINT (on the page) is on a word, or very close to one."""
        for (x0, y0, x1, y1), _, _ in self.page_words():
            if x0 - NEAR_TEXT <= point.x() <= x1 + NEAR_TEXT and y0 - NEAR_TEXT <= point.y() <= y1 + NEAR_TEXT:
                return True
        return False

    def set_mode(self, mode: str):
        self.cancel_polygon()
        self.mode = mode
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if mode == "hand"
                         else QGraphicsView.DragMode.NoDrag)
        self.viewport().unsetCursor()

    def _new(self, kind: str, rect: Rect, paths: tuple = ()) -> Annotation:
        page = self.page.number if self.page is not None else 0
        if self.factory is not None:
            return self.factory(kind, page, rect, paths)
        return Annotation(kind, page, rect, paths=paths)

    def _preview(self, annotation: Annotation) -> AnnotItem:
        item = AnnotItem(-1, annotation, False)
        item.setZValue(3)
        self.scene().addItem(item)
        return item

    def _remove_drag_items(self):
        if self._drag is None:
            return
        for mark in self._drag.get("marks", []):
            self.scene().removeItem(mark)
        if "item" in self._drag and self._drag["kind"] not in ("edit",):
            self.scene().removeItem(self._drag["item"])

    # (polygons and polylines: a click for each point; a double-click, Enter or a click on the first
    #  point ends it, Escape gives it up)

    def _polygon_click(self, point: QPointF):
        p = self._clamp(point)
        here = (round(p.x(), 2), round(p.y(), 2))
        if self._poly is None:
            self._poly = {"points": [here], "item": self._preview(self._new(self.mode, (*here, *here), ((here, here),)))}
            return
        first = QPointF(*self._poly["points"][0])
        if len(self._poly["points"]) > 2 and math.hypot(p.x() - first.x(), p.y() - first.y()) * self.zoom() <= GRIP:
            self.finish_polygon()
            return
        self._poly["points"].append(here)
        self._show_polygon(here)

    def _show_polygon(self, rubber: tuple[float, float] | None):
        points = list(self._poly["points"]) + ([rubber] if rubber else [])
        paths = (tuple(points),)
        self._poly["item"].set_annotation(self._new(self.mode, annots.frame(self.mode, paths, 1), paths))

    def finish_polygon(self):
        poly, self._poly = self._poly, None
        if poly is None:
            return
        self.scene().removeItem(poly["item"])
        points = [p for i, p in enumerate(poly["points"]) if i == 0 or p != poly["points"][i - 1]]
        if len(points) >= (3 if self.mode == "polygon" else 2):
            paths = (tuple(points),)
            annotation = self._new(self.mode, (0, 0, 0, 0), paths)
            self.drawn.emit(dataclasses.replace(annotation, rect=annots.frame(annotation.kind, paths,
                                                                              annotation.width)))

    def cancel_polygon(self):
        if self._poly is not None:
            self.scene().removeItem(self._poly["item"])
            self._poly = None

    def keyPressEvent(self, event):
        key = event.key()
        if self._poly is not None and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish_polygon()
        elif self._poly is not None and key == Qt.Key.Key_Escape:
            self.cancel_polygon()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down) \
                and any(i.chosen for i in self.items_):
            step = 10.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
            dx = {Qt.Key.Key_Left: -step, Qt.Key.Key_Right: step}.get(key, 0.0)
            dy = {Qt.Key.Key_Up: -step, Qt.Key.Key_Down: step}.get(key, 0.0)
            self.nudged.emit(dx, dy)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self.page is None or self.mode == "hand" or event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        if self._poly is not None:
            self.finish_polygon()
            event.accept()
            return
        if not self.editable:
            return
        point = self.mapToScene(event.position().toPoint())
        item, _ = self._hit(event.position().toPoint())
        if item is not None and self.mode in MARKUP and item.annot.kind in MARKUP:
            item = None  # (with a markup tool, the word under a mark is marked too)
        self._remove_drag_items()
        self._drag = None
        self.double_clicked.emit(item.index if item else -1, (point.x(), point.y()))
        event.accept()

    def mousePressEvent(self, event):
        if self.mode == "hand" or self.page is None or event.button() != Qt.MouseButton.LeftButton \
                or not self.editable:
            super().mousePressEvent(event)
            return
        self.setFocus()
        pos = event.position().toPoint()
        point = self.mapToScene(pos)
        if self._poly is not None:
            self._polygon_click(point)
            event.accept()
            return
        if self.mode == "eraser":
            mark = self.scene().addEllipse(QRectF(), QPen(SELECTED, 0), QBrush(QColor(42, 127, 255, 40)))
            mark.setZValue(4)
            self._drag = {"kind": "erase", "start": point, "centres": [], "marks": [mark]}
            self._erase_at(point)
            event.accept()
            return
        add = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        item, edges = self._hit(pos)
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if self.mode in MARKUP and (item is None or item.annot.kind in MARKUP or shift):
            # (over a mark, dragging marks text too; a click selects the mark)
            self._drag = {"kind": "text", "start": point, "marks": [], "candidate": item}
            if item is None:
                self.picked.emit([], False)
            if not self.page_words() and item is None:
                self._drag = None
            event.accept()
            return
        if item is not None and not shift:
            if not item.chosen or add:
                self.picked.emit([item.index], add)
                item = next((i for i in self.items_ if i.index == item.index), None)
                if item is None or add:
                    self._drag = None
                    event.accept()
                    return
            if not item.movable():  # (selected, but it stays where it is)
                self._drag = None
                event.accept()
                return
            self._drag = {"kind": "edit", "start": point, "item": item, "edges": edges, "original": item.annot,
                          "moved": False}
            event.accept()
            return
        if not add:
            self.picked.emit([], False)
        start = self._clamp(point)
        here = (start.x(), start.y())
        if self.mode == "select":
            band = QGraphicsRectItem(QRectF(start, start))
            pen = QPen(SELECTED, 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            band.setPen(pen)
            band.setBrush(QColor(42, 127, 255, 30))
            band.setZValue(4)
            self.scene().addItem(band)
            self._drag = {"kind": "band", "start": start, "item": band, "add": add}
        elif self.mode in CLICKS:
            self._drag = {"kind": "click", "start": start}
            if self.mode == "callout":
                self._drag["item"] = self._preview(self._new("callout", (*here, *here), ((here,),)))
        elif self.mode in BOXES:
            self._drag = {"kind": "draw", "start": start, "item": self._preview(self._new(self.mode, (*here, *here),
                                                                                          self._box_paths(here, here)))}
        elif self.mode in LINES or self.mode == "ink":
            paths = ((here, here),)
            self._drag = {"kind": "line" if self.mode != "ink" else "ink", "start": start,
                          "item": self._preview(self._new(self.mode, (*here, *here), paths)), "points": [here]}
        elif self.mode in POLYGONS:
            self._polygon_click(point)
            self._drag = None
        else:
            self._drag = None
        event.accept()

    def _box_paths(self, a: tuple, b: tuple) -> tuple:
        """The points of a cloud drawn as a box from A to B (other boxes have none)."""
        if self.mode != "cloud":
            return ()
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        return (((x0, y0), (x1, y0), (x1, y1), (x0, y1)),)

    def _callout_box(self, tip: QPointF, at: QPointF) -> Rect:
        """The box of a callout that points at TIP, put at AT (a click: above and to the right of TIP)."""
        w, h = FREETEXT_SIZE
        if math.hypot(at.x() - tip.x(), at.y() - tip.y()) * self.zoom() < 6:
            at = QPointF(tip.x() + 30, tip.y() - 30 - h)
        x = max(min(at.x(), self.page_size.right() - w), self.page_size.left())
        y = max(min(at.y(), self.page_size.bottom() - h), self.page_size.top())
        return round(x, 2), round(y, 2), round(x + w, 2), round(y + h, 2)

    def _erase_at(self, point: QPointF):
        drag = self._drag
        radius = ERASER / (self.zoom() or 1)
        drag["centres"].append((point.x(), point.y()))
        drag["marks"][0].setRect(QRectF(point.x() - radius, point.y() - radius, 2 * radius, 2 * radius))
        for item in self.items_:
            if item.annot.locked or item.annot.kind == "ink":
                continue
            if item.opacity() > 0.5 and item.hit(point, radius) is not None:
                item.setOpacity(0.2)  # (to go, once the button is let go)
        for item in self.items_:
            if item.annot.kind == "ink" and not item.annot.locked:
                original = drag.setdefault("ink", {}).setdefault(item.index, item.annot)
                left = erase_ink(original, drag["centres"], radius)
                if left is None:
                    item.setOpacity(0.2)
                else:
                    item.set_annotation(left)

    def mouseMoveEvent(self, event):
        drag = self._drag
        point = self.mapToScene(event.position().toPoint())
        if self._poly is not None:
            p = self._clamp(point)
            self._show_polygon((round(p.x(), 2), round(p.y(), 2)))
        if drag is None:
            if self.page is not None and self.mode != "hand" and self.editable:
                item, edges = self._hit(event.position().toPoint())
                if self.mode == "eraser":
                    shape = Qt.CursorShape.CrossCursor
                elif item is not None and not (self.mode in MARKUP and item.annot.kind in MARKUP):
                    shape = self._cursor(edges, item.movable())
                elif self.mode in MARKUP:
                    shape = Qt.CursorShape.IBeamCursor if self.near_text(point) else Qt.CursorShape.ArrowCursor
                elif self.mode != "select":
                    shape = Qt.CursorShape.CrossCursor
                else:
                    shape = Qt.CursorShape.ArrowCursor
                self.viewport().setCursor(QCursor(shape))
            super().mouseMoveEvent(event)
            return
        kind = drag["kind"]
        if kind == "text":
            self._show_text(self._text_selection(drag["start"], point))
        elif kind == "erase":
            self._erase_at(point)
        elif kind == "band":
            drag["item"].setRect(QRectF(drag["start"], self._clamp(point)).normalized())
        elif kind == "click" and "item" in drag:  # (a callout: its box follows the mouse)
            tip = drag["start"]
            box = self._callout_box(tip, self._clamp(point))
            drag["item"].set_annotation(self._new("callout", box, (((tip.x(), tip.y()),),)))
        elif kind == "draw":
            r = QRectF(drag["start"], self._clamp(point)).normalized()
            a, b = (r.left(), r.top()), (r.right(), r.bottom())
            drag["item"].set_annotation(self._new(self.mode, (*a, *b), self._box_paths(a, b)))
        elif kind in ("line", "ink"):
            p = self._clamp(point)
            if kind == "line":
                drag["points"] = [drag["points"][0], (p.x(), p.y())]
            elif math.hypot(p.x() - drag["points"][-1][0], p.y() - drag["points"][-1][1]) * self.zoom() >= 2:
                drag["points"].append((p.x(), p.y()))
            paths = (tuple(drag["points"]),)
            drag["item"].set_annotation(self._new(self.mode, annots.frame(self.mode, paths, 1), paths))
        elif kind == "edit":
            new = self._edited(drag, point)
            if new is not None:
                drag["item"].set_annotation(new)
                drag["moved"] = True
        event.accept()

    def _edited(self, drag: dict, point: QPointF) -> Annotation | None:
        """The annotation dragged, as it is with the mouse at POINT."""
        a: Annotation = drag["original"]
        edges = drag["edges"]
        if a.kind in MARKUP or a.locked:  # (they belong to their text, or are locked)
            return None
        if edges.startswith("v"):
            p = self._clamp(point)
            return annots.with_vertex(a, int(edges[1:]), (p.x(), p.y()))
        r = qrect(a.rect)
        if not edges:
            delta = point - drag["start"]
            r.translate(delta)
            # (kept on the page)
            dx = max(self.page_size.left() - r.left(), 0) + min(self.page_size.right() - r.right(), 0)
            dy = max(self.page_size.top() - r.top(), 0) + min(self.page_size.bottom() - r.bottom(), 0)
            r.translate(dx, dy)
        else:
            p = self._clamp(point)
            if "l" in edges:
                r.setLeft(p.x())
            if "r" in edges:
                r.setRight(p.x())
            if "t" in edges:
                r.setTop(p.y())
            if "b" in edges:
                r.setBottom(p.y())
            r = r.normalized()
            if r.width() < MIN_SIZE or r.height() < MIN_SIZE:
                return None
            if a.kind == "stamp" and a.image:  # (its picture keeps its proportions)
                ratio = (a.rect[2] - a.rect[0]) / max(a.rect[3] - a.rect[1], 0.01)
                r.setHeight(r.width() / ratio)
        rect = (r.left(), r.top(), r.right(), r.bottom())
        if a.kind == "callout":  # (its box moves alone: it still points at the same place)
            return dataclasses.replace(a, rect=tuple(round(v, 2) for v in rect))
        return annots.fitted(a, rect)

    def mouseReleaseEvent(self, event):
        drag, self._drag = self._drag, None
        if drag is None or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        point = self.mapToScene(event.position().toPoint())
        moved = (point - drag["start"]).manhattanLength() * self.zoom() > 3
        kind = drag["kind"]
        if kind == "text":
            rects = self._text_selection(drag["start"], point) if moved else []
            for item in drag["marks"]:
                self.scene().removeItem(item)
            if rects:
                self.text_chosen.emit(rects)
            elif drag["candidate"] is not None:
                self.picked.emit([drag["candidate"].index], False)
        elif kind == "erase":
            for mark in drag["marks"]:
                self.scene().removeItem(mark)
            radius = ERASER / (self.zoom() or 1)
            changes: dict = {}
            for item in self.items_:
                if item.annot.locked:
                    continue
                if item.annot.kind == "ink" and item.index in drag.get("ink", {}):
                    left = erase_ink(drag["ink"][item.index], drag["centres"], radius)
                    if left != drag["ink"][item.index]:
                        changes[item.index] = left
                elif item.opacity() < 0.5:
                    changes[item.index] = None
            if changes:
                self.erased.emit(changes)
        elif kind == "band":
            r = drag["item"].rect()
            self.scene().removeItem(drag["item"])
            if moved:
                inside = [i.index for i in self.items_ if r.intersects(i.frame())]
                self.picked.emit(inside, drag["add"])
        elif kind == "click":
            self._clicked(drag, point)
        elif kind == "draw":
            annotation = drag["item"].annot
            self.scene().removeItem(drag["item"])
            r = qrect(annotation.rect)
            if self.mode == "freetext" and (r.width() < MIN_SIZE * 4 or r.height() < MIN_SIZE * 4):
                w, h = FREETEXT_SIZE
                x = max(min(drag["start"].x(), self.page_size.right() - w), self.page_size.left())
                y = max(min(drag["start"].y(), self.page_size.bottom() - h), self.page_size.top())
                self.drawn.emit(self._new("freetext", (round(x, 2), round(y, 2), round(x + w, 2), round(y + h, 2))))
            elif r.width() >= MIN_SIZE and r.height() >= MIN_SIZE:
                rounded = tuple(round(v, 2) for v in (r.left(), r.top(), r.right(), r.bottom()))
                paths = self._box_paths(rounded[:2], rounded[2:])
                annotation = self._new(self.mode, rounded, paths)
                if paths:
                    annotation = dataclasses.replace(annotation, rect=annots.frame(self.mode, paths, annotation.width))
                self.drawn.emit(annotation)
        elif kind in ("line", "ink"):
            self.scene().removeItem(drag["item"])
            points = tuple((round(x, 2), round(y, 2)) for x, y in drag["points"])
            if kind == "line":
                p = self._clamp(point)
                points = (points[0], (round(p.x(), 2), round(p.y(), 2)))
            length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
            if length >= MIN_SIZE:
                annotation = self._new(self.mode, (0, 0, 0, 0), (points,))
                self.drawn.emit(dataclasses.replace(annotation, rect=annots.frame(
                    annotation.kind, annotation.paths, annotation.width)))
        elif kind == "edit":
            if drag["moved"]:
                self.edited.emit(drag["item"].index, drag["item"].annot)
        event.accept()

    def _clicked(self, drag: dict, point: QPointF):
        """A click (or a drag) with a tool of CLICKS: a note, a caret or a stamp there, or a callout."""
        start = drag["start"]
        if self.mode == "callout":
            self.scene().removeItem(drag["item"])
            box = self._callout_box(start, self._clamp(point))
            self.drawn.emit(self._new("callout", box, (((round(start.x(), 2), round(start.y(), 2)),),)))
            return
        if self.mode == "stamp":
            end = self._clamp(point)
            if (end - start).manhattanLength() * self.zoom() > 6:  # (dragged: as wide as that)
                r = QRectF(start, end).normalized()
                self.drawn.emit(self._new("stamp", (r.left(), r.top(), r.right(), r.top())))
            else:  # (a click: of its usual size, there; the window knows it)
                self.drawn.emit(self._new("stamp", (start.x(), start.y(), start.x(), start.y())))
            return
        w, h = (NOTE_SIZE, NOTE_SIZE) if self.mode == "note" else \
            annots.shown_size(self.page.rotation if self.page is not None else 0, CARET_SIZE)
        if self.mode == "caret":  # (the caret's point where the click was)
            x, y = start.x() - w / 2, start.y() - h
        else:
            x, y = start.x(), start.y()
        x = max(min(x, self.page_size.right() - w), self.page_size.left())
        y = max(min(y, self.page_size.bottom() - h), self.page_size.top())
        self.drawn.emit(self._new(self.mode, (round(x, 2), round(y, 2), round(x + w, 2), round(y + h, 2))))

    def word_at(self, point: QPointF) -> str:
        """The word under POINT (on the page), or ''."""
        if self.page is None:
            return ""
        for w in self.page.get_text("words", sort=False):
            r = pymupdf.Rect(w[:4]) * self.page.rotation_matrix
            if r.normalize().contains(pymupdf.Point(point.x(), point.y())):
                return w[4]
        return ""

    def flash(self, rect: Rect):
        """Bring RECT into view, and show it for a moment (an annotation chosen in the list)."""
        color = QColor(255, 200, 0, 90)
        pen = QPen(QColor(230, 120, 0), 2)
        pen.setCosmetic(True)
        item = QGraphicsRectItem(qrect(rect).adjusted(-3, -3, 3, 3))
        item.setPen(pen)
        item.setBrush(QBrush(color))
        item.setZValue(4)
        self.scene().addItem(item)
        self.ensureVisible(item, 60, 60)

        def remove():
            try:
                if item.scene() is not None:
                    item.scene().removeItem(item)
            except RuntimeError:  # (the page was shown again meanwhile: the item is gone)
                pass

        QTimer.singleShot(900, remove)

