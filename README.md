# Miau — catálogos de tiendas de Ecuador

## Clonar desde GitHub

El repositorio incluye el código, el Excel de tiendas y una copia lógica del catálogo en `respaldo/catalogo.jsonl.gz` mediante Git LFS. Para descargar también los datos, instalar Git LFS y usar `git clone` (o ejecutar `git lfs pull` tras clonar). La descarga ZIP de GitHub puede contener solo el puntero LFS, no la base completa.

En Windows, instalar Python 3.11 o superior y MongoDB Community Server. Ejecutar `ABRIR_MIAU.bat` en la carpeta clonada: crea `.venv` y `.env` locales, inicia MongoDB, restaura la copia en la base `frecuento_catalogo` y abre la web. La primera restauración puede tardar varios minutos. `data/` y `.env` son locales y no se publican en GitHub.

Para publicar una copia más reciente del catálogo: ejecutar `.venv\Scripts\python.exe transferir_catalogo.py exportar` con MongoDB en funcionamiento y después confirmar y subir el cambio de `respaldo/catalogo.jsonl.gz` con Git LFS.

Carpeta de trabajo: `Documentos\Idealo - PL_Miau`. Ejecutar `ABRIR_MIAU.bat` para abrir la aplicación. El respaldo exportado el 25/09/2026 contiene las generaciones publicadas de 17 tiendas y 118.112 productos. Las generaciones anteriores y los registros de sincronización permanecen únicamente en la base local original.

Prototipo en Python, Flask y MongoDB. Una tarea independiente actualiza las APIs de 17 tiendas mediante conectores reutilizables. La web busca exclusivamente en MongoDB. Interfaz en color vino y Times New Roman.

## Uso en este equipo

1. Ejecutar `ABRIR_MIAU.bat` (restaura los catálogos incluidos si aún no existen).
2. Abrir http://127.0.0.1:5001; la página inicial muestra el buscador y todos los productos.
3. Buscar y filtrar por precio y disponibilidad, con orden por precio o nombre. Cada ficha indica su tienda y enlaza al producto original. No se incluye filtro de categorías. El diagnóstico se consulta con `python ejecutar.py estado`.
4. Para una actualización manual, ejecutar `SINCRONIZAR_AHORA.bat`.
5. Para cerrar la web y el programador, ejecutar `DETENER_MIAU.bat`.

El lanzador inicia procesos en segundo plano. No es necesario mantener PowerShell abierto. MongoDB permanece disponible para Compass al detener la web.

**MongoDB Compass:** `mongodb://127.0.0.1:27018` → base `frecuento_catalogo`.

Se usa el puerto 27018 y una base independiente para no mezclar esta etapa con el proyecto anterior. Los archivos físicos de esta instancia están en `data/mongodb`.

## Horario

Por defecto: todos los días a las **03:00, America/Guayaquil**. Cambiar `SYNC_HOUR`, `SYNC_MINUTE` y `SYNC_TIMEZONE` en `.env`; detener y volver a abrir para aplicar el cambio.

El equipo y el programador deben estar encendidos. Al abrir la aplicación se inicia la primera carga si no hay catálogo; también se recupera una actualización diaria pendiente. Abrir la página o buscar no ejecuta sincronizaciones. No se instala una tarea de Windows ni un servicio de arranque automático del sistema.

Si la API falla, la búsqueda continúa usando la última carga completa. Una descarga puede tardar varios minutos. El diagnóstico por consola muestra páginas y productos recibidos.

Los precios cero publicados por una tienda se muestran como «Precio no informado» y se ordenan después de los precios válidos. El documento `original` conserva el valor recibido para su revisión.

## En otra computadora

El ZIP contiene una carpeta `Miau`, código editable, `Tiendas_Ecuador_APIs.xlsx` y una copia lógica de todas las tiendas publicadas en `respaldo/catalogo.jsonl.gz`. Después de instalar Python y MongoDB, ejecutar `ABRIR_MIAU.bat`: prepara las dependencias, restaura las tiendas que aún no tengan catálogo y abre la página. Los catálogos ya existentes se conservan. La base local se crea en el equipo receptor.

Instalar Python 3.11 o superior y MongoDB Community Server. El lanzador crea el entorno Python cuando es necesario e instala las dependencias. MongoDB puede estar instalado en su ruta habitual, disponible como `mongod` en PATH o copiado en `data/runtime/mongod.exe`.

