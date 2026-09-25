import logging
from math import ceil
from uuid import uuid4
from app.negocio.normalizacion import normalizar_producto
from app.datos.repositorio import ahora

log = logging.getLogger(__name__)


class ServicioSincronizacion:
    def __init__(self, fuente, repositorio):
        self.fuente = fuente
        self.repo = repositorio

    def ejecutar(self, motivo='programada'):
        token = uuid4().hex
        if not self.repo.adquirir(token):
            return {'estado': 'omitida', 'motivo': 'Ya existe una sincronización en curso.'}
        paginas = 0
        vistos = set()
        try:
            self.repo.iniciar(token, motivo)
            fecha = ahora()
            primera = self.fuente.pagina(1)
            total, limite, numero_paginas = (primera[k] for k in ('count', 'limit', 'pages'))
            if total < 1 or numero_paginas != ceil(total / limite) or numero_paginas > 10000:
                raise ValueError('Catálogo vacío o paginación inconsistente; no se sustituye el catálogo anterior.')
            self.repo.progreso(token, esperados=total)
            for numero in range(1, numero_paginas + 1):
                self.repo.renovar(token)
                respuesta = primera if numero == 1 else self.fuente.pagina(numero)
                if any(respuesta[k] != primera[k] for k in ('count', 'limit', 'pages')):
                    raise ValueError('El catálogo cambió durante la descarga; se requiere una nueva ejecución.')
                productos = [normalizar_producto(p) for p in respuesta['results']]
                esperados = min(limite, total - (numero - 1) * limite)
                if len(productos) != esperados:
                    raise ValueError('Una página no contiene la cantidad declarada.')
                ids = {p['id_externo'] for p in productos}
                if len(ids) != len(productos) or vistos.intersection(ids):
                    raise ValueError('La paginación repitió productos; se conserva el catálogo anterior.')
                vistos.update(ids)
                self.repo.insertar_pagina(token, productos, fecha)
                paginas = numero
                self.repo.progreso(token, paginas=paginas, productos=len(vistos))
                log.info('Página %s/%s: %s/%s productos', numero, numero_paginas, len(vistos), total)
            self.repo.renovar(token)
            self.repo.publicar(token, total)
            self.repo.progreso(token, estado='completada', fin=ahora())
            return {'estado': 'completada', 'productos': total, 'paginas': paginas, 'generacion': token}
        except Exception as error:
            # Mensaje controlado para la web; los detalles técnicos quedan en el log local.
            log.exception('Falló la sincronización %s', token)
            mensaje = str(error) if isinstance(error, ValueError) else 'Error de acceso a la API o MongoDB. Revisar data/logs.'
            self.repo.progreso(token, estado='fallida', fin=ahora(), error=mensaje)
            return {'estado': 'fallida', 'productos': len(vistos), 'paginas': paginas, 'error': mensaje}
        finally:
            self.repo.liberar(token)
