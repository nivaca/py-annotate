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
Version:        0.2.0
Release:        1%{?dist}
Summary:        Add annotations to PDF documents: highlights, notes, text boxes, shapes, stamps

License:        GPL-3.0-or-later
URL:            https://github.com/nivaca/py-annotate
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
# For %%check: the tests run the window (headless).
BuildRequires:  python3-pytest
BuildRequires:  python3-pyside6

# PyMuPDF comes from the package's metadata (pyproject.toml).
# The window: Fedora's PySide6 (pyproject.toml names the PyPI wheel, pyside6-essentials).
Requires:       python3-pyside6
Requires:       hicolor-icon-theme

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

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/py-annotate.desktop
%pyproject_check_import -e 'py_annotate.gui*'
# The whole test suite, on the installed package, with no settings of the
# builder's and the window drawn offscreen.
export HOME="$PWD/check-home" PY_ANNOTATE_CONFIG="$PWD/check-home/config" QT_QPA_PLATFORM=offscreen
%pytest -q tests
%{py3_test_envvars} %{buildroot}%{_bindir}/py-annotate --version | grep -q '%{version}'

%files -f %{pyproject_files}
%doc README.md README_es.md
%{_bindir}/py-annotate
%{_datadir}/applications/py-annotate.desktop
%{_datadir}/icons/hicolor/*/apps/py-annotate.*

%changelog
* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.2.0-1
- Version 0.2.0: copies as PDF/A and PDF/X, made by pdf2iso (the annotations
  Ghostscript leaves out can be made part of the pages); the list of the
  annotations, with their authors, in a panel that can be hidden (F4)

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.1.0-1
- First package: the window, in English or Spanish, with a menu entry that
  also opens PDF files
