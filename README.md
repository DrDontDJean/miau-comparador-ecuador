# Miau

Buscador de productos de tiendas de Ecuador. Código en Python/Flask y catálogo en MongoDB. El respaldo incluido contiene 118.112 productos de 17 tiendas (25/09/2026).

## Instalar en otra computadora (Windows)

1. Instalar Python 3.11 o superior, MongoDB Community Server, Git y Git LFS.
2. Clonar el repositorio y descargar el respaldo:

   ```powershell
   git lfs install
   git clone https://github.com/DrDontDJean/miau-comparador-ecuador.git
   cd miau-comparador-ecuador
   git lfs pull
   ```

3. Ejecutar `ABRIR_MIAU.bat`. La primera vez crea el entorno, restaura el catálogo y abre la web en http://127.0.0.1:5001.

El repositorio es privado: cada integrante necesita acceso para clonarlo.

## Uso

- `ABRIR_MIAU.bat`: inicia MongoDB, la web y el programador.
- `SINCRONIZAR_AHORA.bat`: actualiza el catálogo desde las APIs.
- `DETENER_MIAU.bat`: cierra la web y el programador.
- Actualización automática: 03:00 (Ecuador), mientras el equipo esté encendido. El horario se cambia en `.env`.

MongoDB Compass: `mongodb://127.0.0.1:27018`, base `frecuento_catalogo`.

## Archivos principales

- `app/`: código de la aplicación y conectores de tiendas.
- `Tiendas_Ecuador_APIs.xlsx`: listado de tiendas y APIs.
- `respaldo/catalogo.jsonl.gz`: copia del catálogo; Git LFS la descarga con el proyecto.
- `docs/INTEGRACION_APIS.md`: notas para incorporar tiendas.

Para actualizar el respaldo compartido, ejecutar `.venv\Scripts\python.exe transferir_catalogo.py exportar` y subir el cambio a GitHub. `.env`, `.venv/` y `data/` permanecen locales.
