import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.datos.frecuento import FrecuentoAPI
from app.datos.fuentes import CatalogoAPI, FUENTES
from app.datos.repositorio import RepositorioCatalogo, ahora
from app.negocio.sincronizacion import ServicioSincronizacion
from app.negocio.productos_api import normalizar_api

log = logging.getLogger(__name__)


class SincronizacionAPI:
    def __init__(self, api, repo):
        self.api, self.repo = api, repo

    def ejecutar(self, motivo='programada'):
        token, vistos, paginas = uuid4().hex, set(), 0
        if not self.repo.adquirir(token):
            return {'estado': 'omitida', 'fuente': self.api.fuente}
        try:
            self.repo.iniciar(token, motivo)
            self.repo.resultado_fuente('en_curso')
            fecha = ahora()
            for lote in self.api.lotes():
                self.repo.renovar(token)
                productos = []
                ids_lote = set()
                for original in lote:
                    p = normalizar_api(original, self.api.fuente, self.api.tipo, self.api.base)
                    identidad = p['id_externo']
                    if identidad in ids_lote or (identidad in vistos and self.api.tipo != 'vtex'):
                        raise ValueError('La API repitió productos al paginar.')
                    ids_lote.add(identidad)
                    # VTEX puede incluir un producto en distintas categorías.
                    if identidad not in vistos:
                        productos.append(p)
                        vistos.add(identidad)
                self.repo.insertar_pagina(token, productos, fecha)
                paginas += 1
                self.repo.progreso(token, paginas=paginas, productos=len(vistos), esperados=self.api.total)
                log.info('%s: lote %s, %s productos, total API %s', self.api.fuente, paginas, len(vistos), self.api.total)
            if not vistos or (self.api.total is not None and len(vistos) != self.api.total):
                raise ValueError(f'Catálogo incompleto: {len(vistos)} productos; API declara {self.api.total}.')
            self.repo.renovar(token)
            self.repo.publicar(token, len(vistos))
            self.repo.progreso(token, estado='completada', fin=ahora())
            self.repo.resultado_fuente('completada')
            return {'fuente': self.api.fuente, 'estado': 'completada', 'productos': len(vistos)}
        except Exception as error:
            log.exception('Error al actualizar %s', self.api.fuente)
            mensaje = str(error)[:250] if isinstance(error, (ValueError, RuntimeError)) else 'Error de conexión o contrato de API. Revisar registro local.'
            self.repo.progreso(token, estado='fallida', error=mensaje, fin=ahora())
            self.repo.resultado_fuente('fallida', mensaje)
            return {'fuente': self.api.fuente, 'estado': 'fallida', 'error': mensaje, 'productos': len(vistos)}
        finally:
            self.repo.liberar(token)


class SincronizacionTiendas:
    def __init__(self, db, config, tienda=None, pendientes=False):
        self.db, self.config, self.tienda = db, config, tienda
        self.pendientes = pendientes
        self.repo = RepositorioCatalogo(db)
        self.repo.crear_indices()

    def ejecutar(self, motivo='programada'):
        fuentes = [self.tienda] if self.tienda else ['frecuento', *FUENTES]
        if self.pendientes:
            estados = self.repo.estados_tiendas()
            fuentes = [f for f in fuentes if not estados.get(f, {}).get('generacion') or
                       estados.get(f, {}).get('estado_sync') == 'fallida']
        def actualizar(fuente):
            repo = RepositorioCatalogo(self.db, fuente)
            if motivo == 'inicio_o_recuperacion':
                local = datetime.now(ZoneInfo(self.config.timezone))
                limite = local.replace(hour=self.config.sync_hour, minute=self.config.sync_minute, second=0, microsecond=0)
                if limite > local:
                    limite -= timedelta(days=1)
                estado = repo.estado()
                if estado['actualizado_en'] and estado['actualizado_en'] >= limite:
                    repo.db.control.update_one({'_id': repo.control_id, 'lock_hasta': {'$lt': ahora()}},
                        {'$unset': {'lock_token': '', 'lock_hasta': ''},
                         '$set': {'estado_sync': 'interrumpida', 'mensaje_sync': 'Se conserva el último catálogo completo.'}})
                    return {'fuente': fuente, 'estado': 'omitida', 'motivo': 'Catálogo vigente'}
            if fuente == 'frecuento':
                repo.resultado_fuente('en_curso')
                r = ServicioSincronizacion(FrecuentoAPI(self.config.page_size, self.config.delay), repo).ejecutar(motivo)
                repo.resultado_fuente(r['estado'], r.get('error', ''))
                return {'fuente': fuente, **r}
            return SincronizacionAPI(CatalogoAPI(fuente, self.config.delay), repo).ejecutar(motivo)
        with ThreadPoolExecutor(max_workers=3) as pool:
            resultados = list(pool.map(actualizar, fuentes))
        return {'estado': 'fallida' if any(r['estado'] == 'fallida' for r in resultados) else 'completada',
                'tiendas': resultados}
