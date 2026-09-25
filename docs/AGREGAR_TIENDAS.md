# Miau: procedencia del catálogo y ampliación a otras tiendas

> Documento histórico de la etapa inicial. La integración multitienda ya está implementada; consultar `INTEGRACION_APIS.md` para el funcionamiento y las instrucciones actuales. Las propuestas de CSV/JSON de este documento siguen sin estar implementadas.

## De dónde salieron los 35.644 productos

La primera carga completa del 18 de septiembre de 2026 utilizó la API JSON de Frecuento:

```text
https://app.frecuento.com/products/?limit=500&page=1
```

La dirección se identificó en el JavaScript público que usa la propia web de Frecuento. El endpoint respondió sin autenticación. Para investigar otra tienda, las herramientas del navegador permiten observar sus solicitudes en Inspeccionar → Network/Red → Fetch/XHR, al cargar el catálogo o cambiar de página. Debe comprobarse la respuesta y sus parámetros; no todas las tiendas proporcionan una API pública de catálogo completo.

La respuesta de la primera página declaró `count=35644`, `limit=500`, `pages=72` y una lista `results`. Python solicitó las páginas 1 a 72: 71 páginas de 500 y una de 144. Se comprobaron 35.644 identificadores distintos antes de publicar la carga en MongoDB. Es una cifra de aquella captura, no una cantidad fija ni una garantía del inventario interno de la tienda.

El mapeo principal fue:

| API de Frecuento | Documento de Miau |
|---|---|
| `id` | `id_externo` |
| `name` | `nombre` |
| `code` | `codigo` |
| `brand` | `marca` |
| `amount_total` | `precio` |
| `categories[].name` | `categorias` |
| `photos` | `imagenes` |
| `has_stock` | `disponible` |
| `description` | `descripcion`, texto sin etiquetas |

Se conserva además la respuesta del producto en `original`. La moneda USD es una configuración de esta fuente; no se deduce automáticamente para cualquier tienda. Los productos padre con variantes y precio cero se muestran como precio según variante.

Archivos que realizan el flujo:

1. `app/datos/frecuento.py`: solicitudes HTTP, página, límite y reintentos.
2. `app/negocio/normalizacion.py`: transformación y validación de campos.
3. `app/negocio/sincronizacion.py`: recorrido completo, control de duplicados y publicación.
4. `app/datos/repositorio.py`: escritura y consulta en MongoDB.
5. `ejecutar.py`: tarea diaria e inicio de los servicios.

Para obtener productos nuevos que Frecuento haya añadido a su catálogo, ejecutar `SINCRONIZAR_AHORA.bat` o esperar la actualización programada. El buscador lee la versión almacenada; no solicita esos productos a la API durante una búsqueda.

## Estado actual: una sola fuente

La página inicial muestra el directorio de 17 tiendas con APIs comprobadas, definido en `app/negocio/tiendas.py`. Cada tienda tiene una ruta `/tiendas/<id>`. Frecuento dispone del catálogo sincronizado; las restantes muestran su estado pendiente. El directorio no realiza importaciones ni habilita conectores automáticamente.

`/productos` conserva la vista conjunta con búsqueda, tienda, precio mínimo/máximo, disponibilidad y orden. Los filtros se aplican en MongoDB y se conservan al paginar. Todavía no se incluye un filtro de categorías. Esta navegación no cambia el alcance del proceso de sincronización, que sigue siendo de una sola fuente.

La aplicación todavía no dispone de un formulario de alta de tiendas, un lector de configuración multitienda ni un importador genérico de CSV/JSON. `RESTAURAR_CATALOGO.bat` restaura exclusivamente el formato de respaldo de este proyecto en una base sin catálogo publicado. No sirve para importar cualquier archivo de productos ni para sumar otra tienda.

Los ejemplos siguientes son propuestas de formato para la siguiente etapa. Guardarlos en un archivo no los activa en la versión actual.

