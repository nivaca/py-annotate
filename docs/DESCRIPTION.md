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
how it was made, in fifteen stages.

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

11. The installers on three systems
-----------------------------------

Until then the installers for Windows and macOS had never been run on those
systems. A workflow on GitHub now runs each installer as a user would,
checks what it made, runs the tests against the program installed, and
uninstalls it. Its first runs found three problems that my own machine
could not show. On macOS the installer stopped at a `chmod --`, which the
`chmod` of macOS refuses (py-redact had been fixed already; this copy had
not). On Windows a document with a password could not be saved, because
it is written whole and put in the place of the file, and Windows doesn't
replace a file that PyMuPDF still has open; the document is now closed
first. And `pdf2iso` without an extension was not found there, since
Python's `which` looks only for the extensions Windows knows. A test also
failed on macOS for a reason of its own: the Python of the installer lives
in "Application Support", and a `#!` line can't hold a space.

12. Formatted text, and groups
------------------------------

The text of a text box can now be bold, italic, underlined, of other
colours and in other fonts, and its border can have a colour of its own.
PDF keeps such a text as XHTML (/RC), with its default look in /DS. Trying
it with PyMuPDF showed three things before any code was written: it
misspells the namespace of XHTML; it takes /RC out as soon as the plain
text of the annotation is set; and with rich text, the colour in /DA is
that of the border, not of the text. So py-annotate writes /RC and /DS
itself, after everything else, and uses /DA for the border. The window
paints the rich text with Qt, and I compared it with MuPDF's rendering.

Groups follow the PDF too: each annotation of a group answers the first
(/IRT) as its group (/RT /Group). But MuPDF, when it takes out an
annotation, takes out all that answers it, so deleting the first of a
group, or preparing a page to be shown, deleted the others with it. The
links of the groups are now taken out while the annotations are written,
and put back at the end, and a group is also kept in a key of
py-annotate's own.

13. For the edition of texts
----------------------------

The specification asked for annotations of textual criticism. Any
annotation can now carry an entry of one of its sixteen kinds (variant
reading, emendation, conjecture, lacuna and the others), with the reading
of the text and the other reading, the witness and the place in it, the
source, the rationale and the confidence; and the program exports the
critical apparatus, in the order of the text. Links, attached files and
the other annotations that py-annotate does not edit are now listed,
locked, and saving leaves them alone. Last, the pressure of a tablet's pen
now counts along a stroke, not only for the whole of it: since a drawing
in PDF has one width, a stroke whose pressure changes is cut into drawings
of up to five widths, which make one group.

14. Layers, and scanned pages
-----------------------------

Layers are the PDF's optional content: an annotation names its layer
(/OC), and the document says which layers are shown. py-annotate writes
them so, and a layer hidden in the window is hidden in other viewers once
saved; I checked that MuPDF itself no longer draws it. Since hiding a layer
changes no annotation, it had to count as a change to save on its own.

A scanned page has no text, so none of the tools that mark text could be
used on it. A copy of the document can now be made in which Tesseract,
through PyMuPDF, has read the scanned pages, and each word is written under
the image, invisible, where the image shows it and as wide. Turned pages
were the difficulty: Tesseract reads the page as it is shown, but the words
must be written in the page's own coordinates, turned back. The tests make
a scan, read it, and check that the invisible words are where a second
reading of the copy finds them.

15. The pen of a tablet
-----------------------

Until then the pen was used only through the mouse events Qt makes of it,
which are rounded to whole pixels and come less often. A stroke now follows
the pen's own events, which keep the fractions, and is smoothed a little,
since a tablet records the trembling of the hand. The eraser end of the pen
erases while it touches, whatever tool is chosen; while its side button is
held, the page follows the pen, instead of the right click Qt made of it;
and Settings say how the pressure counts and how hard the pen must press. The tests send the window
the events of a pen, and of its eraser end, as a tablet would. After
trying it with my own Wacom, I published it as version 1.0.0.

Writing by hand with it, though, proved clumsy. Each stroke was an
annotation of its own, selected once made, so the next letter, which
starts on or near it, moved it instead of being drawn; and a stroke whose
pressure changed came out in pieces. Now the pen draws even over other
annotations, strokes made one soon after the other and near each other are
one drawing, and the pressure gives each drawing its width once, by its
first stroke (cutting strokes by pressure is still a choice in Settings).

I then read the pen code of PdfCraft, a PDF editor in Rust (MIT or Apache
2.0), to see what could be taken from it. Two things: a tap of the pen
makes a dot, which py-annotate had thrown away as too short (so the dots
of the i's, and full stops, were lost); and each stroke is drawn as a
curve through its points (a Catmull–Rom spline, as cubic Bézier segments)
instead of straight segments. MuPDF writes the appearance of a drawing
with straight lines, so py-annotate rewrites those lines as curves after
it. Looking at the painting of drawings showed a bug of long standing: the
freehand highlight was never drawn in the window, only in the file.

From PdfCraft came two more ideas. Replace text writes a correction as PDF
programs do: a strikeout and an insert-text mark that holds the new text,
one group. And two versions of a text can be compared: their words, in
reading order, are lined up, and what differs is marked on the document.
The first trial, with difflib on a book of 300 pages, took nearly two
minutes; letting difflib skip the commonest words made it fast but wrong,
with hundreds of false differences. A patience diff solved it: the words
found once in each version are lined up first, as anchors, and only the
short stretches between them are compared word by word. It takes three
seconds, most of them reading the words.

Testing
-------

The program has 100 tests (`uv run pytest`). The tests of the annotations
write one of each kind on a plain page and on a turned one and read them
back, and also text boxes with formatted text and groups made here or by
another program; check that a changed annotation keeps its number and the keys of
other programs, that saving into the document only adds to its end, and
that replies, statuses, tags and categories are kept; and send everything
through JSON and XFDF and back. The window is tested as a user would use
it, with mouse events on the pages: every tool, moving, resizing and
reshaping, the eraser, the panel and its filters, writing on the page,
undo after saving, a save after the file was changed by another program,
the pages rendered in another process without the annotations the window
draws, formatted text written on the page, groups, entries of textual
criticism, the links listed but not changed, a stroke of changing pressure,
layers, searchable copies of scanned pages (when Tesseract is installed),
the pen and its eraser end, and the copies as PDF/A (with a pdf2iso made for the
test that leaves out polygons, as Ghostscript does). A test checks that
every text of the window has its Spanish translation, and no other. The
tests are also run with nothing of mine on the PATH, as Copr runs them, and
the RPM runs them again with Fedora's own Python, PyMuPDF and PySide6. On
GitHub they run on Linux, macOS and Windows, against the program as each
installer installs it. The
pictures were checked by eye, in both languages. A document of 300 pages with
3,000 annotations was used to time the window. The program has 39 files,
around 11,600 lines.