Copiar el código, ejecutar `ABRIR_FRECUENTO.bat` y esperar la primera carga. No copiar `.env` con credenciales ni archivos de una base MongoDB en ejecución. Si se usa Atlas, configurar `MONGODB_URI` y `MONGODB_DB` en `.env` con los permisos correspondientes.

## Arquitectura

- `app/presentacion`: rutas Flask, HTML y CSS. Recibe búsquedas y muestra resultados.
- `app/negocio`: reglas de búsqueda, normalización, validación y sincronización completa.
- `app/datos`: conectores HTTP de las tiendas, conexión PyMongo y repositorio.
- `app/__init__.py`: conecta dependencias para la web.
- `ejecutar.py`: entradas de web, sincronización, programador y diagnóstico.

Documentación técnica: [arquitectura](docs/ARQUITECTURA.md), [contrato y procedencia de la API](docs/CONTRATO_API.md), [validación](docs/VALIDACION.md).

La integración actual y cómo agregar fuentes compatibles se explican en [INTEGRACION_APIS.md](docs/INTEGRACION_APIS.md). `AGREGAR_TIENDAS.md` conserva la explicación histórica de Frecuento y las propuestas iniciales de importación de archivos. No hay importador arbitrario de CSV/JSON.

## API de origen

`GET https://app.frecuento.com/products/?limit=500&page=1`

Se consume la API JSON utilizada por el frontend de Frecuento. No se extraen productos del HTML ni se utiliza Idealo. El endpoint se identificó en el JavaScript público de la tienda y se verificó con peticiones sin autenticación.

La carga obtiene todas las páginas que declara este endpoint. Eso significa **catálogo público expuesto por la API en ese momento**, no inventario interno, productos ocultos ni garantías de detalle completo de todas las variantes. La primera ejecución validada recibió 35.644 IDs únicos en 72 páginas.

## MongoDB

| Colección | Contenido |
|---|---|
| `productos` | Datos normalizados, documento JSON original, ID de origen, generación y fecha |
| `control` | Generación publicada, total, fecha y bloqueo de sincronización |
| `sincronizaciones` | Inicio, fin, motivo, estado, páginas, productos y errores |

Cada tienda publica una generación independiente en su documento de control. Después de validar páginas e identidades, la búsqueda consulta las generaciones activas. Un producto retirado del nuevo catálogo deja de aparecer, aunque exista en una generación anterior. Un fallo de una tienda no reemplaza su catálogo anterior ni afecta a otras fuentes.

La colección `productos` puede contener varias generaciones. Para inspeccionar exactamente lo que utiliza la web, copiar `control.generacion` y filtrar `productos` con `{ "generacion": "VALOR" }`. No contar toda la colección como si fuera el catálogo vigente.

Las generaciones anteriores y fallidas se conservan para revisión. No hay limpieza automática en esta etapa; las ejecuciones periódicas aumentan el uso de disco. Un proceso interrumpido libera su exclusión tras diez minutos sin renovación; su registro puede permanecer `en_curso` hasta que se investigue. El estado del último trabajo no prueba por sí solo que el programador siga ejecutándose.

## Desarrollo

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
# Configurar MongoDB en .env antes de los siguientes comandos.
.\.venv\Scripts\python ejecutar.py sincronizar
.\.venv\Scripts\python ejecutar.py web
# En otra terminal:
.\.venv\Scripts\python ejecutar.py programador
```

El servicio web se ejecuta con Waitress en la interfaz local `127.0.0.1`. El programador usa APScheduler en otro proceso; no se duplica por abrir varias pestañas.

Pruebas de integración (crean y eliminan exclusivamente bases temporales `test_frecuento_*`):

```powershell
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27018'
python -m pytest -q tests
```

La búsqueda utiliza términos normalizados sin acentos y un índice de generación. Los filtros de texto emplean expresiones regulares escapadas con inicio de palabra; no son un motor de relevancia ni una identificación semántica de productos. Para catálogos mucho mayores convendría evaluar un índice de búsqueda especializado.

Comparación entre tiendas, equivalencias de productos, enlaces de compra, exportaciones y dashboards no forman parte de esta primera etapa. Se conserva la URL de origen como dato para una implementación posterior, pero no se añade redirección de compra a la interfaz.
