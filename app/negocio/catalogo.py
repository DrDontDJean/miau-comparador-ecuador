from math import ceil
from app.negocio.normalizacion import filtro_busqueda, dinero
from app.negocio.tiendas import TIENDAS, obtener_tienda


class ServicioCatalogo:
    """Solo lee el repositorio: este servicio no recibe un cliente HTTP."""
    def __init__(self, repositorio):
        self.repo = repositorio

    def buscar(self, q='', pagina=1, orden='precio_asc', disponible=False,
               tienda='', precio_min='', precio_max=''):
        q = str(q).strip()
        if len(q) > 120 or orden not in {'precio_asc', 'precio_desc', 'nombre'}:
            raise ValueError('Búsqueda u orden inválidos.')
        try:
            pagina = int(pagina)
        except (ValueError, TypeError):
            raise ValueError('Página inválida.') from None
        if not 1 <= pagina <= 100000:
            raise ValueError('Página inválida.')
        if tienda and not obtener_tienda(tienda):
            raise ValueError('Tienda no válida.')
        minimo, maximo = dinero(precio_min), dinero(precio_max)
        if minimo is not None and maximo is not None and minimo > maximo:
            raise ValueError('El precio mínimo no puede superar al máximo.')
        filtros = filtro_busqueda(q)
        if tienda:
            filtros.append({'fuente': tienda})
        rango = {}
        if minimo is not None:
            rango['$gte'] = minimo
        if maximo is not None:
            rango['$lte'] = maximo
        if rango:
            filtros.append({'precio': rango})
        filas, total, estado = self.repo.buscar(filtros, pagina, 24, orden, disponible)
        for p in filas:
            p['tienda_nombre'] = (obtener_tienda(p.get('fuente')) or {}).get('nombre', p.get('fuente', ''))
        return {'productos': filas, 'total': total, 'pagina': pagina, 'paginas': ceil(total / 24),
                'q': q, 'orden': orden, 'disponible': disponible, 'estado': estado,
                'tienda': tienda, 'precio_min': str(minimo) if minimo is not None else '',
                'precio_max': str(maximo) if maximo is not None else '', 'tiendas': self.tiendas()}

    def tiendas(self):
        cantidades = self.repo.contar_tiendas()
        estados = self.repo.estados_tiendas()
        return [{**t, 'total': cantidades.get(t['id'], 0),
                 'incorporada': t['id'] in cantidades,
                 'estado_sync': estados.get(t['id'], {}).get('estado_sync', 'pendiente'),
                 'actualizado_en': estados.get(t['id'], {}).get('actualizado_en'),
                 'mensaje_sync': estados.get(t['id'], {}).get('mensaje_sync', '')} for t in TIENDAS]

    def tienda(self, identificador):
        return next((t for t in self.tiendas() if t['id'] == identificador), None)

    def estado(self):
        return self.repo.estado()

    def obtener(self, identificador, fuente='frecuento'):
        if not obtener_tienda(fuente) or not identificador or len(str(identificador)) > 200:
            return None
        producto = self.repo.obtener_fuente(str(identificador), fuente)
        if producto:
            producto['tienda_nombre'] = obtener_tienda(fuente)['nombre']
        return producto
