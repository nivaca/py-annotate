# py-annotate 0.3.1: descripción

## Análisis

py-annotate añade anotaciones a documentos PDF: resaltados, subrayados y tachados sobre el texto, marcas donde falta insertar texto, notas, cuadros de texto y llamadas, zonas resaltadas, rectángulos, elipses, polígonos, nubes, líneas, flechas, dibujos y resaltados a mano alzada, y sellos. Cada anotación puede llevar un comentario, su autor, sus fechas, respuestas, un estado de revisión, etiquetas y categorías. Fue desarrollado en noviembre de 2026 a partir de otros dos programas del autor para PDF, py-redact (la censura) y py-foliation (las etiquetas de página), y de una especificación de lo que debe tener una herramienta de anotación completa.

El requisito central es que las anotaciones sean anotaciones PDF corrientes, no dibujos pegados a las páginas: cualquier visor tiene que mostrarlas, listarlas con sus comentarios y poder cambiarlas, y las páginas debajo deben quedar como estaban. De ahí salen los demás. Las anotaciones que el documento ya tiene, hechas con otros programas, tienen que poder editarse sin perder lo que esos programas guardaron en ellas. Guardar no debe tocar nada más del archivo, y un documento firmado tiene que conservar sus firmas válidas.

La especificación pedía además lo que hace útil una herramienta de lectura y revisión: muchas clases de marcas y formas, cada herramienta con su estilo y su comportamiento, una lista de las anotaciones que se pueda buscar, filtrar y ordenar, respuestas y estados de revisión para el trabajo entre varias personas, etiquetas y categorías para organizar, exportaciones (informe, tabla, datos, XFDF, un resumen en PDF) e importaciones, copias de recuperación, y copias aplanadas, sin anotaciones o como PDF/A y PDF/X. La ventana tenía que estar en español y en inglés.

## Diseño

El trabajo con el PDF lo hace PyMuPDF, que lee y escribe cada clase de anotación del estándar. Una anotación es un registro inmutable con su clase, su página, su rectángulo, sus colores, su opacidad, su comentario, su autor, los puntos de sus líneas, sus respuestas, sus etiquetas y sus categorías. Se mide sobre la página tal como se ve, con su giro; al escribirla se pasa a las coordenadas propias de la página.

El programa se divide en módulos pequeños. `annots.py` define la anotación y la respuesta, y lee y escribe las anotaciones; `exchange.py` exporta e importa (JSON, Markdown, CSV, XFDF, otra copia del PDF) y hace las copias aplanadas, sin anotaciones y el resumen de los comentarios; `search.py` busca texto en las páginas; `recovery.py` guarda las copias de recuperación; `conform.py` pasa a PDF/A y PDF/X con pdf2iso; `settings.py` y `config.py` guardan la configuración, e `interface.py` traduce la ventana. En `gui/` están la ventana (`window.py`), las páginas con sus anotaciones (`canvas.py`, `paint.py`), el panel de las anotaciones (`listing.py`), buscar y resaltar (`finder.py`), la impresión (`printing.py`) y los diálogos.

### Cómo se guardan las anotaciones

Cada clase de py-annotate es una clase del estándar: los resaltados y subrayados son Highlight, Underline, StrikeOut y Squiggly, con un cuadrilátero por línea; la llamada es un FreeText con su línea; la zona resaltada, un Square con relleno, y el resaltado a mano alzada, un Ink, ambos con un asunto que los distingue. Las respuestas son notas que contestan a la anotación (/IRT), y un estado de revisión es una respuesta con /State. El estándar no tiene etiquetas ni categorías, así que se guardan en dos claves propias, /PyAnnotateTags y /PyAnnotateCategories, que los demás programas dejan en paz.

Al guardar, cada anotación se compara con lo que tiene el archivo. La que no cambió no se toca; la que cambió se cambia donde está, y conserva su identificador, las claves de otros programas y las respuestas que apuntan a ella; luego se vuelve a leer, y solo si no es lo que debe se quita y se escribe de nuevo. Los cambios se añaden al final del archivo (un guardado incremental), salvo en un documento con contraseña.

## Implementación

Está escrito en Python 3.14 o superior, con PyMuPDF y PySide6 (Qt 6). Son 36 archivos, unas 9900 líneas. Cada texto de la ventana se busca por su inglés en `locale/es.xml` (464 textos), y cada valor de la configuración, un archivo TOML, se comprueba al leerlo.

### Las páginas

Cada página es un objeto de la escena de Qt, y sus anotaciones son hijas suyas, de modo que las páginas se muestran una debajo de otra y las anotaciones cambian sin volver a dibujar las páginas. Solo se dibujan las páginas a la vista, en procesos propios, porque PyMuPDF retiene a Python mientras dibuja; las páginas se dibujan sin las anotaciones que se pueden editar, para que una anotación movida no se vea dos veces. El texto de los cuadros de texto, las llamadas y las notas se escribe sobre la página.

