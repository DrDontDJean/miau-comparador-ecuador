"""Conectores HTTP de catálogos públicos. Nunca se invocan desde las búsquedas."""
import json
import time
import logging
from decimal import Decimal
from math import ceil
import requests
from app.datos.frecuento import ErrorFuente


FUENTES = {
    'novicompu': ('vtex', 'https://www.novicompu.com'),
    'crecos': ('vtex', 'https://www.crecos.com'),
    'comandato': ('vtex', 'https://www.comandato.com'),
    'marcimex': ('vtex', 'https://www.marcimex.com'),
    'pycca': ('vtex', 'https://www.pycca.com'),
    'japon': ('vtex', 'https://www.almacenesjapon.com'),
    'kywi': ('vtex', 'https://www.kywi.com.ec'),
    'computron': ('woo', 'https://www.computron.com.ec'),
    'colineal': ('shopify', 'https://colineal.com'),
    'newstore': ('shopify', 'https://www.newstoregye.com'),
    'ekustore': ('shopify', 'https://ekustore.com'),
    'smarthomeec': ('shopify', 'https://smarthomeecstore.com'),
    'randalltech': ('shopify', 'https://randall-tech.com'),
    'steren': ('magento', 'https://www.steren.com.ec'),
    'pintulac': ('magento', 'https://www.pintulac.com.ec'),
    'laganga': ('magento', 'https://laganga.com'),
}


