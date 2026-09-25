"""Funciones reutilizables: identidad, texto y precios del catálogo."""
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import urlsplit


def normalizar_texto(valor):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(valor or '').casefold())
                            if not unicodedata.combining(c)).split())


class TextoHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []

    def handle_data(self, data):
        self.partes.append(data)


def texto_descripcion(valor):
    parser = TextoHTML()
    parser.feed(str(valor or ''))
    parser.close()
    return ' '.join(' '.join(parser.partes).split())


def dinero(valor):
    if valor is None or valor == '':
        return None
    try:
        if isinstance(valor, bool):
            raise ValueError()
        d = Decimal(str(valor))
        if not d.is_finite() or d < 0:
            raise ValueError()
        return d
    except (InvalidOperation, ValueError):
        raise ValueError('Precio de producto inválido.') from None


def url_http(valor):
    if not isinstance(valor, str):
        return None
    u = urlsplit(valor)
    return valor if u.scheme in {'https', 'http'} and u.hostname and not u.username else None


def normalizar_producto(p):
    if not isinstance(p, dict) or type(p.get('id')) is not int or not str(p.get('name') or '').strip():
        raise ValueError('Producto sin identidad o nombre.')
    precio = dinero(p.get('amount_total'))
    precio_por_variante = bool(p.get('has_variants')) and precio == 0
    if precio_por_variante:
        precio = None
    categorias = [str(c['name']) for c in p.get('categories', []) if isinstance(c, dict) and c.get('name')]
    marca = str(p.get('brand') or '').strip()
    if marca.lower() == 'x':
        marca = ''
    nombre = str(p['name']).strip()
    codigo = str(p.get('code') or '')
    # El endpoint público no publica moneda: USD se configura por el mercado de esta fuente.
    return {'fuente': 'frecuento', 'id_externo': str(p['id']), 'nombre': nombre,
            'codigo': codigo, 'marca': marca, 'categorias': categorias,
            'precio': precio, 'precio_ausente': precio is None, 'moneda': 'USD',
            'precio_por_variante': precio_por_variante,
            'precio_antes_descuento': dinero(p.get('amount_incl_tax')),
            'disponible': p.get('has_stock') if isinstance(p.get('has_stock'), bool) else None,
            'existencias': p.get('stock'), 'descripcion': texto_descripcion(p.get('description')),
            'imagenes': [u for i in p.get('photos', []) if (u := url_http(i))],
            'url_origen': url_http(p.get('url')), 'variantes': p.get('variants') or [],
            'busqueda': normalizar_texto(' '.join([nombre, codigo, marca, *categorias])),
            'original': p}


def filtro_busqueda(consulta):
    return [{'busqueda': {'$regex': r'\b' + re.escape(palabra)}} for palabra in normalizar_texto(consulta).split()]
