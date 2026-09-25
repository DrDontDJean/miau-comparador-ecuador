# API utilizada y alcance de la captura

Fuente: sitio oficial https://www.frecuento.com/.

El frontend público referencia `https://app.frecuento.com` y rutas `/products/`. Se identificaron en el recurso de la propia tienda `/_next/static/chunks/pages/_app-a5a2cc1ab623c96f.js`, vigente durante la investigación. No se copiaron credenciales ni tokens del frontend.

Endpoint verificado sin autenticación:

```http
GET https://app.frecuento.com/products/?limit=500&page=1
Accept: application/json
```

Respuesta resumida observada:

```json
{
  "count": 35644,
  "limit": 500,
  "pages": 72,
  "results": [
    {
      "id": 906522,
      "name": "Secadora a Gas Whirlpool Carga Frontal Blanca 19KG | 7MWGD1900EW",
      "code": "40367532",
      "brand": "Whirlpool",
      "amount_total": "529.00",
      "amount_incl_tax": "529.00",
      "has_stock": true,
      "stock": 6
    }
  ]
}
```

La respuesta real incluye categorías, fotos, descripción, variantes y otros campos conservados en `original`. El ejemplo está abreviado.

- `page` cambia la página. `offset` fue ignorado por la fuente durante la verificación; usarlo repetiría los primeros productos.
- `amount_total` se toma como precio publicado. Los componentes de impuesto y descuento permanecen en `original`.
- La moneda USD se configura para esta fuente del mercado ecuatoriano; no aparece explícitamente en la respuesta observada.
- `has_stock` y `stock` se conservan según lo publicado. No se afirma que representen existencias de cada sucursal.
- Dos productos padre con `has_variants=true` publicaron `amount_total=0.00` y una lista vacía de variantes. Su precio normalizado queda vacío y la interfaz indica «Según variante». El valor original no se altera.
- Algunas descripciones de origen contienen caracteres de sustitución. El programa no inventa el texto perdido.

La primera carga completa recibió **35.644 productos con IDs únicos en 72 páginas**, sin filtros de categoría ni búsqueda. Se comprobó el tamaño de cada página, la estabilidad de `count/limit/pages`, la ausencia de IDs repetidos y el total almacenado antes de publicar.

Este endpoint es una interfaz utilizada por el sitio, no una API contratada con documentación de estabilidad aportada por el proveedor. Si cambia el contrato o se rechaza el acceso, el trabajo falla y se conserva el catálogo anterior. Completo se refiere al listado expuesto por este endpoint, no al inventario privado ni a cada detalle de variante que pueda existir en otras rutas.

Política de consumo: un proceso, páginas de hasta 500 productos, separación mínima configurable de 1,5 segundos entre solicitudes, tiempos de espera y hasta cuatro intentos por página. Un HTTP 429 respeta `Retry-After` numérico hasta 120 segundos; pausas mayores abortan el trabajo. La API no se consulta al buscar.