class CatalogoAPI:
    def __init__(self, fuente, delay=1.5, session=None):
        self.fuente = fuente
        self.tipo, self.base = FUENTES[fuente]
        self.session = session or requests.Session()
        self.delay, self.ultima = delay, 0
        self.total = None
        self.moneda = 'USD'

    def get(self, ruta, params=None):
        for intento in range(3):
            time.sleep(max(0, self.delay - (time.monotonic() - self.ultima)))
            self.ultima = time.monotonic()
            try:
                r = self.session.get(self.base + ruta, params=params, timeout=(10, 45),
                    headers={'Accept': 'application/json', 'User-Agent': 'MiauCatalogo/1.0'}, allow_redirects=False)
            except requests.RequestException:
                if intento == 2:
                    raise ErrorFuente('Tiempo de espera agotado en la API.') from None
                time.sleep(2 ** intento)
                continue
            if r.status_code in (429, 500, 502, 503, 504) and intento < 2:
                espera = r.headers.get('Retry-After', '0')
                if not espera.isdigit() or int(espera) > 120:
                    raise ErrorFuente('La API solicita posponer la actualización.')
                time.sleep(max(int(espera), 2 ** intento))
                continue
            contenido = r.headers.get('Content-Type', '')
            if r.status_code not in (200, 206) or not ('json' in contenido or (ruta == '/cart.js' and 'javascript' in contenido)):
                logging.getLogger(__name__).warning('%s HTTP %s en %s params=%s', self.fuente, r.status_code, ruta, params)
                raise ErrorFuente(f'API no disponible: HTTP {r.status_code} o respuesta no JSON.')
            if len(r.content) > 32_000_000:
                raise ErrorFuente('Página demasiado grande.')
            try:
                return json.loads(r.content, parse_float=Decimal), r.headers
            except ValueError:
                raise ErrorFuente('JSON de API inválido.') from None
        raise ErrorFuente('No se pudo consultar la API.')

    def lotes(self):
        yield from getattr(self, self.tipo)()

    def woo(self):
        pagina, limite = 1, 100
        while True:
            filas, headers = self.get('/wp-json/wc/store/v1/products',
                                      {'per_page': limite, 'page': pagina, 'orderby': 'id', 'order': 'asc'})
            total = int(headers['X-WP-Total'])
            if self.total is None:
                self.total = total
            if total != self.total or not isinstance(filas, list):
                raise ValueError('El catálogo cambió durante la descarga.')
            if len(filas) != min(limite, total-(pagina-1)*limite):
                raise ValueError('Página WooCommerce incompleta.')
            yield filas
            if pagina >= ceil(total/limite):
                break
            pagina += 1

    def shopify(self):
        carrito, _ = self.get('/cart.js')
        self.moneda = carrito.get('currency')
        if self.moneda != 'USD':
            raise ValueError('La tienda no devolvió moneda USD.')
        # El listado público no declara total. Se recorre hasta una página vacía.
        for pagina in range(1, 1001):
            respuesta, _ = self.get('/products.json', {'limit': 250, 'page': pagina})
            filas = respuesta.get('products')
            if not isinstance(filas, list):
                raise ValueError('Contrato Shopify inválido.')
            if not filas:
                return
            yield filas
        raise ValueError('Se alcanzó el límite de páginas sin finalizar el catálogo.')

    def magento(self):
        pagina, limite = 1, 100
        while True:
            query = '''{products(search:"",pageSize:%d,currentPage:%d,sort:{name:ASC}){
              total_count items{sku name url_key url_suffix description{html}
              price_range{minimum_price{final_price{value currency}}}
              image{url} stock_status categories{name}}}}''' % (limite, pagina)
            respuesta, _ = self.get('/graphql', {'query': query})
            if respuesta.get('errors'):
                raise ValueError('GraphQL rechazó el contrato de productos: ' +
                                 str(respuesta['errors'][0].get('message', ''))[:200])
            datos = respuesta['data']['products']
            total, filas = datos['total_count'], datos['items']
            if self.total is None:
                self.total = total
            if total != self.total or len(filas) != min(limite, total-(pagina-1)*limite):
                raise ValueError('Página GraphQL incompleta o catálogo modificado.')
            yield filas
            if pagina >= ceil(total/limite):
                return
            pagina += 1

    def vtex_buscar(self, inicio=0, filtros=None, fin=None, orden='OrderByNameASC'):
        params = {'_from': inicio, '_to': fin if fin is not None else inicio+49, 'O': orden}
        if filtros:
            params['fq'] = filtros
        try:
            filas, headers = self.get('/api/catalog_system/pub/products/search', params)
        except ErrorFuente as error:
            # Algunas tiendas fallan al construir respuestas grandes. Reintentar
            # el mismo intervalo en bloques menores, sin omitir productos.
            if 'HTTP 500' not in str(error) or params['_to'] <= inicio:
                raise
            filas, total = [], None
            ancho = 10 if params['_to'] - inicio >= 10 else 1
            for offset in range(inicio, params['_to'] + 1, ancho):
                bloque, declarado = self.vtex_buscar(offset, filtros, min(offset + ancho - 1, params['_to']), orden)
                if total is not None and declarado != total:
                    raise ValueError('El catálogo VTEX cambió durante la descarga.')
                total = declarado
                filas.extend(bloque)
                if offset + ancho >= total:
                    break
            return filas, total
        if not isinstance(filas, list):
            raise ValueError('Contrato VTEX inválido.')
        rango = headers.get('resources') or headers.get('Content-Range')
        if not rango or '/' not in rango:
            if not filas:
                return filas, 0
            raise ValueError('VTEX no declaró el total del catálogo.')
        return filas, int(rango.rsplit('/', 1)[1])

    def vtex(self):
        primera, self.total = self.vtex_buscar()
        def recorrer(filtros, nodos, inicial=None):
            filas, total = inicial if inicial else self.vtex_buscar(filtros=filtros)
            if total > 2500:
                if not nodos:
                    raise ValueError('Una categoría supera el límite público VTEX; se necesita partición adicional.')
                for nodo in nodos:
                    ruta = (filtros or 'C:/') + str(nodo['id']) + '/'
                    yield from recorrer(ruta, nodo.get('children', []))
                return
            for inicio in range(0, total, 50):
                lote, actual = (filas, total) if inicio == 0 else self.vtex_buscar(inicio, filtros, min(inicio+49, total-1))
                if actual != total or len(lote) != min(50, total-inicio):
                    raise ValueError('Página VTEX incompleta o catálogo modificado.')
                yield lote
        nodos = []
        if self.total > 2500:
            nodos, _ = self.get('/api/catalog_system/pub/category/tree/10')
        vistos = set()
        for lote in recorrer(None, nodos, (primera, self.total)):
            vistos.update(str(p['productId']) for p in lote)
            yield lote
        # Complementa productos asociados al nivel padre o ausentes del árbol.
        # Solo se publica si el número de IDs únicos coincide con el total global.
        if self.total > 2500:
            for orden in ('OrderByNameASC', 'OrderByNameDESC'):
                for inicio in range(0, min(self.total, 2500), 50):
                    if len(vistos) == self.total:
                        break
                    filas, actual = self.vtex_buscar(inicio, orden=orden)
                    if actual != self.total:
                        raise ValueError('El catálogo VTEX cambió durante la descarga.')
                    vistos.update(str(p['productId']) for p in filas)
                    yield filas
        _, final = self.vtex_buscar()
        if final != self.total:
            raise ValueError('El total VTEX cambió durante la descarga.')
