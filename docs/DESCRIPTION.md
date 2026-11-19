How py-annotate was made
========================

py-annotate is a program for adding annotations to PDF documents:
highlights and other marks over the text, notes, text boxes and callouts,
shapes, drawings made by hand and stamps, with comments, replies, review
statuses, tags and categories. They are written as ordinary PDF
annotations, which any viewer shows and can edit. Nicolas Vaughan made it
in November 2026, starting from two other PDF programs of his, py-redact
(redaction) and py-foliation (the page labels of a PDF), and from a
specification of what a full annotation tool should have. Here I explain
how it was made, in ten stages.

It is free software, under the GNU General Public License, version 3 or
later. The annotations are read and written by PyMuPDF (GNU AGPL 3), and
the window is made with PySide6 (GNU LGPL 3).

Nicolas Vaughan is Associate Professor of Literature at the School of Arts
and Humanities of the Universidad de los Andes, Bogotá, Colombia.

1. A first version from py-redact
---------------------------------

py-redact already had most of what an annotation program needs: a page
drawn by PyMuPDF and shown in a Qt graphics view, marks drawn, moved and
resized on it with the mouse, the pages rendered in processes of their own,
thumbnails, undo, recent files, and the interface in English and Spanish.
py-foliation uses pikepdf and Qt's own PDF module, so less of it could be
taken. The first version kept py-redact's frame and changed what the marks
are: an annotation became a small immutable record with its kind, page,
rectangle, colours, opacity, comment and author, and the points of its
lines when it has them.

Before writing the model I tried what PyMuPDF does with each kind of
annotation, on a page turned 90 degrees as well as on a plain one. It works
in the page's own coordinates, before it is turned; the window works on
the page as it is shown, so every point is turned on the way out and on
the way back. Some things only showed up in these trials: MuPDF makes every
note's icon 16 points square and, on a turned page, puts it beside the
point it is given, so the note is written again where it belongs; a text
box keeps its fill where other annotations keep their line colour; a
rectangle's border is half outside its shape.

The window draws the annotations itself, and the pages are rendered without
those that can be edited, so that an annotation moved is not seen twice.
Saving wrote only the annotations that had changed, and left the others,
and everything else in the file, as they were.

2. The tools of a full annotation program
-----------------------------------------

The second version followed a specification of a complete annotation tool
and the help pages of other programs. The kinds grew to eighteen: area
highlights, insert-text marks, callouts, polygons, clouds, polylines and
stamps were added, with ends for each side of a line, dashes, fonts and
alignment for text boxes, icons for notes, and a lock. Each tool got its
own style and behaviour (whether it stays chosen, what opens after an
annotation is made), set by right-clicking it. The window got an eraser,
selection with a frame, copy and paste, alignment, a list that can be
searched and filtered, colours with meanings, shortcuts that can be
changed, exports to Markdown, CSV and JSON, imports from JSON and from
another copy of the PDF, flattened copies, and recovery copies of what is
not yet saved.

A callout read back from a file showed that its box is kept as differences
from the annotation's rectangle, in an order that is not the one the
standard seems to give; and a plain text box written by PyMuPDF carried a
callout line of no length, which other programs could take for a callout.
Both are now handled.

3. Packages
-----------

The repositories were made on GitHub and Codeberg, and the AppImage, the
signed RPM, the Copr project and the release script came from py-redact.
Codeberg made the repository with its releases switched off, which had to
be changed before the first release. The first Copr build of 0.2.0 failed:
a test passed on my machine only because pdf2iso was installed there, and
Copr builds in a clean system. The bug it hid was real (the PDF/A entries
were enabled only at the next change of the window). It was fixed as
0.2.1, and the tests are now also run with nothing of mine on the PATH
before a release.

4. PDF/A, PDF/X and a panel
---------------------------

Copies as PDF/A and PDF/X are made by pdf2iso, as in my other programs. The
first trial showed that Ghostscript, which pdf2iso uses, leaves out some
kinds of annotations: insert-text marks, polygons and clouds. py-annotate
now compares the copy with what it wrote, says which were left out, and
offers to make only those part of the pages, keeping the others as
annotations. The list of the annotations moved into a panel that can be
hidden, moved or taken out of the window.

5. Keeping the document as it was
---------------------------------

