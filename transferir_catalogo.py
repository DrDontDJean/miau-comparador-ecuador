"""Respaldo portable de las generaciones publicadas de todas las tiendas."""
import argparse
import gzip
from pathlib import Path
from uuid import uuid4
from bson import json_util
from app.config import Config, ROOT
from app.datos.conexion import conectar
from app.datos.repositorio import RepositorioCatalogo, ahora
from app.negocio.tiendas import obtener_tienda

ARCHIVO = ROOT / 'respaldo/catalogo.jsonl.gz'


def exportar(db, destino=ARCHIVO):
    controles = RepositorioCatalogo(db).controles()
    if not controles:
        raise ValueError('No existe un catálogo publicado para exportar.')
    fuentes = [{'fuente': 'frecuento' if c['_id'] == 'catalogo' else c['_id'].split(':', 1)[1],
                'total': c['total'], 'capturado_en': c['actualizado_en']} for c in controles]
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + '.tmp')
    cantidad = 0
    with gzip.open(temporal, 'wt', encoding='utf-8') as salida:
        salida.write(json_util.dumps({'formato': 'miau-2', 'fuentes': fuentes,
                                     'total': sum(f['total'] for f in fuentes)}) + '\n')
        for control, fuente in zip(controles, fuentes):
            recibidos = 0
            consulta = {'generacion': control['generacion'], 'fuente': fuente['fuente']}
            for producto in db.productos.find(consulta, {'_id': 0, 'generacion': 0}):
                salida.write(json_util.dumps(producto) + '\n')
                recibidos += 1
            if recibidos != fuente['total']:
                raise ValueError('La copia no coincide con el total de ' + fuente['fuente'])
            cantidad += recibidos
    temporal.replace(destino)
    return cantidad


def restaurar(db, origen=ARCHIVO):
    RepositorioCatalogo(db).crear_indices()
    pendientes, contadores, lotes = {}, {}, {}
    try:
        with gzip.open(origen, 'rt', encoding='utf-8') as entrada:
            meta = json_util.loads(next(entrada))
            if meta.get('formato') == 'frecuento-1':
                fuentes = [{'fuente': 'frecuento', 'total': meta['total'],
                            'capturado_en': meta['capturado_en']}]
            elif meta.get('formato') == 'miau-2':
                fuentes = meta['fuentes']
            else:
                raise ValueError('Formato de respaldo inválido.')
            for f in fuentes:
                fuente = f['fuente']
                if (not obtener_tienda(fuente) or fuente in contadores or
                        type(f['total']) is not int or f['total'] < 1):
                    raise ValueError('Fuente de respaldo inválida.')
                contadores[fuente], lotes[fuente] = 0, []
                repo = RepositorioCatalogo(db, fuente)
                if repo.estado()['generacion']:
                    continue
                token = uuid4().hex
                if not repo.adquirir(token):
                    raise ValueError('Hay una actualización en curso: ' + fuente)
                pendientes[fuente] = (repo, token)
                repo.iniciar(token, 'restauracion_del_paquete')
            if not pendientes:
                return 0
            for linea in entrada:
                p = json_util.loads(linea)
                fuente = p.get('fuente')
                if fuente not in contadores or not p.get('id_externo') or not p.get('nombre'):
                    raise ValueError('Producto de respaldo inválido.')
                contadores[fuente] += 1
                if fuente not in pendientes:
                    continue
                repo, token = pendientes[fuente]
                p.pop('_id', None)
                p['generacion'] = token
                lotes[fuente].append(p)
                if len(lotes[fuente]) >= 500:
                    repo.renovar(token)
                    db.productos.insert_many(lotes[fuente])
                    lotes[fuente] = []
            if any(contadores[f['fuente']] != f['total'] for f in fuentes):
                raise ValueError('El respaldo está incompleto.')
            for fuente, lote in lotes.items():
                if lote:
                    repo, token = pendientes[fuente]
                    repo.renovar(token)
                    db.productos.insert_many(lote)
            for f in fuentes:
                if f['fuente'] not in pendientes:
                    continue
                repo, token = pendientes[f['fuente']]
                repo.renovar(token)
                repo.publicar(token, f['total'])
                db.control.update_one({'_id': repo.control_id, 'generacion': token},
                    {'$set': {'actualizado_en': f['capturado_en']}})
                repo.resultado_fuente('completada')
                repo.progreso(token, estado='completada', productos=f['total'],
                              esperados=f['total'], fin=ahora(), fecha_origen=f['capturado_en'])
        return sum(contadores[f] for f in pendientes)
    except Exception:
        for repo, token in pendientes.values():
            if repo.estado()['generacion'] != token:
                repo.progreso(token, estado='fallida', fin=ahora(), error='No se pudo restaurar la copia.')
        raise
    finally:
        for repo, token in pendientes.values():
            repo.liberar(token)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('accion', choices=['exportar', 'restaurar'])
    args = parser.parse_args()
    db = conectar(Config.cargar())
    total = exportar(db) if args.accion == 'exportar' else restaurar(db)
    print(f'{total} productos transferidos. Los catálogos existentes se conservan.')
