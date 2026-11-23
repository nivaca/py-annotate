# Changelog

All notable changes to py-annotate. The releases, with the source ZIP,
the AppImage and the signed RPM, are on
[Codeberg](https://codeberg.org/nivaca/py-annotate/releases) and
[GitHub](https://github.com/nivaca/py-annotate/releases); the RPM is also
built on Copr. Some versions (0.2.0, 0.3.1 to 0.3.3, and others) were
made but not released apart: each is told in the section of the next
release.

## 1.1.2 — 2026-11-22

### Added

- **Every release signed**: besides the RPM, each file published (the
  wheel, the source, the ZIP, the AppImage) comes with
  its signature (`.asc`), with `SHA256SUMS` and its signature, and with the
  public key; the tag of the version is signed too. Each signature is
  checked with the published key before anything is published. The README
  says how to check a download.

## 1.1.1 — 2026-11-21

### Added

- **The software used, and its licences.** `docs/THIRD_PARTY.md` (and
  `docs/THIRD_PARTY_es.md`, in Spanish) lists the open-source software
  py-annotate uses: the libraries it needs and those PyMuPDF brings, the
  programs it runs when they are installed (Tesseract, pdf2iso and
  Ghostscript), and the tools that build and test it, each with its
  licence. The READMEs link to it.
- **This changelog**, in English and Spanish.

## 1.1.0 — 2026-11-19

This release takes in 1.0.3 to 1.0.7.

### Added

- **Strokes as curves, and dots.** A tap with the freehand tool makes a
  dot (the dot of an i, a full stop), which was thrown away before. Each
  stroke is drawn as a curve through its points (a Catmull-Rom spline, as
  cubic Bezier segments), in the window and in the PDF. Taken from the pen
  code of PdfCraft (MIT or Apache 2.0).
- **Replace text** (Shift+I): dragged over text, it strikes it out (`/IT
  /StrikeOutTextEdit`) and writes the new text in an insert-text mark at
  its end (`/IT /Replace`), the two one group, so that other viewers show
  a replacement.
- **Comparing two versions of a text.** File > Compare with another
  version marks what differs from another version of the text: changed
  words in orange, with the other's words in their comment; words only
  here in red; and an insert-text mark where the other's words are
  missing. The words are lined up with a patience diff (`compare.py`),
  which takes three seconds on 300 pages, where difflib took nearly two
  minutes and gave hundreds of false differences.
- Typewriter (Y), a text box with no border nor fill
  (`/IT /FreeTextTypeWriter`), and Check mark (K), a check mark, cross,
  dot or dash, for filling forms that have no fields.
- Attach a file (Shift+A): file-attachment annotations are now edited,
  not only listed; the file can be opened or saved again from the
  right-click menu. JSON keeps the file; XFDF leaves it out.
- Signature (Shift+K): drawn once by hand, kept on this computer only,
  and put on the page with each click.

### Changed

- **A better Find and highlight.** It finds a word hyphenated at the end
  of a line; it can ignore accents and ligatures (accion: acción; caesar:
  cæsar) and take u and v, i and j as one letter, as in Latin and
  medieval texts; it takes `*` and `?` as wildcards; it has Previous and
  Next, and remembers the searches and its options. The search of the
  panel's list ignores accents too.
- The intent of strikeouts and insert-text marks is read and kept.
- The manual pages and the metainfo tell of the new tools and versions.

### Fixed

- The freehand highlight was never drawn in the window, only in the file.
- On Windows, the history of searches was lost: it is now kept as JSON,
  in the same settings as the window's state.

## 1.0.2 — 2026-11-19

- **Writing by hand with a pen is one drawing.** The freehand tools draw
  even over other annotations (moving them is for Select). Strokes made
  within a second and a half of the one before, near it (40 points), with
  the same tool and look, are added to that drawing, so a word or a line
  is one annotation; undo still takes back one stroke at a time.
- The pressure gives each drawing its width once, by its first stroke;
  cutting strokes by pressure is still a choice in Settings.

## 1.0.1 — 2026-11-19

- View > The thumbnails of the pages (F3) shows or hides them, and the
  window remembers it. While they are hidden, they are not drawn.

## 1.0.0 — 2026-11-19

- The first stable version. The manual pages tell what the program does
  now (textual criticism, groups, layers, formatted text, OCR, the pen of
  a tablet), and the metainfo lists the versions released.
- (0.4.4) While a side button of a tablet's pen is held, the page follows
  the pen, as with the hand tool, whatever tool is chosen; Settings can
  make it a right click again.

## 0.4.3 — 2026-11-19

This release takes in 0.4.1 and 0.4.2.

- **Layers.** The Layers menu puts annotations in layers that can be
  shown or hidden; new annotations go to the layer chosen there. The
  layers are the PDF's optional content (an annotation's `/OC`), so other
  viewers show and hide them as well.
- **Searchable copies of scanned documents.** File > Save a copy >
  Searchable (OCR) reads the text of scanned pages with Tesseract,
  through PyMuPDF, and writes it under their images, invisible, each word
  where it is on the image. The languages are set in Settings (`eng`, or
  `lat+eng`). Without Tesseract the entry is greyed out; the RPM
  recommends it.
- **Better support for the pen of a tablet.** Strokes follow the pen's own
  events, which keep the fractions of a pixel, and are smoothed a little.
  The eraser end of the pen erases while it touches, whatever tool is
  chosen. Settings say how the pressure counts and how hard the pen must
  press.

## 0.4.0 — 2026-11-19

This release takes in 0.3.5 to 0.3.9.

- **The pressure of a pen counts along a stroke.** When the pressure
  changes along a stroke, the stroke is cut there into drawings of
  different widths, joined end to end as one group.
- **Formatted text in text boxes and callouts**: bold, italic, underline,
  colours and fonts (Ctrl+B, Ctrl+I, Ctrl+U, and the right-click menu),
  written as the PDF's rich text (`/RC`, `/DS`), with the plain text kept
  in `/Contents`. The border can have a colour of its own.
- **Groups** (Ctrl+G, Ctrl+Shift+G): grouped annotations are selected,
  moved, copied and deleted together. They are written as PDF groups
  (`/IRT` with `/RT /Group`), and groups made by other programs are read
  and kept.
- **Entries of textual criticism.** Any annotation can carry one: the
  sixteen kinds of the specification (variant reading, emendation,
  conjecture, lacuna...), the readings, the witness, the source, the
  rationale and the confidence. File > Export writes the critical
  apparatus in Markdown.
- Links, attached files and other annotations that py-annotate does not
  edit are listed, locked, with what they point at or hold.
- A workflow on GitHub runs each installer on Linux, macOS and Windows,
  runs the tests against what it installed, and uninstalls it. It found
  three problems, now fixed: a `chmod --` that macOS refuses, a document
  that could not be replaced on Windows because PyMuPDF still had it
  open, and pdf2iso without an extension not found on Windows.

## 0.3.4 — 2026-11-19

This release takes in 0.3.1 to 0.3.3, all about documents with thousands
of annotations.

- Searching the list is fast: the words of each page are read once, and
  the first search takes 0.8 seconds on 300 pages instead of 14 seconds
  with 750 highlights. The list is searched when the typing stops.
- With 3000 annotations, a change takes 0.016 seconds instead of 0.17:
  the columns fit a sample of the rows, and only the annotations that
  changed are drawn again.
- Opening and saving are faster: the document is no longer copied whole
  into a temporary file, and saving no longer reads every annotation
  three times (0.4 seconds instead of 1.4 with 3000 annotations).
- The copies, printing, export and import moved from `window.py` to
  `gui/files.py`; nothing they do has changed.
- `docs/DESCRIPTION.md` and `docs/DESCRIPCIÓN_es.md` in the structure of
  the other projects.

## 0.3.0 — 2026-11-19

- **Annotations changed where they are.** Saving keeps what py-annotate
  does not know of an annotation (its identifier, keys of other programs,
  replies), and saves incrementally, so that signatures stay valid; what
  was done can be undone after saving.
- Replies and review statuses, tags and categories, with filters in the
  panel.
- XFDF export and import, and a summary of the comments as a PDF.
- Find and highlight; printing; a freehand highlight and the pressure of
  a tablet's pen; a continuous view of the pages; thumbnails of the size
  chosen.
- Callouts of other programs are read whichever way their box is given;
  stamps on turned pages are the right way up.
- Installers for Windows and macOS, screenshots, manual pages and the
  metainfo.

## 0.2.1 — 2026-11-19

- (0.2.0) **PDF/A and PDF/X.** File > Save a copy makes PDF/A-1b,
  PDF/A-2b, PDF/A-3b and PDF/X-4 with pdf2iso. Ghostscript leaves out
  some kinds of annotations (insert-text marks, polygons, clouds), so the
  copy is checked, and those can be made part of the pages instead.
- (0.2.0) The list of the annotations is a panel on the right that can be
  hidden (F4), moved or taken out.
- The PDF/A and PDF/X entries can be chosen as soon as pdf2iso is given
  in Settings; before, they were enabled only at the next change of the
  window.

## 0.1.0 — 2026-11-19

- First version: a program to add annotations to PDF documents, written
  as ordinary PDF annotations: highlights, underlines, strikeouts,
  squiggly underlines, insert-text marks, notes, text boxes, callouts,
  area highlights, shapes, lines, arrows, freehand drawings and stamps.
  The annotations a document already has are read and can be edited.
- A window in English and Spanish, with thumbnails, a searchable list of
  the annotations, an eraser, copy and paste, alignment, locking, export
  (Markdown, CSV, JSON), import, flattened copies, recovery copies, a
  palette of colours with meanings, and shortcuts that can be changed.
- Releases as a source ZIP, an AppImage and a signed RPM, also built on
  Copr (`tools/release.py`).
