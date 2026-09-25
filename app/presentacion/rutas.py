from datetime import timezone
from zoneinfo import ZoneInfo
from flask import Blueprint, current_app, render_template, request, jsonify, abort, redirect, url_for

web = Blueprint('web', __name__)


def servicio():
    return current_app.extensions['catalogo']


@web.app_template_filter('fecha')
def fecha(valor):
    if not valor:
        return 'Sin actualización completa'
    return valor.replace(tzinfo=valor.tzinfo or timezone.utc).astimezone(ZoneInfo('America/Guayaquil')).strftime('%d/%m/%Y · %H:%M')


@web.get('/')
@web.get('/tiendas')
def inicio():
    return redirect(url_for('web.productos'))


def parametros(tienda=None):
    return dict(q=request.args.get('q', ''), pagina=request.args.get('pagina', 1),
                orden=request.args.get('orden', 'precio_asc'), disponible=request.args.get('disponible') == '1',
                tienda=tienda if tienda is not None else request.args.get('tienda', ''),
                precio_min=request.args.get('precio_min', ''), precio_max=request.args.get('precio_max', ''))


@web.get('/productos')
def productos():
    return mostrar_catalogo()


@web.get('/tiendas/<tienda_id>')
def tienda(tienda_id):
    seleccionada = servicio().tienda(tienda_id)
    if seleccionada is None:
        abort(404)
    return mostrar_catalogo(seleccionada)


def mostrar_catalogo(seleccionada=None):
    try:
        datos = servicio().buscar(**parametros(seleccionada['id'] if seleccionada else None))
    except ValueError as e:
        return render_template('error.html', mensaje=str(e)), 400
    def enlace_pagina(numero):
        from flask import url_for
        args = dict(q=datos['q'], pagina=numero, orden=datos['orden'],
                    disponible='1' if datos['disponible'] else '',
                    precio_min=datos['precio_min'], precio_max=datos['precio_max'])
        if seleccionada:
            return url_for('web.tienda', tienda_id=seleccionada['id'], **args)
        return url_for('web.productos', tienda=datos['tienda'], **args)
    return render_template('catalogo.html', seleccionada=seleccionada,
                           enlace_pagina=enlace_pagina, **datos)


@web.get('/productos/<identificador>')
def detalle(identificador):
    producto = servicio().obtener(identificador)
    if producto is None:
        abort(404)
    return render_template('detalle.html', p=producto)


@web.get('/tiendas/<tienda_id>/productos/<path:identificador>')
def detalle_tienda(tienda_id, identificador):
    producto = servicio().obtener(identificador, tienda_id)
    if producto is None:
        abort(404)
    return render_template('detalle.html', p=producto)


@web.get('/api/productos')
def api_productos():
    try:
        return jsonify(servicio().buscar(**parametros()))
    except ValueError as e:
        return jsonify(error=str(e)), 400


@web.get('/api/estado')
def api_estado():
    return jsonify(servicio().estado())


@web.get('/salud')
def salud():
    servicio().estado()
    return jsonify(aplicacion='frecuento-etapa1', estado='disponible')
