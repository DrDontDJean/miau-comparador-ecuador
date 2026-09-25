# Arquitectura en tres capas

## Integración actual (17 tiendas)

```mermaid
flowchart LR
    A[APIs: Frecuento, VTEX, WooCommerce, Shopify y Magento] --> B[Datos: conectores HTTP y paginación]
    T[APScheduler: actualización diaria] --> C[Negocio: normalización, integridad y publicación]
    B --> C
    C --> D[Datos: repositorio PyMongo]
    D <--> M[(MongoDB: productos, control y sincronizaciones)]
    U[Usuario] --> W[Presentación: Flask, HTML y CSS]
    W --> S[Negocio: búsqueda y filtros]
    S --> D
    W --> U
```

Cada tienda tiene una generación publicada y un bloqueo independientes. La búsqueda conjunta consulta las generaciones vigentes en MongoDB; el filtro de tienda limita los resultados a una fuente. El proceso programado consulta las APIs y solo publica una generación cuando está completa. La ficha conserva la URL original para abrir el producto en la tienda. Se muestran resultados ordenados por precio, pero todavía no se agrupan automáticamente modelos equivalentes.

Los diagramas siguientes describen el conector original de Frecuento y siguen siendo un ejemplo concreto de las mismas tres capas.

## Componentes y dependencias

```mermaid
flowchart TB
    U[Usuario del buscador]
    T[Tarea diaria APScheduler\n03:00 America/Guayaquil]
    subgraph P[1. Presentación]
        W[Flask · rutas web y API local]
        V[HTML / Jinja / CSS\nBúsqueda y resultados]
    end
    subgraph N[2. Negocio — Python]
        B[Servicio de catálogo\nValidación, filtros, orden y paginación]
        S[Servicio de sincronización\nNormalización y control de integridad]
    end
    subgraph D[3. Datos — Python]
        R[Repositorio de catálogo\nPyMongo]
        C[Conector Frecuento\nRequests / JSON / paginación]
    end
    M[(MongoDB\nproductos · control · sincronizaciones)]
    A[API JSON de Frecuento\napp.frecuento.com/products/]
    U -->|consulta| W
    W --> B
    B --> R
    R <-->|lecturas y escrituras| M
    R -->|productos guardados| B
    B --> W
    W --> V
    V -->|resultados| U
    T --> S
    S -->|solicitar páginas| C
    C <-->|HTTP GET / JSON| A
    C -->|páginas recibidas| S
    S -->|guardar y publicar catálogo completo| R
```

La API de Frecuento y MongoDB son sistemas externos a las capas. El programador invoca la capa de negocio. La presentación recibe un servicio que solo tiene acceso al repositorio; no recibe el conector HTTP. Las dependencias se conectan en los puntos de entrada, no dentro de las plantillas.

## Secuencia de actualización

```mermaid
sequenceDiagram
    participant T as Programador
    participant N as Negocio
    participant C as Datos: conector
    participant F as API Frecuento
    participant R as Datos: repositorio
    participant M as MongoDB
    T->>N: Ejecutar sincronización
    N->>R: Adquirir bloqueo e iniciar generación
    R->>M: Guardar control y ejecución
    loop Cada página declarada
        N->>C: Obtener página
        C->>F: GET /products/?limit=500&page=N
        F-->>C: count, limit, pages, results
        C-->>N: Respuesta JSON
        N->>N: Normalizar y comprobar IDs y cantidades
        N->>R: Guardar página de generación nueva
        R->>M: Insertar documentos
    end
    N->>R: Publicar si catálogo íntegro
    R->>M: Cambiar generación activa en un documento
    N->>R: Registrar finalización y liberar bloqueo
```

Un error antes de publicar conserva el puntero anterior. No se emplea una transacción de múltiples documentos; la visibilidad del catálogo depende de un cambio atómico en `control`. La generación completa se almacena antes de ese cambio.

## Secuencia de búsqueda

```mermaid
sequenceDiagram
    participant U as Usuario
    participant P as Presentación Flask
    participant N as Negocio
    participant D as Datos: repositorio
    participant M as MongoDB
    U->>P: GET /?q=televisor&orden=precio_asc
    P->>N: Buscar con parámetros
    N->>N: Validar y normalizar texto
    N->>D: Consultar catálogo publicado
    D->>M: Leer generación y productos coincidentes
    M-->>D: Resultados, total y fecha
    D-->>N: Diccionarios Python
    N-->>P: Página de resultados
    P-->>U: HTML con productos y precios
```

No hay ninguna llamada a Frecuento en esta secuencia. Las imágenes se muestran mediante URL públicas de la fuente, pero el catálogo y los precios proceden de MongoDB.

## Funciones reutilizables

| Función o componente | Responsabilidad |
|---|---|
| `normalizar_texto` | Unificar mayúsculas, espacios y acentos |
| `dinero` | Validar importes decimales |
| `normalizar_producto` | Transformar un producto JSON al modelo local |
| `filtro_busqueda` | Construir filtros de texto escapados |
| `a_bson` / `a_python` | Convertir decimales de forma recursiva |
| `FrecuentoAPI.pagina` | Solicitudes, pausas, reintentos y validación del contrato |
| `RepositorioCatalogo` | Encapsular consultas y escrituras de MongoDB |
| `ServicioSincronizacion` | Recorrer, comprobar y publicar el catálogo |

## Agrupación de modelos equivalentes (pendiente)

Los conectores de las 17 tiendas ya proporcionan productos normalizados. Para comparar ofertas del mismo modelo con precisión todavía se necesita resolver identidades y variantes equivalentes, además de revisar las condiciones de cada precio. El listado actual ordena productos de distintas tiendas por importe y enlaza con sus páginas de origen.
