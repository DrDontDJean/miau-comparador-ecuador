"""Pruebas de contrato y flujo. MongoDB de prueba usa una base temporal aislada."""
import ast
import json
import os
from pathlib import Path
from uuid import uuid4
import pytest
import requests
from pymongo import MongoClient
from app import create_app
from app.config import Config
from app.datos.frecuento import FrecuentoAPI, ErrorFuente
from app.datos.repositorio import RepositorioCatalogo
from app.negocio.sincronizacion import ServicioSincronizacion


def producto(i, precio='12.34', nombre=None):
    return {'id': i, 'name': nombre or f'Producto {i}', 'amount_total': precio,
            'amount_incl_tax': precio, 'brand': 'Marca', 'has_stock': True,
            'categories': [{'id': 1, 'name': 'Electrónica'}], 'photos': [], 'variants': []}


class Fuente:
    def __init__(self, productos, fail=False, repeat=False):
        self.productos, self.fail, self.repeat = productos, fail, repeat

    def pagina(self, n):
        if n == 2 and self.fail:
            raise ErrorFuente('Interrupción simulada')
        if self.repeat:
            n = 1
        return {'count': len(self.productos), 'limit': 2, 'pages': (len(self.productos)+1)//2,
                'results': self.productos[(n-1)*2:n*2]}


@pytest.fixture
def repo():
    uri = os.getenv('TEST_MONGODB_URI')
    if not uri:
        pytest.skip('Configura TEST_MONGODB_URI para las pruebas de integración.')
    cliente = MongoClient(uri, serverSelectionTimeoutMS=2000, tz_aware=True)
    nombre = 'test_frecuento_' + uuid4().hex
    repositorio = RepositorioCatalogo(cliente[nombre])
    repositorio.crear_indices()
    yield repositorio
    cliente.drop_database(nombre)
    cliente.close()


def test_publica_todo_y_sustituye_desaparecidos(repo):
    s = ServicioSincronizacion(Fuente([producto(1), producto(2), producto(3)]), repo)
    assert s.ejecutar()['estado'] == 'completada'
    primera = repo.estado()['generacion']
    assert ServicioSincronizacion(Fuente([producto(2, '9.99')]), repo).ejecutar()['estado'] == 'completada'
    assert repo.estado()['generacion'] != primera
    assert repo.obtener('1') is None
    assert str(repo.obtener('2')['precio']) == '9.99'


@pytest.mark.parametrize('opciones', [{'fail': True}, {'repeat': True}])
def test_fallo_o_duplicado_no_reemplaza_catalogo(repo, opciones):
    ServicioSincronizacion(Fuente([producto(8)]), repo).ejecutar()
    gen = repo.estado()['generacion']
    result = ServicioSincronizacion(Fuente([producto(1), producto(2), producto(3)], **opciones), repo).ejecutar()
    assert result['estado'] == 'fallida'
    assert repo.estado()['generacion'] == gen
    assert repo.obtener('8') is not None


def test_concurrencia(repo):
    assert repo.adquirir('propietario')
    assert not repo.adquirir('otro')
    assert ServicioSincronizacion(Fuente([]), repo).ejecutar()['estado'] == 'omitida'
    repo.liberar('otro')
    assert not repo.adquirir('tercero')
    repo.liberar('propietario')
    assert repo.adquirir('nuevo')


def test_busqueda_solo_mongo_y_precios_exactos(repo, monkeypatch):
    datos = [producto(1, '99.90', 'Teléfono Samsung'), producto(2, '9.05', 'Teléfono Samsung'), producto(3)]
    ServicioSincronizacion(Fuente(datos), repo).ejecutar()
    def prohibido(*a, **k):
        pytest.fail('La búsqueda intentó acceder a una API externa.')
    monkeypatch.setattr(requests.sessions.Session, 'request', prohibido)
    cliente = create_app(Config(), repo).test_client()
    r = cliente.get('/api/productos?q=telefono+samsung')
    assert r.status_code == 200
    assert r.json['total'] == 2
    assert [x['precio'] for x in r.json['productos']] == ['9.05', '99.90']
    assert cliente.get('/?q=telefono').status_code == 200
    assert cliente.get('/productos/1').status_code == 200
    assert cliente.get('/estado').status_code == 404
    assert cliente.get('/arquitectura').status_code == 404
    assert cliente.get('/api/productos?pagina=-1').status_code == 400
    assert cliente.get('/api/productos?q=%3Cscript%3E').json['total'] == 0


def test_no_publica_vacio_ni_precio_invalido(repo):
    assert ServicioSincronizacion(Fuente([]), repo).ejecutar()['estado'] == 'fallida'
    assert ServicioSincronizacion(Fuente([producto(1, '-2')]), repo).ejecutar()['estado'] == 'fallida'
    assert repo.estado()['generacion'] is None