Until then a changed annotation was taken out and written again, which
lost what py-annotate doesn't know of it: its identifier, keys of other
programs, the replies that point at it. Now it is changed where it is: its
points, colours, texts and flags are written over the old ones, and then it
is read back; only if it is not what it should be is it written again.
Saving into the document itself adds the changes at its end, so that what
was there stays byte by byte and a signed document keeps its signatures
valid for what they signed. PyMuPDF's incremental save of a document with a
password left the program unable to read it back now and then, so those are
still written whole. Undo now survives saving: each annotation still in the
file keeps its number in the history.

6. Replies, statuses, tags and categories
-----------------------------------------

Replies and review statuses are written as PDF viewers write them: a note
that answers the annotation, and for a status, a state (Accepted, Rejected,
Cancelled, Completed, None). Deleting an annotation with PyMuPDF takes its
replies with it, which the first version of this code did not expect. The
standard has no tags nor categories, so they are kept in two keys of
py-annotate's own, which other programs leave alone; the categories offered
come from the settings.

7. XFDF and the summary of the comments
---------------------------------------

XFDF, the format in which PDF programs exchange annotations, is written and
read by py-annotate itself, with the points turned into the PDF's own space
(from the bottom of the page) and back. The summary of the comments puts
each page with annotations, numbered, beside the list of them. Its text was
first written with Helvetica, which in PyMuPDF has no dashes nor curly
quotes; it is now laid out as HTML, with fonts that cover them.

8. A continuous view, and writing on the page
---------------------------------------------

The page view was written again: each page is an item of the scene, with
its annotations as children, so that the pages can be shown one under the
other and the annotations changed without drawing the pages again. Only the
pages in view are rendered. The text of text boxes, callouts and notes is
now written on the page. The list became a model that makes its rows only
when they are shown, so thousands of annotations are listed at once. Find
and highlight came from py-redact's search, and printing, a freehand
highlight and the pressure of a tablet's pen were added. A test in a clean
system found that an editor losing the focus could keep the text of the
next one, empty; an editor now keeps only its own.

9. Installers, the manual and pictures
--------------------------------------

The installers for Windows, macOS and Linux came from py-redact, the manual
pages and the metainfo for software centres were written, and a script
makes the screenshots of the README in both languages, on an essay it
writes each time. That script once wrote the window's layout into my own
settings, because Qt follows `XDG_CONFIG_HOME`; it now redirects that too.

10. Thousands of annotations
----------------------------

To see where the program was slow, I made a document of 300 pages with
3,000 annotations and timed what the window does with it. Most of it was
quick, but the first letter typed in the search of the list took fourteen
seconds: to find a word in the text a highlight covers, each highlight
asked PyMuPDF for the text of its rectangle, which took 18 milliseconds
each. The words of a page are now read once and kept, the words of a mark
are those whose middle is under it, and the list is searched when the
typing stops; the first search takes less than a second.

Each change took a sixth of a second, because the list measured all its
rows to fit its columns and the pages made all their annotations again;
now a sample of the rows is measured, and only what changed is made again.
A document with annotations was copied whole, without them, at each
opening and each save, for the other processes to render; they now render
the document itself and take the annotations out of their own copy. Saving
read the annotations of the file three times, and now reads only those it
changed: it takes 0.4 seconds instead of 1.4. Reading 3,000 annotations
still takes half a second, spread over many small calls to PyMuPDF, and I
found nothing that made it shorter. Last, what writes or reads other files
than the document (copies, printing, exports and imports) moved out of the
main window's module, which had grown to 2,147 lines, into one of its own.

Testing
-------

The program has 69 tests (`uv run pytest`). The tests of the annotations
write one of each kind on a plain page and on a turned one and read them
back; check that a changed annotation keeps its number and the keys of
other programs, that saving into the document only adds to its end, and
that replies, statuses, tags and categories are kept; and send everything
through JSON and XFDF and back. The window is tested as a user would use
it, with mouse events on the pages: every tool, moving, resizing and
reshaping, the eraser, the panel and its filters, writing on the page,
undo after saving, a save after the file was changed by another program,
the pages rendered in another process without the annotations the window
draws, and the copies as PDF/A (with a pdf2iso made for the
test that leaves out polygons, as Ghostscript does). A test checks that
every text of the window has its Spanish translation, and no other. The
tests are also run with nothing of mine on the PATH, as Copr runs them, and
the RPM runs them again with Fedora's own Python, PyMuPDF and PySide6. The
pictures were checked by eye, in both languages. A document of 300 pages with
3,000 annotations was used to time the window. The program has 37 files,
around 10,000 lines.
