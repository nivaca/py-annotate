Open-source software used by py-annotate
========================================

py-annotate is licensed under the GNU General Public License, version 3 or
later (GPL-3.0-or-later). It is made with the open-source software listed
here. The licences are those of the versions in `uv.lock` for py-annotate
1.1.1; the identifiers are SPDX identifiers. All of them allow their use in
a program under the GPL, version 3 or later.

Libraries the program needs
---------------------------

These are installed with py-annotate (`pyproject.toml`), and the AppImage
carries them.

| Software | What it does in py-annotate | Licence |
|---|---|---|
| [Python](https://www.python.org/) 3.14 | the language; the AppImage carries its own | PSF-2.0 |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | reads, draws and writes the PDF and its annotations | AGPL-3.0-or-later (or a commercial licence from Artifex) |
| [MuPDF](https://mupdf.com/) | the PDF library inside PyMuPDF | AGPL-3.0-or-later (or a commercial licence from Artifex) |
| [PySide6](https://doc.qt.io/qtforpython-6/) and Shiboken6 | the window (Qt for Python) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [Qt](https://www.qt.io/) 6 | the toolkit under PySide6, carried in its wheels | LGPL-3.0-only (open-source licence) |

PyMuPDF 2 brings these other packages with it. py-annotate does not use
them itself, but they are installed and carried in the AppImage:

| Software | Licence |
|---|---|
| [pymupdf-layout](https://pypi.org/project/pymupdf-layout/), [pymupdf4llm](https://pypi.org/project/pymupdf4llm/) (empty packages, kept for upgrades from PyMuPDF 1) | the licence of PyMuPDF |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | MIT |
| [NumPy](https://numpy.org/) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| [NetworkX](https://networkx.org/) | BSD-3-Clause |
| [Protocol Buffers](https://github.com/protocolbuffers/protobuf) (protobuf) | BSD-3-Clause |
| [FlatBuffers](https://github.com/google/flatbuffers) | Apache-2.0 |
| [packaging](https://github.com/pypa/packaging) | Apache-2.0 OR BSD-2-Clause |
| [psutil](https://github.com/giampaolo/psutil) | BSD-3-Clause |
| [PyYAML](https://pyyaml.org/) | MIT |
| [tabulate](https://github.com/astanin/python-tabulate) | MIT |

The RPM for Fedora uses Fedora's own packages of PyMuPDF and PySide6
(`python3-pymupdf`, `python3-pyside6`), under the same licences.

Programs used when they are installed
-------------------------------------

py-annotate runs these as separate programs, for two of its features. They
are not part of it and are not carried in the AppImage.

| Software | What for | Licence |
|---|---|---|
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | the searchable copies of scanned pages (OCR, through MuPDF); the RPM recommends it | Apache-2.0 |
| pdf2iso, by the same author | the copies as PDF/A and PDF/X | GPL-3.0-or-later |
| [Ghostscript](https://www.ghostscript.com/), used by pdf2iso | the conversion to PDF/A and PDF/X | AGPL-3.0-or-later |
| [pikepdf](https://github.com/pikepdf/pikepdf), used by pdf2iso | the PDF/A and PDF/X copies | MPL-2.0 |

Tools for development, testing and packaging
--------------------------------------------

These are used to make, test and build py-annotate, and are not part of
what is installed (the AppImage runtime excepted, which is the start of
every AppImage).

| Software | What for | Licence |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) and uv_build | the environment, the lock file, the wheel and the source package | MIT OR Apache-2.0 |
| [pytest](https://pytest.org/) | the tests | MIT |
| pluggy, iniconfig, [Pygments](https://pygments.org/) (brought by pytest) | the tests | MIT, MIT, BSD-2-Clause |
| [python-appimage](https://github.com/niess/python-appimage) | the relocatable Python inside the AppImage | GPL-3.0 |
| [appimagetool](https://github.com/AppImage/appimagetool) and the AppImage runtime | making the AppImage | MIT |
| [RPM](https://rpm.org/) (rpmbuild) | the RPM | GPL-2.0-or-later |
| [desktop-file-utils](https://www.freedesktop.org/wiki/Software/desktop-file-utils/) | checking the menu entry in the RPM | GPL-2.0-or-later |
| [AppStream](https://www.freedesktop.org/wiki/Distributions/AppStream/) (appstreamcli) | checking the metainfo file in the RPM | LGPL-2.1-or-later |
| [Git](https://git-scm.com/) | version control | GPL-2.0-only |
