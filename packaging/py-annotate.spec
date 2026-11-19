# py-annotate, which adds annotations to PDF documents.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENSE file, or <https://www.gnu.org/licenses/>.
#
# Build with packaging/build-rpm.sh, which makes the source tarball.

Name:           py-annotate
Version:        0.4.3
Release:        1%{?dist}
Summary:        Add annotations to PDF documents: highlights, notes, text boxes, shapes, stamps

License:        GPL-3.0-or-later
URL:            https://github.com/nivaca/py-annotate
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
BuildRequires:  /usr/bin/appstreamcli
# For %%check: the tests run the window (headless).
BuildRequires:  python3-pytest
BuildRequires:  python3-pyside6

# PyMuPDF comes from the package's metadata (pyproject.toml).
# The window: Fedora's PySide6 (pyproject.toml names the PyPI wheel, pyside6-essentials).
Requires:       python3-pyside6
Requires:       hicolor-icon-theme
# (for the searchable copies of scanned pages: OCR)
Recommends:     tesseract
Recommends:     tesseract-langpack-eng

%description
py-annotate adds annotations to PDF documents: highlights, underlines and
strikeouts over the text, notes, text boxes and callouts, rectangles,
ellipses, polygons, clouds, lines, arrows, drawings made by hand, and stamps.
They are written as ordinary PDF annotations, which any PDF viewer shows and
can edit; those a document already has can be edited too. The annotations
can be searched, filtered, exported (Markdown, CSV, JSON) and imported.

The window is in English or Spanish.

%prep
%autosetup -n %{name}-%{version}
# (Fedora's PySide6 is python3-pyside6, which doesn't provide pyside6-essentials)
sed -i '/"pyside6-essentials/d' pyproject.toml

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l py_annotate
desktop-file-install --dir=%{buildroot}%{_datadir}/applications packaging/py-annotate.desktop
install -d %{buildroot}%{_datadir}/icons
cp -pr src/py_annotate/icons/linux/hicolor %{buildroot}%{_datadir}/icons/
install -Dpm 0644 packaging/io.github.nivaca.py-annotate.metainfo.xml \
    %{buildroot}%{_metainfodir}/io.github.nivaca.py-annotate.metainfo.xml
install -Dpm 0644 packaging/man/py-annotate.1 %{buildroot}%{_mandir}/man1/py-annotate.1
install -Dpm 0644 packaging/man/es/py-annotate.1 %{buildroot}%{_mandir}/es/man1/py-annotate.1

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/py-annotate.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/io.github.nivaca.py-annotate.metainfo.xml
%pyproject_check_import -e 'py_annotate.gui*'
# The whole test suite, on the installed package, with no settings of the
# builder's and the window drawn offscreen.
export HOME="$PWD/check-home" PY_ANNOTATE_CONFIG="$PWD/check-home/config" QT_QPA_PLATFORM=offscreen
%pytest -q tests
%{py3_test_envvars} %{buildroot}%{_bindir}/py-annotate --version | grep -q '%{version}'

%files -f %{pyproject_files}
%doc README.md README_es.md docs/DESCRIPTION.md docs/DESCRIPCIÓN_es.md
%{_bindir}/py-annotate
%{_datadir}/applications/py-annotate.desktop
%{_datadir}/icons/hicolor/*/apps/py-annotate.*
%{_metainfodir}/io.github.nivaca.py-annotate.metainfo.xml
%{_mandir}/man1/py-annotate.1*
%lang(es) %{_mandir}/es/man1/py-annotate.1*

%changelog
* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.3-1
- Version 0.4.3: better support for the pen of a tablet

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.2-1
- Version 0.4.2: searchable copies of scanned documents (OCR, with Tesseract)

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.1-1
- Version 0.4.1: layers of annotations

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.0-1
- Version 0.4.0: the pressure of a pen counts along a stroke

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.9-1
- Version 0.3.9: links, attached files, sounds and other annotations are listed,
  read only

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.8-1
- Version 0.3.8: entries of textual criticism, and the critical apparatus

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.7-1
- Version 0.3.7: groups of annotations

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.6-1
- Version 0.3.6: text boxes with bold, italic, underlined, coloured text and
  other fonts, and a border of a colour of its own

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.5-1
- Version 0.3.5: the installers are tried on Linux, macOS and Windows, on GitHub

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.4-1
- Version 0.3.4: the copies, printing, export and import of the main window in
  a module of their own

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.3-1
- Version 0.3.3: opening and saving are faster (the pages are rendered from the
  document itself, and saving reads only what it changed)

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.2-1
- Version 0.3.2: a change is shown at once with thousands of annotations (only
  the annotations that changed are drawn again; the list fits its columns to
  a sample of its rows)

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.1-1
- Version 0.3.1: searching the list is fast (the words of each page are read once,
  and the list is searched when the typing stops)

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.0-1
- Version 0.3.0: annotations changed where they are, and saved incrementally (signatures
  stay valid); undo after saving; replies and review statuses, tags and
  categories; XFDF; a summary of the comments; Find and highlight; continuous
  scrolling; text written on the page; printing; installers for Windows and
  macOS; the manual and the metainfo

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.2.1-1
- Version 0.2.1: PDF/A and PDF/X can be chosen as soon as pdf2iso is given in
  Settings

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.2.0-1
- Version 0.2.0: copies as PDF/A and PDF/X, made by pdf2iso (the annotations
  Ghostscript leaves out can be made part of the pages); the list of the
  annotations, with their authors, in a panel that can be hidden (F4)

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.1.0-1
- First package: the window, in English or Spanish, with a menu entry that
  also opens PDF files
