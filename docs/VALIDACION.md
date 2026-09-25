# Validación de la primera etapa

Carga real realizada el 18 de septiembre de 2026, hora de Ecuador. Evidencia cuantitativa: [validacion-carga.json](validacion-carga.json).

| Comprobación | Resultado |
|---|---|
| Fuente | API JSON de Frecuento, HTTP 200, acceso sin autenticación |
| Catálogo publicado | 35.644 productos |
| Identidades distintas | 35.644 IDs de la fuente |
| Paginación | 72 páginas completas según el contrato del endpoint |
| Persistencia | MongoDB real, base `frecuento_catalogo`, puerto 27018 |
| Búsqueda web | Verificada en el navegador con lavadora y televisor |
| Interfaz | Revisión visual de tarjetas, formulario, precios y navegación |
| Programación | Proceso APScheduler activo, horario diario 03:00 America/Guayaquil |
| Pruebas automatizadas | 10 correctas, menos de dos segundos de ejecución |

Las pruebas usan una base temporal independiente y cubren:

- Publicación de un catálogo completo y sustitución de productos retirados.
- Conservación de la versión anterior cuando falla una página.
- Rechazo de páginas con IDs repetidos.
- Exclusión de sincronizaciones concurrentes mediante bloqueo MongoDB.
- Búsqueda y detalle con todas las solicitudes HTTP externas bloqueadas por la prueba.
- Orden numérico de precios, precisión decimal y búsqueda sin acentos.
- Rechazo de entrada inválida, catálogo vacío y precios negativos.
- Contrato de paginación y reintento ante HTTP 429.
- Reglas de importación de las tres capas.
- Precio no determinado de un producto padre con variantes.
- Ejecución efectiva de una tarea APScheduler sin intervención de búsquedas.

La ejecución programada fue probada con una fuente controlada y disparo inmediato en una base temporal. No se simuló que hubiera transcurrido una noche: la carga real fue manual, y el programador diario quedó iniciado para las siguientes actualizaciones.

La evidencia corresponde al catálogo público expuesto durante la carga. No certifica el inventario interno de Frecuento ni la estabilidad futura de su endpoint. El esquema de páginas no ofrece un snapshot transaccional del proveedor; se comprueban totales estables e IDs únicos, aunque diferentes productos pueden reflejar instantes distintos dentro de la descarga.
