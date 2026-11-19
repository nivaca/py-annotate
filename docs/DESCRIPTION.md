How py-annotate keeps the annotations
=====================================

*(Español: [DESCRIPCIÓN_es.md](DESCRIPCIÓN_es.md))*

py-annotate writes ordinary PDF annotations, of the kinds the PDF standard
has, so that any viewer shows them and can edit them. This page tells how
each one is written, and what is done to keep a document as it was.

The kinds of annotations
------------------------

| In py-annotate             | In the PDF                                    |
|----------------------------|-----------------------------------------------|
| Highlight, underline, strikeout, squiggly underline | Highlight, Underline, StrikeOut, Squiggly, with a quadrilateral for each line of text |
| Insert text                | Caret                                         |
| Note                       | Text, with its icon                           |
| Text box                   | FreeText                                      |
| Callout                    | FreeText with the intent FreeTextCallout, and its line (/CL) |
| Area highlight             | Square, filled, with no border, and the subject "Area highlight" |
| Rectangle, ellipse         | Square, Circle                                |
| Polygon, cloud             | Polygon (a cloud has a cloudy border, /BE)    |
| Line, arrow                | Line, with its ends (/LE)                     |
| Polyline                   | PolyLine                                      |
| Freehand                   | Ink                                           |
| Freehand highlight         | Ink, wide and see-through, with the subject "Freehand highlight" |
| Stamp                      | Stamp: a standard one by its name, or one of the user's as a picture |

The author is the annotation's title (/T), the comment its contents
(/Contents), and the dates its creation date and its modification date (/M).
A locked annotation has the PDF's flag Locked.

Replies and review statuses
---------------------------

A reply is a note (Text) that answers the annotation (/IRT). A review status
is a reply too, with the state (/State: Accepted, Rejected, Cancelled,
Completed or None) and its model (/StateModel Review). This is how PDF
viewers keep them, and they show them in the same way. The status of an
annotation is that of its last reply that gives one.

Tags and categories
-------------------

The PDF standard has no tags nor categories, so py-annotate keeps them in two
keys of its own in each annotation, /PyAnnotateTags and
/PyAnnotateCategories, as texts with the names separated by commas. Other
programs leave keys they don't know alone. Exported as XFDF, they are left
out; exported as JSON, they are kept.

Saving
------

When a document is opened, py-annotate reads its annotations of the kinds
above, with their replies. When it is saved, each one is compared with what
the file has:

* one left as it was is not touched;
* one changed is changed where it is: its points, colours, texts, flags and
  replies are written over the old ones, and all else it has stays (its
  identifier, keys of other programs, the replies that point at it). Then it
  is read back, and only if it is not what it should be is it taken out and
  written again;
* one deleted is taken out, with its replies;
* one new is written, with its replies.

Saving into the document itself adds the changes at its end (an incremental
save): what was in the file stays as it was, byte by byte, and a signed
document keeps its signatures valid for what they signed. A file that can't
take that, or one with a password, is written whole (through a file of its
own, put in its place at the end, so that a failure never leaves it half
written).

Undoing after saving works because each annotation that is still in the file
keeps its number in the history; those that are not are written again if
they are brought back.

Showing the pages
-----------------

The window draws the annotations itself, over the pages. The pages are
rendered without the annotations that can be edited (in a copy kept in
memory, and in a temporary file when they are rendered in another process),
so that an annotation moved is not seen twice. The pages are rendered in
processes of their own, only those in view, so that the window answers at
once even with long, scanned documents.

Recovery copies
---------------

While there are annotations not yet saved, a copy of them is kept every two
minutes (as JSON) in the folder `recovery` of the configuration folder,
with the time and size of the file. When the document is opened again, the
copy is offered only if the file has not changed since.
