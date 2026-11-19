py-annotate
===========

*(Español: [README_es.md](README_es.md))*

py-annotate adds annotations to PDF documents: highlights, underlines and
strikeouts over the text, marks where text is to be inserted, notes, text
boxes and callouts, highlighted regions, rectangles, ellipses, polygons,
clouds, lines, arrows and drawings made by hand, and stamps. Each one can
carry a comment, the name of its author, and the dates when it was made and
last changed.

They are written as ordinary PDF annotations, not painted into the pages.
Any PDF viewer shows them, lists them with their comments, and can change
or remove them; the pages under them stay as they were. The annotations
that a document already has (of the kinds above) are read when it is
opened, so they can be moved, changed or deleted too. Saving rewrites only
the annotations that changed, and never touches the others, nor links,
file attachments or form fields.

It has a window, in English and in Spanish, and is meant to work on Linux,
Windows and macOS. This is version 0.2.1.

I am Nicolas Vaughan (<nicolasvaughan@proton.me>), and I wrote it in 2026.
It is free software, under the GNU General Public License, version 3 or
later (see "Licensing").

Running it
----------

It needs Python 3.14 or later and [uv](https://docs.astral.sh/uv/), which
brings the rest (PyMuPDF and PySide6):

    $ uv run py-annotate [file.pdf]

A PDF can also be opened from File > Open, or dropped on the window.

The tools
---------

Choose a tool in the second toolbar, in the Tools menu, or with its key
(the keys can be changed: see "Settings"):

| Tool               | Key     | What it does                                                 |
|--------------------|---------|--------------------------------------------------------------|
| Select             | V       | selects, moves and resizes; drag around annotations to select several |
| Hand               | M       | dragging moves the page in the window                        |
| Eraser             | E       | drag over annotations to erase them; over a drawing, only what it touches |
| Highlight          | H       | drag over text                                               |
| Area highlight     | Shift+H | drag over a region: a picture, a table, a scanned page        |
| Underline          | U       | drag over text                                               |
| Strikeout          | S       | drag over text                                               |
| Squiggly underline | Q       | drag over text                                               |
| Insert text        | I       | click where text is missing, and write it                     |
| Note               | N       | click on the page                                            |
| Text box           | T       | drag a box, or click, and write the text                      |
| Callout            | Shift+T | press on the place to point at, drag to where the text goes   |
| Stamp              | Shift+S | click (or drag, for its width) where the stamp goes           |
| Rectangle          | R       | drag on the page                                             |
| Ellipse            | O       | drag on the page                                             |
| Polygon            | G       | click each corner; double-click or Enter to end               |
| Cloud              | Shift+G | drag on the page                                             |
| Line               | L       | drag on the page                                             |
| Arrow              | A       | drag on the page                                             |
| Polyline           | Shift+L | click each point; double-click or Enter to end                |
| Freehand           | P       | draw on the page with the mouse                               |

Right-clicking a tool in the toolbar gives its colours, the stamp it puts
(the standard ones, such as Approved, Draft or Confidential, or one of your
own, with your name and the date under its text), and its properties: how
the annotations it makes look, whether the tool stays chosen after making
one (or goes back to Select), and what opens after each one is made (a
field for its text, its comment, its properties, or nothing).

Editing annotations
-------------------

With any tool, an annotation is selected by clicking it (Ctrl adds it to the
selection), moved by dragging it or with the arrow keys (Shift: ten points
at a time), and resized by dragging its edges and corners. The points of a
line, a polygon or a polyline, and the place a callout points at, are
dragged one by one; the box of a callout moves on its own. Marks over text
belong to their text, and are not moved. With a tool for text, a
double-click marks one word.

A double-click on an annotation opens its properties: its colour and fill,
line width, dashes, the ends of a line (arrows, circles, squares...), the
font, size and alignment of a text box, the icon of a note, its opacity,
its text or comment, its author, and whether it is locked (a locked
annotation can't be moved, resized, erased or deleted). Right-clicking it
gives a menu with more: copy the text it marks, or copy it as a quotation
with the name of the document and the page; change a highlight into an
underline; use its style for new annotations; align several.

The Edit menu has Copy, Paste and Duplicate (annotations can be pasted on
another page, or in another document), Lock, Align (sides, centres, the
same size, spread evenly), and the selection of the annotations of a page,
or of those of the same kind.

The list
--------

The panel on the right lists all the annotations of the document, with
their page, kind, author, date and comment (or, for marks over text, the text they
mark). It can be sorted by page, by date, by kind or by author, searched
(comments, texts marked, authors), and filtered by kind, author and colour.
View > Next annotation (Alt+Down) and Previous annotation (Alt+Up) go
through the annotations in the order of the list, and only through those it
shows. View > Show the annotations hides them all, to see the document as
it is; View > Only those the list shows leaves on the pages only those the
search and filters let through. The filter of authors says how many
annotations each author has.

The panel can be hidden (View > The panel of the annotations, or F4), to
give the page the whole width, moved to the left side of the window, or
taken out of it (the buttons on its title).

Below the list, the comment of the annotation selected can be written
directly (C puts the cursor there); it is kept when the field is left.

Saving, exporting, importing
----------------------------

File > Save writes the annotations in the document itself; File > Save as
writes a copy with them, and goes on with the copy. Everything can be
undone (Ctrl+Z) until the document is saved. File > Save a copy writes a
flattened copy (the annotations become part of the pages: every viewer
shows and prints them, but they can no longer be edited), a copy without
any annotation, or a copy as PDF/A-1b, PDF/A-2b, PDF/A-3b (for archiving) or
PDF/X-4 (for printing). These are made by
[pdf2iso](https://github.com/nivaca/pdf2iso), which must be installed: it
is looked for on the PATH, in `~/bin` and in `~/.local/bin`, or Settings
say where it is; without it, those entries are greyed out. Ghostscript,
which pdf2iso uses, leaves out some kinds of annotations (insert-text marks,
polygons and clouds, at least). If it does, py-annotate says which, and
offers to make those part of the pages instead, keeping the others as
annotations. PDF/A and PDF/X can't have a password, so the copy of a
protected document has none.

File > Export the annotations writes those the list shows as a report in
Markdown (how many there are of each kind, colour and author, then each of
them with the text it marks and its comment, page by page), as a table
(CSV), or as JSON, which holds all there is to know of them and can be
imported again. File > Import annotations brings them in from such a JSON
file, or from another copy of the PDF, for instance one annotated by someone
else; their authors are kept, and those already in the document are left
out.

While there are annotations not yet saved, a recovery copy of them is kept
every two minutes. If the program stops before they are saved, they are
offered when the document is opened again (if the file has not changed
meanwhile).

Settings
--------

Settings > Settings has three parts:

* General: the name written as author in new annotations, how often the
  recovery copy is kept, where pdf2iso is (empty: looked for), and a way to put the tools back as they were at
  first.
* Colours: the colours offered in the menus, and what each one means to you
  (by default, yellow for what is important, green for definitions, blue for
  references, pink for questions, orange for arguments, purple for context,
  red for errors to check). The meanings are shown with the colours in the
  menus, the list and the exported files.
* Shortcuts: the key of each tool and action. Two actions can't have the
  same key.

The language is chosen in Settings > Language.

These settings are kept in a small TOML file, `config.toml`, in
`~/.config/py-annotate` on Linux, `~/Library/Application Support/py-annotate`
on macOS, and `%APPDATA%\py-annotate` on Windows (`$PY_ANNOTATE_CONFIG`
names another folder); the recovery copies, in the folder `recovery` beside
it. Deleting the file gives back the usual values.

What it does not do yet
-----------------------

* It does not save incrementally: a digital signature is no longer valid once the document is saved.
* Replies to annotations, review states, tags, categories, groups and
  layers are not there yet. Replies already in a document are kept as they
  are, but are not shown.
* Annotations of other kinds (links, sounds, file attachments, measurements)
  are kept as they are, but are not shown in the list and cannot be edited.
* A text box has one font (Helvetica, Times or Courier) and one colour for
  all its text, and its border has the colour of its text.
* Pens with pressure, and annotations that rotate, are not there.

Tests
-----

    $ uv run pytest

Licensing
---------

py-annotate is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option)
any later version. It is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file
[LICENSE](LICENSE) for the details.