### Lo que MuPDF hace a su manera

Las pruebas con cada clase de anotación, en una página normal y en una girada, mostraron varias cosas que hubo que tener en cuenta: MuPDF hace todos los iconos de nota de 16 puntos y, en una página girada, los pone al lado del punto dado; un cuadro de texto guarda su relleno donde las demás guardan el color de su línea; PyMuPDF da a todo cuadro de texto una línea de llamada de longitud cero, y al borrar una anotación borra también sus respuestas. El recuadro de una llamada se guarda como diferencias respecto del rectángulo de la anotación, en un orden que no todos los programas siguen, así que se elige la lectura que pone el final de la línea sobre el borde del recuadro.

### Lista, intercambio y PDF/A

La lista es un modelo que arma cada fila solo cuando se muestra, y miles de anotaciones se listan enseguida. El XFDF lo escribe y lo lee el propio programa, con los puntos pasados al espacio del PDF. El resumen de los comentarios se compone como HTML, con fuentes que tienen las rayas y las comillas. Ghostscript, que usa pdf2iso, deja fuera las marcas de insertar texto, los polígonos y las nubes; py-annotate lo comprueba y ofrece hacer solo esas parte de las páginas.

## Validación

Hay 65 pruebas automáticas (`uv run pytest`). Las de las anotaciones escriben una de cada clase en una página normal y en una girada y las vuelven a leer; comprueban que una anotación cambiada conserva su número y las claves de otros programas, que guardar en el documento solo añade a su final, y que se conservan las respuestas, los estados, las etiquetas y las categorías; y pasan todo por JSON y por XFDF y de vuelta.

La ventana se prueba manejándola como lo haría un usuario, con eventos del ratón sobre las páginas: cada herramienta, mover, redimensionar y cambiar la forma, la goma de borrar, el panel y sus filtros, escribir en la página, deshacer después de guardar y las copias como PDF/A, con un pdf2iso hecho para la prueba que deja fuera los polígonos, como Ghostscript. Una prueba comprueba que cada texto de la ventana tenga su traducción al español, y ninguna otra.

Las pruebas se corren también sin nada del autor en el PATH, como las corre Copr; así se encontraron dos errores que en su equipo no se veían. El RPM vuelve a correrlas sobre el paquete instalado, con el Python, el PyMuPDF y el PySide6 de Fedora, y la AppImage escribe y lee una anotación con su propio Python antes de terminar de armarse. Las ventanas se revisaron además a ojo, con capturas de pantalla en los dos idiomas. Los instaladores de Windows y macOS no se han probado en esos sistemas.

## Plataforma

Funciona en Linux, Windows y macOS. La AppImage lleva su propio Python, Qt y PyMuPDF, y corre en cualquier Linux con glibc 2.34 o posterior; el RPM es para Fedora 45 y posteriores, y Copr lo construye para cada versión. En Windows y macOS (y en Linux, si se prefiere) se instala desde el código con los instaladores de `install/`, que solo necesitan Python 3.14 o posterior. Desde el código fuente, a mano, bastan Python 3.14 y uv. Para PDF/A y PDF/X hace falta pdf2iso, con Ghostscript.

Es una aplicación de escritorio y no necesita internet. Nada sale del equipo: los documentos, la configuración y las copias de recuperación se quedan en él.

## Ambiente

Fue desarrollado en Fedora Linux 45 con KDE Plasma, con Python 3.14 y uv, y con git, con repositorios en GitHub (https://github.com/nivaca/py-annotate) y en Codeberg (https://codeberg.org/nivaca/py-annotate). Las versiones se publican en los dos sitios y en Copr (https://copr.fedorainfracloud.org/coprs/nivaca/py-annotate/); un solo script corre las pruebas, hace la rueda, el paquete fuente, el ZIP, la AppImage y el RPM firmado, pone la etiqueta, publica en los dos sitios y manda el RPM fuente a Copr.

Para usarlo en Linux basta descargar la AppImage, hacerla ejecutable y abrirla; en Fedora, `sudo dnf copr enable nivaca/py-annotate` y `sudo dnf install py-annotate` lo instalan con su entrada en el menú y su manual (`man py-annotate`). En Windows y macOS, el instalador de `install/` lo deja en el menú Inicio o en `~/Applications`. La configuración queda en la carpeta de configuración del usuario (`~/.config/py-annotate/config.toml` en Linux, con las copias de recuperación en `recovery/`); en macOS, en `~/Library/Application Support/py-annotate/`, y en Windows, en `%APPDATA%\py-annotate\`.
