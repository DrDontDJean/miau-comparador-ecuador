"""Directorio de fuentes comprobadas. Registrar una tienda no importa su catálogo."""
TIENDAS = [
    {'id': identificador, 'nombre': nombre}
    for identificador, nombre in [
        ('frecuento', 'Frecuento'), ('novicompu', 'Novicompu'),
        ('computron', 'Computron'), ('crecos', 'Créditos Económicos'),
        ('comandato', 'Comandato'), ('marcimex', 'Marcimex'), ('pycca', 'Pycca'),
        ('japon', 'Almacenes Japón'), ('kywi', 'Kywi'), ('colineal', 'Colineal'),
        ('newstore', 'NewStore'), ('ekustore', 'EkuStore'),
        ('smarthomeec', 'Smart Home EC'), ('randalltech', 'Randall Tech'),
        ('steren', 'Steren Ecuador'), ('pintulac', 'Pintulac'), ('laganga', 'La Ganga'),
    ]
]


def obtener_tienda(identificador):
    return next((t for t in TIENDAS if t['id'] == identificador), None)