def test_tiendas_y_filtros_en_mongo(repo, monkeypatch):
    datos = [producto(i, str(i), 'Teléfono') for i in range(1, 31)]
    datos[-1]['has_stock'] = False
    ServicioSincronizacion(Fuente(datos), repo).ejecutar()
    monkeypatch.setattr(requests.sessions.Session, 'request',
                        lambda *a, **k: pytest.fail('La web no debe consultar las APIs.'))
    cliente = create_app(Config(), repo).test_client()
    inicio = cliente.get('/').get_data(as_text=True)
    assert 'Tiendas' in inicio and 'Novicompu' in inicio and '30 productos' in inicio
    assert cliente.get('/tiendas/frecuento').status_code == 200
    assert 'pendiente de sincronización' in cliente.get('/tiendas/novicompu').get_data(as_text=True)
    assert cliente.get('/tiendas/inventada').status_code == 404
    consulta = '/api/productos?tienda=frecuento&precio_min=10&precio_max=30&disponible=1&orden=precio_desc'
    r = cliente.get(consulta).json
    assert r['total'] == 20
    assert r['productos'][0]['precio'] == '29'
    assert r['productos'][-1]['precio'] == '10'
    assert cliente.get('/api/productos?tienda=novicompu').json['total'] == 0
    for invalido in ['precio_min=30&precio_max=10', 'precio_min=NaN', 'precio_max=-1', 'tienda=inventada']:
        assert cliente.get('/api/productos?' + invalido).status_code == 400
    html = cliente.get('/productos?tienda=frecuento&precio_min=1&orden=precio_desc&disponible=1').get_data(as_text=True)
    assert 'pagina=2' in html and 'precio_min=1' in html and 'orden=precio_desc' in html
    assert 'name="categoria"' not in html


def test_contrato_api_paginacion_y_reintento(monkeypatch):
    monkeypatch.setattr('app.datos.frecuento.time.sleep', lambda _: None)
    llamadas = []
    class Session:
        def get(self, url, **kwargs):
            llamadas.append(kwargs['params'])
            r = requests.Response()
            r.status_code = 429 if len(llamadas) == 1 else 200
            r.headers['Content-Type'] = 'application/json'
            r._content = json.dumps({'count': 1, 'limit': 2, 'pages': 1, 'results': [producto(1)]}).encode()
            return r
    d = FrecuentoAPI(2, 1, Session()).pagina(2)
    assert llamadas == [{'limit': 2, 'page': 2}, {'limit': 2, 'page': 2}]
    assert d['count'] == 1


def test_separacion_de_capas():
    raiz = Path(__file__).resolve().parents[1] / 'app'
    prohibidos = {'presentacion': ('app.datos', 'requests', 'pymongo'),
                  'negocio': ('app.presentacion', 'flask'),
                  'datos': ('app.negocio', 'app.presentacion', 'flask')}
    for capa, modulos in prohibidos.items():
        for archivo in (raiz / capa).rglob('*.py'):
            arbol = ast.parse(archivo.read_text(encoding='utf-8'))
            for nodo in ast.walk(arbol):
                imports = [n.name for n in nodo.names] if isinstance(nodo, ast.Import) else [nodo.module or ''] if isinstance(nodo, ast.ImportFrom) else []
                assert not any(i == m or i.startswith(m+'.') for i in imports for m in modulos), str(archivo)


def test_precio_de_variante_y_busqueda_por_palabra():
    import re
    from app.negocio.normalizacion import normalizar_producto, filtro_busqueda
    p = normalizar_producto({**producto(1, '0'), 'has_variants': True})
    assert p['precio'] is None and p['precio_por_variante']
    patron = filtro_busqueda('lavadora')[0]['busqueda']['$regex']
    assert re.search(patron, 'lavadora de carga frontal')
    assert not re.search(patron, 'clavadora neumatica')


def test_programador_ejecuta_sin_busquedas(repo):
    from datetime import datetime, timezone, timedelta
    from threading import Event
    from apscheduler.schedulers.background import BackgroundScheduler
    finalizo = Event()
    resultado = []
    worker = ServicioSincronizacion(Fuente([producto(1)]), repo)
    def tarea():
        resultado.append(worker.ejecutar('programada_prueba'))
        finalizo.set()
    planificador = BackgroundScheduler(timezone='America/Guayaquil')
    planificador.add_job(tarea, 'date', run_date=datetime.now(timezone.utc)+timedelta(milliseconds=100))
    planificador.start()
    try:
        assert finalizo.wait(5)
        assert resultado[0]['estado'] == 'completada'
        assert repo.estado()['total'] == 1
    finally:
        planificador.shutdown()
