"""Composición de dependencias. La web recibe solo el servicio de búsqueda."""
from flask import Flask
from app.config import Config
from app.datos.conexion import conectar
from app.datos.repositorio import RepositorioCatalogo
from app.negocio.catalogo import ServicioCatalogo


def create_app(config=None, repositorio=None):
    config = config or Config.cargar()
    repo = repositorio or RepositorioCatalogo(conectar(config))
    repo.crear_indices()
    app = Flask(__name__, template_folder='presentacion/templates',
                static_folder='presentacion/static')
    app.config.update(MAX_CONTENT_LENGTH=16384)
    app.extensions['catalogo'] = ServicioCatalogo(repo)
    app.config['SYNC_LABEL'] = f'{config.sync_hour:02d}:{config.sync_minute:02d} · {config.timezone}'
    from app.presentacion.rutas import web
    app.register_blueprint(web)
    from pymongo.errors import PyMongoError
    @app.errorhandler(PyMongoError)
    def mongo_error(error):
        from flask import render_template
        app.logger.error('MongoDB no disponible: %s', type(error).__name__)
        return render_template('error.html', mensaje='MongoDB no está disponible. Ejecuta ABRIR_FRECUENTO.bat.'), 503
    return app
