Cómo guarda py-annotate las anotaciones
=======================================

*(English: [DESCRIPTION.md](DESCRIPTION.md))*

py-annotate escribe anotaciones PDF corrientes, de los tipos que tiene el
estándar PDF, de modo que cualquier visor las muestra y puede editarlas.
Esta página cuenta cómo se escribe cada una y qué se hace para conservar el
documento como estaba.

Los tipos de anotaciones
------------------------

| En py-annotate             | En el PDF                                     |
|----------------------------|-----------------------------------------------|
| Resaltado, subrayado, tachado, subrayado ondulado | Highlight, Underline, StrikeOut, Squiggly, con un cuadrilátero para cada línea de texto |
| Insertar texto             | Caret                                         |
| Nota                       | Text, con su icono                            |
| Cuadro de texto            | FreeText                                      |
| Llamada                    | FreeText con la intención FreeTextCallout y su línea (/CL) |
| Resaltado de zona          | Square, con relleno, sin borde y con el asunto «Area highlight» |
| Rectángulo, elipse         | Square, Circle                                |
| Polígono, nube             | Polygon (la nube tiene borde de nube, /BE)    |
| Línea, flecha              | Line, con sus extremos (/LE)                  |
| Polilínea                  | PolyLine                                      |
| A mano alzada              | Ink                                           |
| Resaltado a mano alzada    | Ink, ancho y translúcido, con el asunto «Freehand highlight» |
| Sello                      | Stamp: uno de los habituales por su nombre, o uno propio como imagen |

El autor es el título de la anotación (/T); el comentario, su contenido
(/Contents); y las fechas, su fecha de creación y su fecha de modificación
(/M). Una anotación bloqueada tiene la marca Locked del PDF.

Respuestas y estados de revisión
--------------------------------

Una respuesta es una nota (Text) que contesta a la anotación (/IRT). Un
estado de revisión es también una respuesta, con el estado (/State:
Accepted, Rejected, Cancelled, Completed o None) y su modelo (/StateModel
Review). Así los guardan los visores de PDF, y así los muestran. El estado
de una anotación es el de su última respuesta que da uno.

Etiquetas y categorías
----------------------

El estándar PDF no tiene etiquetas ni categorías, así que py-annotate las
guarda en dos claves propias de cada anotación, /PyAnnotateTags y
/PyAnnotateCategories, como textos con los nombres separados por comas. Los
demás programas dejan en paz las claves que no conocen. Al exportar como
XFDF quedan fuera; como JSON, se conservan.

Al guardar
----------

Al abrir un documento, py-annotate lee sus anotaciones de los tipos dichos,
con sus respuestas. Al guardarlo, compara cada una con lo que tiene el
archivo:

* la que quedó como estaba no se toca;
* la que cambió se cambia donde está: sus puntos, colores, textos, marcas y
  respuestas se escriben sobre los anteriores, y todo lo demás que tenga se
  queda (su identificador, claves de otros programas, las respuestas que
  apuntan a ella). Luego se vuelve a leer, y solo si no es lo que debe se
  quita y se escribe de nuevo;
* la que se borró se quita, con sus respuestas;
* la nueva se escribe, con sus respuestas.

Al guardar en el propio documento, los cambios se añaden a su final (un
guardado incremental): lo que había en el archivo queda igual, byte por
byte, y un documento firmado conserva sus firmas válidas para lo que
firmaron. Un archivo que no lo admite, o uno con contraseña, se escribe
entero (en un archivo aparte que al final ocupa su lugar, de modo que un
fallo nunca lo deja a medio escribir).

Deshacer después de guardar funciona porque cada anotación que sigue en el
archivo conserva su número en el historial; las que no siguen se escriben de
nuevo si se recuperan.

Cómo se muestran las páginas
----------------------------

La ventana dibuja ella misma las anotaciones sobre las páginas. Las páginas
se dibujan sin las anotaciones que se pueden editar (en una copia que se
guarda en memoria, y en un archivo temporal cuando se dibujan en otro
proceso), para que una anotación movida no se vea dos veces. Las páginas se
dibujan en procesos propios, solo las que están a la vista, de modo que la
ventana responde enseguida aun con documentos largos o escaneados.

Copias de recuperación
----------------------

Mientras haya anotaciones sin guardar, se guarda una copia de ellas cada dos
minutos (en JSON) en la carpeta `recovery` de la carpeta de configuración,
con la hora y el tamaño del archivo. Al volver a abrir el documento, la
copia se ofrece solo si el archivo no cambió desde entonces.
