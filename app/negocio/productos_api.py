"""Mapeo de contratos externos al documento común de Miau."""
from decimal import Decimal
from html import unescape
from urllib.parse import quote
from app.negocio.normalizacion import dinero, normalizar_texto, texto_descripcion, url_http


def normalizar_api(p, fuente, tipo, base):
    variantes, imagenes, categorias = [], [], []
    marca, descripcion, codigo, enlace = '', '', '', None
    precio, disponible = None, None
    if tipo == 'vtex':
        identificador, nombre = p['productId'], p['productName']
        marca, descripcion = p.get('brand', ''), p.get('description', '')
        codigo, enlace = p.get('productReference', ''), p.get('link')
        categorias = p.get('categories', [])
        for sku in p.get('items', []):
            imagenes.extend(i.get('imageUrl') for i in sku.get('images', []))
            for vendedor in sku.get('sellers', []):
                oferta = vendedor.get('commertialOffer', {})
                precio_sku = dinero(oferta.get('Price'))
                variantes.append({'id': str(sku['itemId']), 'nombre': sku.get('name'),
                    'ean': sku.get('ean'), 'vendedor': vendedor.get('sellerName'),
                    'precio': precio_sku if precio_sku and precio_sku > 0 else None,
                    'disponible': oferta.get('AvailableQuantity', 0) > 0})
    elif tipo == 'shopify':
        identificador, nombre = p['id'], p['title']
        # vendor es el proveedor publicado por Shopify, no siempre una marca fabricante.
        descripcion = p.get('body_html', '')
        categorias = [p['product_type']] if p.get('product_type') else []
        imagenes = [i.get('src') for i in p.get('images', [])]
        enlace = base + '/products/' + quote(p['handle'], safe='-')
        for v in p.get('variants', []):
            variantes.append({'id': str(v['id']), 'nombre': v.get('title'), 'codigo': v.get('sku'),
                              'precio': dinero(v.get('price')), 'disponible': v.get('available')})
        codigo = next((v['codigo'] for v in variantes if v.get('codigo')), '')
    elif tipo == 'woo':
        identificador, nombre = p['id'], p['name']
        precios = p['prices']
        if precios.get('currency_code') != 'USD':
            raise ValueError('Precio WooCommerce fuera de USD.')
        minor = precios['currency_minor_unit']
        if type(minor) is not int or not 0 <= minor <= 4:
            raise ValueError('Unidad monetaria no válida.')
        bruto = dinero(precios.get('price'))
        precio = bruto / (Decimal(10) ** minor) if bruto is not None else None
        codigo, enlace = p.get('sku', ''), p.get('permalink')
        descripcion = p.get('description') or p.get('short_description', '')
        categorias = [c['name'] for c in p.get('categories', [])]
        imagenes = [i.get('src') for i in p.get('images', [])]
        disponible = p.get('is_in_stock')
    elif tipo == 'magento':
        identificador, nombre = p['sku'], p['name']
        oferta = p['price_range']['minimum_price']['final_price']
        if oferta.get('currency') != 'USD':
            raise ValueError('Precio GraphQL fuera de USD.')
        precio, codigo = dinero(oferta.get('value')), p['sku']
        descripcion = (p.get('description') or {}).get('html', '')
        categorias = [c['name'] for c in p.get('categories', [])]
        imagenes = [(p.get('image') or {}).get('url')]
        if p.get('url_key'):
            enlace = base + '/' + quote(p['url_key'] + (p.get('url_suffix') or ''), safe='-/')
        disponible = {'IN_STOCK': True, 'OUT_OF_STOCK': False}.get(p.get('stock_status'))
    else:
        raise ValueError('Conector no reconocido.')
    if variantes:
        for variante in variantes:
            if variante.get('precio') is not None and variante['precio'] <= 0:
                variante['precio'] = None
        disponibles = [v for v in variantes if v.get('disponible') is True]
        importes = [v['precio'] for v in (disponibles or variantes) if v.get('precio') is not None]
        precio = min(importes) if importes else None
        disponible = any(v.get('disponible') is True for v in variantes)
    if precio is not None and precio <= 0:
        precio = None
    # Los títulos son texto, no HTML: HTMLParser pierde algunos nombres con &.
    nombre = unescape(str(nombre or '')).strip()
    if not identificador or not nombre:
        raise ValueError('Producto sin identidad o nombre.')
    return {'fuente': fuente, 'id_externo': str(identificador), 'nombre': nombre,
            'marca': marca, 'codigo': codigo or '', 'categorias': categorias,
            'precio': precio, 'precio_ausente': precio is None, 'moneda': 'USD',
            'precio_por_variante': len(variantes) > 1, 'variantes': variantes,
            'disponible': disponible, 'descripcion': texto_descripcion(descripcion),
            'imagenes': list(dict.fromkeys(u for i in imagenes if (u := url_http(i)))),
            'url_origen': url_http(enlace), 'original': p,
            'busqueda': normalizar_texto(' '.join([nombre, marca, codigo or '', *categorias]))}
