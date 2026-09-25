"""API JSON utilizada por la tienda. No lee productos del HTML.

Verificado: GET https://app.frecuento.com/products/?limit=500&page=1.
`offset` es ignorado por la fuente; la paginación real utiliza `page`.
"""
import json
import time
from decimal import Decimal
import requests

ENDPOINT = 'https://app.frecuento.com/products/'


class ErrorFuente(RuntimeError):
    pass


class FrecuentoAPI:
    def __init__(self, page_size=500, delay=1.5, session=None):
        self.page_size = page_size
        self.delay = delay
        self.session = session or requests.Session()
        self.ultima = 0

    def pagina(self, numero):
        for intento in range(4):
            time.sleep(max(0, self.delay - (time.monotonic() - self.ultima)))
            self.ultima = time.monotonic()
            try:
                r = self.session.get(ENDPOINT, params={'limit': self.page_size, 'page': numero},
                    headers={'Accept': 'application/json', 'User-Agent': 'CatalogoAcademico/1.0'},
                    timeout=(10, 60), allow_redirects=False)
            except requests.RequestException:
                if intento == 3:
                    raise ErrorFuente('La API no respondió después de cuatro intentos.') from None
                time.sleep(2 ** intento)
                continue
            if r.status_code in {429, 500, 502, 503, 504} and intento < 3:
                espera = r.headers.get('Retry-After', '')
                if espera.isdigit() and int(espera) > 120:
                    raise ErrorFuente('La API solicita una pausa prolongada. Se conserva el catálogo anterior.')
                time.sleep(max(2 ** intento, int(espera) if espera.isdigit() else 0))
                continue
            if r.status_code != 200 or 'json' not in r.headers.get('Content-Type', ''):
                raise ErrorFuente(f'La API devolvió HTTP {r.status_code} o un formato diferente de JSON.')
            if len(r.content) > 32_000_000:
                raise ErrorFuente('La página supera el límite de tamaño.')
            try:
                d = json.loads(r.content, parse_float=Decimal)
                if not isinstance(d, dict) or not isinstance(d['results'], list):
                    raise ValueError()
                for k in ('count', 'limit', 'pages'):
                    if type(d[k]) is not int or d[k] < 0:
                        raise ValueError()
                if d['limit'] < 1 or d['limit'] > self.page_size:
                    raise ValueError()
                return d
            except (ValueError, KeyError, TypeError):
                raise ErrorFuente('El contrato JSON del catálogo cambió.') from None
        raise ErrorFuente('No se pudo obtener la página.')
