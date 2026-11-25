# Registro de cambios

Los cambios notables de py-annotate. Las versiones publicadas, con el ZIP
del código fuente, la AppImage y el RPM firmado, están en
[Codeberg](https://codeberg.org/nivaca/py-annotate/releases) y
[GitHub](https://github.com/nivaca/py-annotate/releases); el RPM se
construye también en Copr. Algunas versiones (la 0.2.0, de la 0.3.1 a la
0.3.3, y otras) se hicieron pero no se publicaron aparte: cada una se
cuenta en la sección de la siguiente versión publicada.

## Sin publicar

- `tools/zenodo.py`: la descripción del depósito es ahora el README entero
  de la etiqueta, en HTML. El borrador recibe además el colaborador (el
  director del proyecto), los idiomas, el copyright, el repositorio en
  GitHub, el lenguaje de programación y el estado del desarrollo; estos
  últimos, por la API de registros de Zenodo, porque la de depósitos no los
  admite. El token puede guardarse en el llavero del escritorio
  (`secret-tool store --label="Zenodo token" service zenodo`) en vez de en
  `$ZENODO_TOKEN`; `tools/zenodo.py check-token` dice si hay uno.

- `tools/zenodo.py` prepara el depósito de una versión en Zenodo. `collect`
  deja en `dist/zenodo/` el árbol de la etiqueta como
  `py-annotate-VERSIÓN-source.tar.gz`, con su firma, un `SHA256SUMS` del
  depósito, firmado, y la clave pública, y comprueba cada firma con solo esa
  clave (`--packages` añade los archivos de la versión). `upload` lo sube a
  Zenodo como borrador, versión nueva del depósito si ya lo hay, y nunca lo
  publica. `tools/release.py` reúne ahora el depósito después de la etiqueta
  y lo sube como borrador, salvo con `--no-zenodo`. Los metadatos están en
  `.zenodo.json`.
- `tools/zenodo.py`: la descripción del depósito deja fuera la línea que
  lleva a los README en otras lenguas y la sección Screenshots, cuyas
  imágenes Zenodo no muestra.

## 1.1.2 — 2026-11-22

### Nuevo

- **Cada versión firmada**: además del RPM, cada archivo publicado (la
  rueda, el paquete fuente, el ZIP, la AppImage) va con su
  firma (`.asc`), con `SHA256SUMS` y su firma, y con la clave pública; la
  etiqueta de la versión también se firma. Cada firma se comprueba con la
  clave publicada antes de publicar nada. El README dice cómo comprobar
  una descarga.

## 1.1.1 — 2026-11-21

### Nuevo

- **El software que usa, y sus licencias.** `docs/THIRD_PARTY_es.md` (y
  `docs/THIRD_PARTY.md`, en inglés) lista el software libre que usa
  py-annotate: las bibliotecas que necesita y las que trae PyMuPDF, los
  programas que corre si están instalados (Tesseract, pdf2iso y
  Ghostscript) y las herramientas con que se construye y se prueba, cada
  uno con su licencia. Los README la enlazan.
- **Este registro de cambios**, en inglés y en español.

## 1.1.0 — 2026-11-19

Esta versión reúne de la 1.0.3 a la 1.0.7.

### Nuevo

- **Trazos como curvas, y puntos.** Un toque con la herramienta a mano
  alzada hace un punto (el de una i, un punto final), que antes se
  descartaba. Cada trazo se dibuja como una curva por sus puntos (una
  spline de Catmull-Rom, como segmentos de Bézier cúbicos), en la ventana
  y en el PDF. Tomado del código del lápiz de PdfCraft (MIT o Apache 2.0).
- **Replace text** (*Reemplazar texto*; Shift+I): arrastrado sobre un
  texto, lo tacha (`/IT /StrikeOutTextEdit`) y escribe el texto nuevo en
  una marca de insertar texto a su final (`/IT /Replace`), las dos en un
  grupo, de modo que otros visores muestran un reemplazo.
- **Comparar dos versiones de un texto.** File > Compare with another
  version (*Archivo > Comparar con otra versión*) marca lo que difiere de
  otra versión del texto: las palabras cambiadas en naranja, con las de
  la otra en su comentario; las que solo están aquí, en rojo; y una marca
  de insertar texto donde faltan palabras de la otra. Las palabras se
  alinean con un patience diff (`compare.py`), que tarda tres segundos en
  300 páginas, donde difflib tardaba casi dos minutos y daba cientos de
  diferencias falsas.
- Typewriter (*Máquina de escribir*; Y), un cuadro de texto sin borde ni
  relleno (`/IT /FreeTextTypeWriter`), y Check mark (*Marca de
  verificación*; K), una marca de verificación, una cruz, un punto o un
  guion, para llenar formularios que no tienen campos.
- Attach a file (*Adjuntar un archivo*; Shift+A): las anotaciones de
  archivo adjunto ya se editan, no solo se listan; el archivo puede
  abrirse o guardarse de nuevo desde el menú del clic derecho. JSON
  conserva el archivo; XFDF lo deja fuera.
- Signature (*Firma*; Shift+K): se dibuja una vez a mano, se guarda solo
  en este equipo y se pone en la página con cada clic.

### Cambios

- **Un Buscar y resaltar mejor.** Encuentra una palabra cortada con guion
  al final de un renglón; puede no distinguir acentos ni ligaduras
  (accion: acción; caesar: cæsar) y tomar u y v, i y j como una sola
  letra, como en los textos latinos y medievales; toma `*` y `?` como
  comodines; tiene Previous y Next (*Anterior*, *Siguiente*), y recuerda
  las búsquedas y sus opciones. La búsqueda de la lista del panel tampoco
  distingue acentos.
- La intención de los tachados y de las marcas de insertar texto se lee y
  se conserva.
- Las páginas del manual y el metainfo describen las nuevas herramientas y
  versiones.

### Correcciones

- El resaltado a mano alzada nunca se dibujaba en la ventana, solo en el
  archivo.
- En Windows se perdía el historial de búsquedas: ahora se guarda como
  JSON, en los mismos ajustes que el estado de la ventana.

## 1.0.2 — 2026-11-19

- **Lo escrito a mano con un lápiz es un solo dibujo.** Las herramientas a
  mano alzada dibujan aun sobre otras anotaciones (moverlas le corresponde
  a Select, *Seleccionar*). Los trazos hechos menos de un segundo y medio
  después del anterior, cerca de él (40 puntos), con la misma herramienta
  y el mismo aspecto, se añaden a ese dibujo, así que una palabra o un
  renglón son una sola anotación; deshacer sigue quitando un trazo cada
  vez.
- La presión da a cada dibujo su grosor una sola vez, según su primer
  trazo; cortar los trazos según la presión sigue siendo una opción de la
  configuración.

## 1.0.1 — 2026-11-19

- View > The thumbnails of the pages (*Ver > Las miniaturas de las
  páginas*; F3) las muestra u oculta, y la ventana lo recuerda. Mientras
  están ocultas, no se dibujan.

## 1.0.0 — 2026-11-19

- La primera versión estable. Las páginas del manual cuentan lo que el
  programa hace ahora (crítica textual, grupos, capas, texto con formato,
  OCR, el lápiz de una tableta), y el metainfo lista las versiones
  publicadas.
- (0.4.4) Mientras se mantiene apretado un botón lateral del lápiz de una
  tableta, la página sigue al lápiz, como con la herramienta mano, sea
  cual sea la herramienta elegida; la configuración puede volver a hacer
  de él un clic derecho.

## 0.4.3 — 2026-11-19

Esta versión reúne la 0.4.1 y la 0.4.2.

- **Capas.** El menú Layers (*Capas*) pone las anotaciones en capas que
  se pueden mostrar u ocultar; las anotaciones nuevas van a la capa
  elegida allí. Las capas son el contenido opcional del PDF (el `/OC` de
  una anotación), así que otros visores también las muestran y ocultan.
- **Copias buscables de documentos escaneados.** File > Save a copy >
  Searchable (OCR) (*Archivo > Guardar una copia > Con texto buscable
  (OCR)*) lee con Tesseract, por medio de PyMuPDF, el texto de las páginas
  escaneadas y lo escribe bajo sus imágenes, invisible, cada palabra
  donde está en la imagen. Los idiomas se fijan en la configuración
  (`eng`, o `lat+eng`). Sin Tesseract la opción aparece en gris; el RPM
  lo recomienda.
- **Mejor manejo del lápiz de una tableta.** Los trazos siguen los
  eventos del propio lápiz, que conservan las fracciones de píxel, y se
  suavizan un poco. El extremo de borrador del lápiz borra mientras toca,
  sea cual sea la herramienta elegida. La configuración dice cómo cuenta
  la presión y cuánto hay que apretar el lápiz.

## 0.4.0 — 2026-11-19

Esta versión reúne de la 0.3.5 a la 0.3.9.

- **La presión de un lápiz cuenta a lo largo de un trazo.** Cuando la
  presión cambia a lo largo de un trazo, el trazo se corta allí en
  dibujos de grosores distintos, unidos extremo con extremo en un grupo.
- **Texto con formato en cuadros de texto y llamadas**: negrita, cursiva,
  subrayado, colores y letras (Ctrl+B, Ctrl+I, Ctrl+U y el menú del clic
  derecho), escrito como texto enriquecido del PDF (`/RC`, `/DS`), con el
  texto plano guardado en `/Contents`. El borde puede tener un color
  propio.
- **Grupos** (Ctrl+G, Ctrl+Shift+G): las anotaciones agrupadas se
  seleccionan, se mueven, se copian y se borran juntas. Se escriben como
  grupos del PDF (`/IRT` con `/RT /Group`), y los grupos hechos por otros
  programas se leen y se conservan.
- **Entradas de crítica textual.** Cualquier anotación puede llevar una:
  los dieciséis tipos de la especificación (variante, enmienda,
  conjetura, laguna...), las lecturas, el testimonio, la fuente, la
  justificación y el grado de seguridad. File > Export (*Archivo >
  Exportar*) escribe el aparato crítico en Markdown.
- Los enlaces, los archivos adjuntos y otras anotaciones que py-annotate
  no edita se listan, bloqueados, con aquello a lo que apuntan o que
  contienen.
- Un flujo de trabajo en GitHub ejecuta cada instalador en Linux, macOS y
  Windows, corre las pruebas contra lo instalado y lo desinstala. Encontró
  tres problemas, ya corregidos: un `chmod --` que macOS rechaza, un
  documento que no podía reemplazarse en Windows porque PyMuPDF aún lo
  tenía abierto, y pdf2iso sin extensión, que no se encontraba en Windows.

## 0.3.4 — 2026-11-19

Esta versión reúne de la 0.3.1 a la 0.3.3, todas sobre documentos con
miles de anotaciones.

- Buscar en la lista es rápido: las palabras de cada página se leen una
  sola vez, y en 300 páginas con 750 resaltados la primera búsqueda tarda
  0,8 segundos en lugar de 14. La lista se busca cuando se
  deja de escribir.
- Con 3000 anotaciones, un cambio tarda 0,016 segundos en lugar de 0,17:
  las columnas se ajustan a una muestra de las filas, y solo se vuelven a
  dibujar las anotaciones que cambiaron.
- Abrir y guardar es más rápido: el documento ya no se copia entero a un
  archivo temporal, y al guardar ya no se lee cada anotación tres veces
  (0,4 segundos en lugar de 1,4 con 3000 anotaciones).
- Las copias, la impresión, la exportación y la importación pasaron de
  `window.py` a `gui/files.py`; nada de lo que hacen ha cambiado.
- `docs/DESCRIPTION.md` y `docs/DESCRIPCIÓN_es.md` con la estructura de
  los otros proyectos.

## 0.3.0 — 2026-11-19

- **Las anotaciones se cambian donde están.** Al guardar se conserva lo
  que py-annotate no sabe de una anotación (su identificador, claves de
  otros programas, respuestas), y se guarda de forma incremental, de modo
  que las firmas siguen siendo válidas; lo hecho puede deshacerse después
  de guardar.
- Respuestas y estados de revisión, etiquetas y categorías, con filtros en
  el panel.
- Exportación e importación en XFDF, y un resumen de los comentarios en
  PDF.
- Buscar y resaltar; impresión; un resaltado a mano alzada y la presión
  del lápiz de una tableta; una vista continua de las páginas; miniaturas
  del tamaño elegido.
- Las llamadas de otros programas se leen dé como se dé su recuadro; los
  sellos en páginas giradas quedan derechos.
- Instaladores para Windows y macOS, capturas de pantalla, páginas del
  manual y el metainfo.

## 0.2.1 — 2026-11-19

- (0.2.0) **PDF/A y PDF/X.** File > Save a copy (*Archivo > Guardar una
  copia*) hace PDF/A-1b, PDF/A-2b, PDF/A-3b y PDF/X-4 con pdf2iso.
  Ghostscript deja fuera algunos tipos de anotaciones (marcas de insertar
  texto, polígonos, nubes), así que la copia se revisa, y esas anotaciones
  pueden hacerse parte de las páginas.
- (0.2.0) La lista de las anotaciones es un panel a la derecha que puede
  ocultarse (F4), moverse o sacarse de la ventana.
- Las opciones PDF/A y PDF/X pueden elegirse en cuanto se indica pdf2iso
  en la configuración; antes, solo se activaban con el siguiente cambio en
  la ventana.

## 0.1.0 — 2026-11-19

- Primera versión: un programa para añadir anotaciones a documentos PDF,
  escritas como anotaciones PDF corrientes: resaltados, subrayados,
  tachados, subrayados ondulados, marcas de insertar texto, notas, cuadros
  de texto, llamadas, zonas resaltadas, formas, líneas, flechas, dibujos a
  mano alzada y sellos. Las anotaciones que el documento ya tiene se leen
  y pueden editarse.
- Una ventana en inglés y en español, con miniaturas, una lista de las
  anotaciones en la que se puede buscar, un borrador, copiar y pegar,
  alineación, bloqueo, exportación (Markdown, CSV, JSON), importación,
  copias aplanadas, copias de recuperación, una paleta de colores con
  significados y atajos de teclado que se pueden cambiar.
- Versiones publicadas como ZIP del código fuente, AppImage y RPM firmado,
  construido también en Copr (`tools/release.py`).
