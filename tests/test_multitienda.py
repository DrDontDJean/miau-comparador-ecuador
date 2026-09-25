from decimal import Decimal
import pytest
from test_flujo import repo, producto, Fuente
from app import create_app
from app.config import Config
from app.datos.repositorio import RepositorioCatalogo
from app.negocio.sincronizacion import ServicioSincronizacion
from app.negocio.multitienda import SincronizacionAPI
from app.negocio.productos_api import normalizar_api


def woo(i=1):
    return {'id': i, 'name': 'Producto Woo', 'prices': {'price': '1099', 'currency_code': 'USD', 'currency_minor_unit': 2},
            'is_in_stock': True}


class API:
    fuente, tipo, base, total = 'computron', 'woo', 'https://www.computron.com.ec', 1
    def lotes(self):
        yield [woo()]


def test_fuentes_aisladas_y_fallo_no_reemplaza(repo):
    ServicioSincronizacion(Fuente([producto(1)]), repo).ejecutar()
    otra = RepositorioCatalogo(repo.db, 'computron')
    assert SincronizacionAPI(API(), otra).ejecutar()['estado'] == 'completada'
    assert repo.estado()['total'] == 2
    assert repo.contar_tiendas() == {'frecuento': 1, 'computron': 1}
    cliente = create_app(Config(), repo).test_client()
    assert cliente.get('/api/productos').json['total'] == 2
    assert cliente.get('/api/productos?tienda=computron').json['productos'][0]['precio'] == '10.99'
    assert cliente.get('/tiendas/computron/productos/1').status_code == 200
    assert cliente.get('/productos/1').status_code == 200
    assert repo.adquirir('a') and otra.adquirir('b')
    repo.liberar('a'); otra.liberar('b')
    class Rota(API):
        total = 2
    generacion = otra.estado()['generacion']
    assert SincronizacionAPI(Rota(), otra).ejecutar()['estado'] == 'fallida'
    assert otra.estado()['generacion'] == generacion
    assert repo.estado()['total'] == 2


def test_mapeos_precio_y_variantes():
    assert normalizar_api(woo(), 'computron', 'woo', '')['precio'] == Decimal('10.99')
    p = {'id': 2, 'title': 'Producto', 'handle': 'producto', 'variants': [
        {'id': 1, 'price': '10', 'available': False}, {'id': 2, 'price': '20', 'available': True}]}
    resultado = normalizar_api(p, 'ekustore', 'shopify', 'https://ekustore.com')
    assert resultado['precio'] == 20 and resultado['disponible']
    assert len(resultado['variantes']) == 2
    p['title'] = 'Aspiradora Env Dualforce 600 Wet&Dry'
    assert normalizar_api(p, 'ekustore', 'shopify', 'https://ekustore.com')['nombre'] == p['title']


def test_decimal_original_no_se_redondea():
    from app.datos.repositorio import a_bson
    valor = Decimal('0.123456789012345678901234567890123456789')
    assert a_bson({'original': valor})['original'] == str(valor)


def test_vtex_conserva_ruta_de_subcategoria():
    from app.datos.fuentes import CatalogoAPI
    api = CatalogoAPI('kywi', delay=0)
    rutas = []
    def buscar(inicio=0, filtros=None, fin=None, orden=None):
        rutas.append(filtros)
        if filtros in (None, 'C:/50/'):
            return [{'productId': str(i)} for i in range(50)], 3000
        if filtros == 'C:/50/70/':
            return [{'productId': str(i)} for i in range(50)], 50
        raise AssertionError(filtros)
    api.vtex_buscar = buscar
    api.get = lambda *a: ([{'id':50,'children':[{'id':70,'children':[]}]}], {})
    next(api.vtex())
    assert 'C:/50/70/' in rutas


def test_vtex_recupera_intervalo_500_sin_omitir_productos():
    from app.datos.fuentes import CatalogoAPI
    from app.datos.frecuento import ErrorFuente
    api = CatalogoAPI('crecos', delay=0)
    def respuesta(ruta, params):
        inicio, fin = params['_from'], params['_to']
        if fin-inicio >= 10:
            raise ErrorFuente('API no disponible: HTTP 500 o respuesta no JSON.')
        return [{'productId': str(i)} for i in range(inicio, fin+1)], {'resources': '0-199/200'}
    api.get = respuesta
    filas, total = api.vtex_buscar(150, 'C:/9/', 199)
    assert total == 200
    assert [p['productId'] for p in filas] == [str(i) for i in range(150, 200)]
