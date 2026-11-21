Software libre que usa py-annotate
==================================

py-annotate se distribuye bajo la Licencia Pública General de GNU, versión
3 o posterior (GPL-3.0-or-later). Está hecho con el software libre de esta
lista. Las licencias son las de las versiones de `uv.lock` para py-annotate
1.1.1, con sus identificadores SPDX. Todas permiten usarlo en un programa
bajo la GPL, versión 3 o posterior.

Bibliotecas que el programa necesita
------------------------------------

Se instalan con py-annotate (`pyproject.toml`), y la AppImage las lleva.

| Software | Qué hace en py-annotate | Licencia |
|---|---|---|
| [Python](https://www.python.org/) 3.14 | el lenguaje; la AppImage lleva el suyo | PSF-2.0 |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | lee, dibuja y escribe el PDF y sus anotaciones | AGPL-3.0-or-later (o una licencia comercial de Artifex) |
| [MuPDF](https://mupdf.com/) | la biblioteca de PDF que hay dentro de PyMuPDF | AGPL-3.0-or-later (o una licencia comercial de Artifex) |
| [PySide6](https://doc.qt.io/qtforpython-6/) y Shiboken6 | la ventana (Qt para Python) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [Qt](https://www.qt.io/) 6 | la biblioteca gráfica debajo de PySide6, que viene en sus ruedas | LGPL-3.0-only (licencia libre) |

PyMuPDF 2 trae consigo estos otros paquetes. py-annotate no los usa
directamente, pero quedan instalados y van en la AppImage:

| Software | Licencia |
|---|---|
| [pymupdf-layout](https://pypi.org/project/pymupdf-layout/), [pymupdf4llm](https://pypi.org/project/pymupdf4llm/) (paquetes vacíos, que se conservan para actualizar desde PyMuPDF 1) | la de PyMuPDF |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | MIT |
| [NumPy](https://numpy.org/) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| [NetworkX](https://networkx.org/) | BSD-3-Clause |
| [Protocol Buffers](https://github.com/protocolbuffers/protobuf) (protobuf) | BSD-3-Clause |
| [FlatBuffers](https://github.com/google/flatbuffers) | Apache-2.0 |
| [packaging](https://github.com/pypa/packaging) | Apache-2.0 OR BSD-2-Clause |
| [psutil](https://github.com/giampaolo/psutil) | BSD-3-Clause |
| [PyYAML](https://pyyaml.org/) | MIT |
| [tabulate](https://github.com/astanin/python-tabulate) | MIT |

El RPM para Fedora usa los paquetes de PyMuPDF y PySide6 de la propia
Fedora (`python3-pymupdf`, `python3-pyside6`), con las mismas licencias.

Programas que usa si están instalados
-------------------------------------

py-annotate los corre como programas aparte, para dos de sus funciones. No
forman parte de él ni van en la AppImage.

| Software | Para qué | Licencia |
|---|---|---|
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | las copias con texto buscable de las páginas escaneadas (OCR, por medio de MuPDF); el RPM lo recomienda | Apache-2.0 |
| pdf2iso, del mismo autor | las copias en PDF/A y PDF/X | GPL-3.0-or-later |
| [Ghostscript](https://www.ghostscript.com/), que usa pdf2iso | la conversión a PDF/A y PDF/X | AGPL-3.0-or-later |
| [pikepdf](https://github.com/pikepdf/pikepdf), que usa pdf2iso | las copias en PDF/A y PDF/X | MPL-2.0 |

Herramientas de desarrollo, pruebas y empaquetado
-------------------------------------------------

Sirven para hacer, probar y empaquetar py-annotate, y no forman parte de lo
que se instala (salvo el runtime de AppImage, que es el comienzo de toda
AppImage).

| Software | Para qué | Licencia |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) y uv_build | el entorno, el archivo de bloqueo, la rueda y el paquete fuente | MIT OR Apache-2.0 |
| [pytest](https://pytest.org/) | las pruebas | MIT |
| pluggy, iniconfig, [Pygments](https://pygments.org/) (los trae pytest) | las pruebas | MIT, MIT, BSD-2-Clause |
| [python-appimage](https://github.com/niess/python-appimage) | el Python reubicable que va dentro de la AppImage | GPL-3.0 |
| [appimagetool](https://github.com/AppImage/appimagetool) y el runtime de AppImage | armar la AppImage | MIT |
| [RPM](https://rpm.org/) (rpmbuild) | el RPM | GPL-2.0-or-later |
| [desktop-file-utils](https://www.freedesktop.org/wiki/Software/desktop-file-utils/) | comprobar la entrada del menú en el RPM | GPL-2.0-or-later |
| [AppStream](https://www.freedesktop.org/wiki/Distributions/AppStream/) (appstreamcli) | comprobar el archivo metainfo en el RPM | LGPL-2.1-or-later |
| [Git](https://git-scm.com/) | el control de versiones | GPL-2.0-only |
