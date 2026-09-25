"""Comprobaciones para el lanzador; no imprime credenciales ni trazas."""
import importlib
import sys
from urllib.parse import urlsplit


def main():
    accion = sys.argv[1]
    try:
        if accion == 'dependencias':
            for modulo in ('flask', 'pymongo', 'requests', 'dotenv', 'apscheduler', 'waitress'):
                importlib.import_module(modulo)
        else:
            from app.config import Config
            c = Config.cargar()
            if accion == 'mongo':
                from app.datos.conexion import conectar
                conectar(c).command('ping')
            elif accion == 'puerto-mongo':
                u = urlsplit(c.mongo_uri)
                print(u.port or 27017 if u.scheme == 'mongodb' and u.hostname in {'127.0.0.1', 'localhost'} else 'REMOTO')
            elif accion == 'puerto-web':
                print(c.port)
        return 0
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
