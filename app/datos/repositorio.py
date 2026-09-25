"""Generaciones completas: publicar cambia un único puntero atómico.

Una captura fallida jamás sustituye a la generación utilizada por las búsquedas.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from decimal import DecimalException
from bson.decimal128 import Decimal128
from pymongo.errors import DuplicateKeyError


def ahora():
    return datetime.now(timezone.utc)


def a_bson(valor):
    if isinstance(valor, Decimal):
        try:
            return Decimal128(valor)
        except DecimalException:
            # Datos originales de terceros pueden superar los 34 dígitos BSON.
            # Conservar su representación exacta sin redondear silenciosamente.
            return str(valor)
    if isinstance(valor, dict):
        return {k: a_bson(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [a_bson(v) for v in valor]
    return valor


def a_python(valor):
    if isinstance(valor, Decimal128):
        return valor.to_decimal()
    if isinstance(valor, dict):
        return {k: a_python(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [a_python(v) for v in valor]
    return valor


class RepositorioCatalogo:
    def __init__(self, db, fuente=None):
        self.db = db
        self.fuente = fuente
        self.control_id = 'catalogo' if fuente in (None, 'frecuento') else 'catalogo:' + fuente

    def crear_indices(self):
        self.db.productos.create_index([('generacion', 1), ('id_externo', 1)], unique=True)
        self.db.productos.create_index([('generacion', 1), ('precio_ausente', 1), ('precio', 1), ('id_externo', 1)])
        self.db.sincronizaciones.create_index([('inicio', -1)])

    def adquirir(self, token):
        fecha = ahora()
        try:
            self.db.control.update_one({'_id': self.control_id, '$or': [
                {'lock_hasta': {'$lt': fecha}}, {'lock_hasta': {'$exists': False}}]},
                {'$set': {'lock_token': token, 'lock_hasta': fecha + timedelta(minutes=10)}}, upsert=True)
            return True
        except DuplicateKeyError:
            return False

    def renovar(self, token):
        r = self.db.control.update_one({'_id': self.control_id, 'lock_token': token},
            {'$set': {'lock_hasta': ahora() + timedelta(minutes=10)}})
        if not r.matched_count:
            raise RuntimeError('La sincronización perdió su bloqueo.')

    def liberar(self, token):
        self.db.control.update_one({'_id': self.control_id, 'lock_token': token},
                                  {'$unset': {'lock_token': '', 'lock_hasta': ''}})

    def iniciar(self, token, motivo):
        self.db.sincronizaciones.insert_one({'_id': token, 'estado': 'en_curso', 'inicio': ahora(),
            'motivo': motivo, 'fuente': self.fuente or 'frecuento', 'paginas': 0, 'productos': 0})

    def progreso(self, token, **campos):
        self.db.sincronizaciones.update_one({'_id': token}, {'$set': a_bson(campos)})

    def insertar_pagina(self, token, productos, fecha):
        if productos:
            self.db.productos.insert_many([a_bson({**p, 'generacion': token, 'actualizado_en': fecha}) for p in productos])

    def publicar(self, token, total):
        if self.db.productos.count_documents({'generacion': token}) != total:
            raise RuntimeError('El total guardado no coincide con el catálogo.')
        resultado = self.db.control.update_one({'_id': self.control_id, 'lock_token': token},
            {'$set': {'generacion': token, 'total': total, 'actualizado_en': ahora()}})
        if not resultado.matched_count:
            raise RuntimeError('No se pudo publicar la actualización.')

    def estado(self):
        controles = self.controles()
        control = self.db.control.find_one({'_id': self.control_id}) or {}
        if self.fuente is None and controles:
            control = {'total': sum(c.get('total', 0) for c in controles),
                       'actualizado_en': max(c['actualizado_en'] for c in controles),
                       'generacion': controles[0]['generacion']}
        filtro = {'fuente': self.fuente} if self.fuente else {}
        ultima = self.db.sincronizaciones.find_one(filtro, sort=[('inicio', -1)]) or {}
        # Las credenciales y errores internos nunca se incluyen en el estado público.
        return {'total': control.get('total', 0), 'actualizado_en': control.get('actualizado_en'),
                'generacion': control.get('generacion'), 'ultima': {k: ultima.get(k) for k in
                ('estado', 'inicio', 'fin', 'paginas', 'productos', 'esperados', 'error')}}

    def obtener(self, identificador):
        fuente = self.fuente or 'frecuento'
        control = self.db.control.find_one({'_id': self.control_id}) or {}
        if not control.get('generacion'):
            return None
        return a_python(self.db.productos.find_one({'generacion': control['generacion'],
            'fuente': fuente, 'id_externo': identificador}, {'_id': 0, 'original': 0, 'busqueda': 0}))

    def obtener_fuente(self, identificador, fuente):
        return RepositorioCatalogo(self.db, fuente).obtener(identificador)

    def controles(self):
        filtro = {'_id': self.control_id} if self.fuente else {'_id': {'$regex': r'^catalogo(?::|$)'}}
        return list(self.db.control.find({**filtro, 'generacion': {'$exists': True}}))

    def consulta_activa(self):
        return {'$or': [{'generacion': c['generacion'],
                        'fuente': 'frecuento' if c['_id'] == 'catalogo' else c['_id'].split(':', 1)[1]}
                       for c in self.controles()]} or {}

    def buscar(self, filtros, pagina, por_pagina, orden, disponible):
        estado = self.estado()
        gen = estado['generacion']
        if not gen:
            return [], 0, estado
        consulta = self.consulta_activa()
        if filtros:
            consulta['$and'] = a_bson(filtros)
        if disponible:
            consulta['disponible'] = True
        total = self.db.productos.count_documents(consulta)
        ordenes = {'precio_asc': [('precio_ausente', 1), ('precio', 1), ('fuente', 1), ('id_externo', 1)],
                   'precio_desc': [('precio_ausente', 1), ('precio', -1), ('fuente', 1), ('id_externo', 1)],
                   'nombre': [('nombre', 1), ('fuente', 1), ('id_externo', 1)]}
        cursor = self.db.productos.find(consulta, {'original': 0, 'busqueda': 0, '_id': 0}).sort(ordenes[orden])
        return a_python(list(cursor.skip((pagina - 1) * por_pagina).limit(por_pagina))), total, estado

    def contar_tiendas(self):
        return {('frecuento' if c['_id'] == 'catalogo' else c['_id'].split(':', 1)[1]): c['total']
                for c in self.controles()}

    def estados_tiendas(self):
        return {c['_id'].split(':', 1)[-1] if c['_id'] != 'catalogo' else 'frecuento': c
                for c in self.db.control.find({'_id': {'$regex': r'^catalogo(?::|$)'}})}

    def resultado_fuente(self, estado, mensaje=''):
        self.db.control.update_one({'_id': self.control_id}, {'$set': {
            'estado_sync': estado, 'mensaje_sync': mensaje, 'intento_en': ahora()}}, upsert=True)