## Opción A: incorporar una API

Para incorporar una tienda manualmente en el código:

1. Identificar el endpoint de catálogo, autenticación requerida, paginación y moneda. Confirmar que da acceso a todo el listado, no solo sugerencias o resultados destacados.
2. Crear un conector en `app/datos/` que obtenga las páginas con sus límites y reintentos. Si necesita una clave, configurarla en el entorno, sin incluirla en archivos compartidos.
3. Definir el mapeo de sus campos al modelo común. Por ejemplo, una tienda puede usar `title` y `sale_price` donde Frecuento usa `name` y `amount_total`.
4. Integrar el conector en un registro de fuentes y en el programador.
5. Adaptar el repositorio a generaciones y bloqueos por tienda antes de publicar su catálogo.

Ejemplo de una futura configuración `tiendas.json`:

```json
[
  {
    "id": "tienda_ejemplo",
    "nombre": "Tienda de ejemplo",
    "conector": "api_ejemplo",
    "endpoint": "https://tienda.example/api/products",
    "moneda": "USD",
    "hora": "04:00",
    "activa": true
  }
]
```

El campo `conector` debe referirse a código implementado. Un archivo de configuración indica qué fuente utilizar; no interpreta por sí mismo cualquier contrato de API.

## Opción B: incorporar productos desde un archivo

Un archivo CSV o JSON puede servir como fuente de catálogo cuando no hay una API disponible. El importador tendría que validar sus filas, transformarlas al modelo común y publicar una generación de esa tienda. Esta función está pendiente de implementación.

Ejemplo de CSV con cabecera, UTF-8 y punto decimal:

```csv
tienda_id,id_externo,nombre,marca,precio,moneda,disponible,url_origen
tienda_ejemplo,ABC-01,Teclado USB,Marca Ejemplo,19.90,USD,true,https://tienda.example/productos/ABC-01
```

Ejemplo equivalente en JSON:

```json
{
  "tienda_id": "tienda_ejemplo",
  "productos": [
    {
      "id_externo": "ABC-01",
      "nombre": "Teclado USB",
      "marca": "Marca Ejemplo",
      "precio": "19.90",
      "moneda": "USD",
      "disponible": true,
      "categorias": ["Accesorios"],
      "imagenes": [],
      "url_origen": "https://tienda.example/productos/ABC-01"
    }
  ]
}
```

Se debe acordar si el archivo representa el catálogo completo de esa tienda o solamente cambios. Un catálogo completo permite retirar los productos ausentes; un archivo parcial solo debe agregar o actualizar los registros incluidos. Los datos de ejemplo no son productos reales.

Insertar documentos directamente con Compass no garantiza que sean visibles: el buscador filtra por la generación publicada y necesita campos normalizados. Conviene usar un importador que respete ese proceso.

## Cambios necesarios para que varias tiendas coexistan

Actualmente `control` contiene un único documento `catalogo`. Publicar otro conector con este mismo mecanismo sustituiría la fuente visible. También el identificador y el detalle asumen una sola tienda.

La ampliación debe incluir:

- Configuración o colección `tiendas` con identificador estable y tipo de fuente.
- Generación activa y bloqueo independientes por tienda.
- Clave única `(tienda_id, generacion, id_externo)` para evitar colisiones.
- Búsqueda que reúna las generaciones publicadas de las tiendas activas.
- Rutas de detalle que incluyan la tienda además del identificador del producto.
- Sincronización programada por fuente; un fallo en una tienda debe conservar su catálogo anterior sin afectar las demás.

Comparar el mismo producto entre tiendas requerirá después identificar equivalencias mediante EAN/GTIN, modelo y variante. Ordenar todos los resultados por precio no demuestra que sean productos equivalentes.

La extracción por API y la importación por archivo terminarían usando la misma normalización y el mismo repositorio. La diferencia está en el origen de los datos; las búsquedas seguirían consultando únicamente MongoDB.
