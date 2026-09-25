"""Puntos de entrada separados para web, actualización y planificador."""
import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from app.config import Config, ROOT
from app.datos.conexion import conectar
from app.datos.frecuento import FrecuentoAPI
from app.datos.repositorio import RepositorioCatalogo
from app.negocio.sincronizacion import ServicioSincronizacion
from app.negocio.multitienda import SincronizacionTiendas
from app.datos.fuentes import FUENTES


def servicio(config, tienda=None, pendientes=False):
    return SincronizacionTiendas(conectar(config), config, tienda, pendientes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('accion', choices=['web', 'sincronizar', 'programador', 'estado'])
    parser.add_argument('--tienda', choices=['frecuento', *FUENTES])
    parser.add_argument('--pendientes', action='store_true', help='Actualizar solo tiendas sin catálogo o con errores.')
    args = parser.parse_args()
    config = Config.cargar()
    (ROOT / 'data' / 'logs').mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / 'data/logs/aplicacion.log', encoding='utf-8')])
    if args.accion == 'web':
        from app import create_app
        from waitress import serve
        serve(create_app(config), host='127.0.0.1', port=config.port, threads=4)
    elif args.accion == 'sincronizar':
        resultado = servicio(config, args.tienda, args.pendientes).ejecutar('manual')
        print(json.dumps(resultado, ensure_ascii=False))
        return 1 if resultado['estado'] == 'fallida' else 0
    elif args.accion == 'estado':
        print(json.dumps(RepositorioCatalogo(conectar(config)).estado(), default=str, ensure_ascii=False, indent=2))
    else:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
        worker = servicio(config)
        scheduler = BlockingScheduler(timezone=config.timezone)
        scheduler.add_job(worker.ejecutar, CronTrigger(hour=config.sync_hour, minute=config.sync_minute,
            timezone=config.timezone), id='frecuento-diario', max_instances=1, coalesce=True,
            misfire_grace_time=3600)
        # Recupera la carga inicial o la ejecución diaria perdida mientras el equipo estaba apagado.
        estado = worker.repo.estado()
        local = datetime.now(ZoneInfo(config.timezone))
        vencimiento = local.replace(hour=config.sync_hour, minute=config.sync_minute, second=0, microsecond=0)
        if vencimiento > local:
            vencimiento -= timedelta(days=1)
        controles = worker.repo.controles()
        if len(controles) < len(FUENTES)+1 or any(c['actualizado_en'] < vencimiento for c in controles):
            scheduler.add_job(worker.ejecutar, 'date', args=['inicio_o_recuperacion'],
                              id='recuperacion', misfire_grace_time=3600)
        logging.info('Actualización diaria a las %02d:%02d (%s); mantener este proceso activo.',
                     config.sync_hour, config.sync_minute, config.timezone)
        scheduler.start()
    return 0


if __name__ == '__main__':
    sys.exit(main())
