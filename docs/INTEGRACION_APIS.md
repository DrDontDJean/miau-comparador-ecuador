# Miau: integración de tiendas

## Ejecución

`ABRIR_MIAU.bat` inicia MongoDB, la web y el programador. La página está en http://127.0.0.1:5001.

`SINCRONIZAR_AHORA.bat` actualiza todas las tiendas. Para una tienda concreta, desde la carpeta del proyecto y con el entorno Python activado:

```powershell
python ejecutar.py sincronizar --tienda computron
```

Para repetir únicamente las fuentes pendientes o fallidas: `python ejecutar.py sincronizar --pendientes`.

La actualización diaria utiliza el horario de `.env` (03:00, America/Guayaquil, por defecto). Al abrir el programa recupera los catálogos ausentes o anteriores al último horario programado. El equipo y el programador deben permanecer encendidos durante las cargas. Las búsquedas no generan solicitudes externas.

## Conectores

| Conector | Tiendas configuradas | Recorrido |
|---|---|---|
| Frecuento REST | Frecuento | page y limit, total declarado |
| VTEX | Novicompu, Créditos Económicos, Comandato, Marcimex, Pycca, Almacenes Japón, Kywi | Rangos de 50 productos y particiones por categoría cuando se supera el límite de 2.500 resultados |
| WooCommerce Store API | Computron | page y per_page, total en cabeceras HTTP |
| Shopify JSON | Colineal, NewStore, EkuStore, Smart Home EC, Randall Tech | products.json hasta página vacía; moneda comprobada con cart.js |
| Magento GraphQL | Steren Ecuador, Pintulac, La Ganga | products con currentPage, pageSize y total_count |

Las categorías se usan internamente para descargar ciertos catálogos. No se ha añadido un filtro de categorías en la interfaz.

Los enlaces del inventario de APIs muestran únicamente la primera página como ejemplo del contrato. El proceso de ingesta cambia `page`, `currentPage` o `_from`/`_to` para recorrer el resto. En VTEX, `fq=C:/...` divide consultas que superan el límite público; se reúnen todas las categorías, se eliminan IDs repetidos y solo se publica la carga cuando coincide con el total global declarado. Estos parámetros no limitan la búsqueda posterior en MongoDB a una sola categoría.

## Datos y publicación

Cada ejecución tiene un identificador de generación independiente. Los productos se escriben con `fuente`, `id_externo` y `generacion`. MongoDB mantiene un control por tienda: `catalogo` para Frecuento (compatibilidad) y `catalogo:<tienda>` para las nuevas fuentes.

El buscador solo lee las generaciones publicadas. Una ejecución con error conserva los productos anteriores de esa tienda. Los catálogos incompletos no se publican. Los bloqueos por tienda impiden dos actualizaciones simultáneas de la misma fuente. Se consultan como máximo tres tiendas simultáneamente, con pausas y reintentos limitados por API.

Se conserva `original` para inspeccionar la respuesta recibida. La web utiliza nombre, código, precio, moneda, imágenes, descripción y disponibilidad normalizados. Las fichas usan una URL que incluye la tienda para evitar colisiones entre identificadores.

En VTEX se guardan las variantes y vendedores. El precio mostrado es el mínimo entre las variantes disponibles, o entre las variantes con precio si ninguna está disponible. En Shopify también se conservan las variantes; `vendor` permanece en el original porque no siempre representa una marca. WooCommerce expresa el precio en unidades menores: se convierte según `currency_minor_unit`. Los precios de GraphQL se reciben con su moneda. No se convierten monedas automáticamente.

## Alcance y fallos

Los conectores consultan los catálogos públicos de cada escaparate, no el inventario privado de la empresa. Shopify no declara total en este listado: se comprueba el final del recorrido y que no se repitan IDs. VTEX comprueba que los productos únicos obtenidos coincidan con el total declarado. Si una categoría no se puede dividir lo suficiente o cambia el catálogo durante la carga, esa tienda conserva su versión anterior y registra el error.

VTEX limita el intervalo de búsqueda a 2.500 resultados. El conector recorre el árbol de categorías con sus rutas completas y elimina duplicados por ID. Si faltan productos, complementa el recorrido con búsquedas generales en orden ascendente y descendente. Ante un HTTP 500 divide el mismo intervalo de 50 registros en bloques de 10 y, si hace falta, de uno. Nunca omite silenciosamente un bloque que falla.

La página conjunta permite comparar resultados ordenados por precio. Todavía no existe una agrupación automática de productos equivalentes entre tiendas. Para ello deben relacionarse marca, modelo, GTIN y variante; la igualdad del nombre no basta.

## Agregar una tienda

1. Registrar su ID y nombre en `app/negocio/tiendas.py`.
2. Si comparte un contrato compatible, agregar su tipo y dominio en `FUENTES`, dentro de `app/datos/fuentes.py`.
3. Verificar moneda, paginación, campos y condiciones de precio del nuevo dominio.
4. Ejecutar `python ejecutar.py sincronizar --tienda <id>` y comprobar el resultado en MongoDB y en la web.

Para una plataforma diferente se debe implementar el recorrido en la capa de datos y su mapeo en `app/negocio/productos_api.py`. No hay importación de catálogos arbitrarios desde CSV/JSON en esta versión.

## Archivos principales

- `app/datos/fuentes.py`: solicitudes y paginación de las nuevas APIs.
- `app/negocio/productos_api.py`: transformación al documento común.
- `app/negocio/multitienda.py`: ejecución, validación y publicación por tienda.
- `app/datos/repositorio.py`: generaciones, bloqueos y consultas MongoDB.
- `app/negocio/catalogo.py`: validación de búsquedas y filtros.
- `ejecutar.py`: web, ejecución manual y programación diaria.

Los registros se encuentran en `data/logs/aplicacion.log`. El respaldo `respaldo/catalogo.jsonl.gz` usa el formato `miau-2` y contiene las generaciones publicadas de todas las tiendas al preparar el paquete. `ABRIR_MIAU.bat` restaura las fuentes que todavía no tengan catálogo en el equipo receptor. `transferir_catalogo.py exportar` permite renovar la copia.

Referencias de los contratos: https://developers.vtex.com/docs/api-reference/search-api, https://developer.woocommerce.com/docs/apis/store-api/resources-endpoints/products/, https://developer.adobe.com/commerce/webapi/graphql/schema/products/queries/products/ y https://shopify.dev/docs/api/ajax/reference/product. El listado `/products.json` de Shopify se verificó directamente en cada tienda y no se identifica como Admin API.
