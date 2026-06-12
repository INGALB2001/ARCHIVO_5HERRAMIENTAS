import os, sys, io, tempfile, base64, sqlite3, json, html, re
from datetime import datetime
from flask import Flask, send_from_directory, request, send_file, jsonify, session

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from generar_pdf import generar
from generar_remision import generar_remision

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'eshen_secret_2024')
ADMIN_PASS = os.environ.get('ADMIN_PASS', '247096')
DB = os.path.join(BASE, 'ordenes.db')


# =========================
# HELPERS PDF
# =========================

def safe_text(value):
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def safe_float(value, default=0):
    try:
        if value is None or value == "":
            return default
        value = str(value)
        value = value.replace("$", "")
        value = value.replace(",", "")
        value = value.replace("MXN", "")
        value = value.replace("mxn", "")
        value = value.strip()
        return float(value)
    except:
        return default


def limpiar_data_cotizacion(data):
    if not isinstance(data, dict):
        data = {}

    cliente = data.get("cliente", {})
    if not isinstance(cliente, dict):
        cliente = {}

    condiciones_pago = data.get("condiciones_pago", ["", "", ""])
    if isinstance(condiciones_pago, str):
        condiciones_pago = [condiciones_pago, "", ""]
    if not isinstance(condiciones_pago, list):
        condiciones_pago = ["", "", ""]
    while len(condiciones_pago) < 3:
        condiciones_pago.append("")

    partidas_limpias = []
    partidas = data.get("partidas", [])

    if not isinstance(partidas, list) or len(partidas) == 0:
        partidas = [{
            "numero": "1",
            "cantidad": 1,
            "sku": "",
            "concepto": data.get("concepto", "Servicio industrial"),
            "precio_unitario": data.get("precio_unitario", 0)
        }]

    contador = 1

    for item in partidas:
        if not isinstance(item, dict):
            continue

        if item.get("tipo") == "grupo":
            partidas_limpias.append({
                "tipo": "grupo",
                "titulo": safe_text(item.get("titulo", ""))
            })
        else:
            cantidad = safe_float(item.get("cantidad", 1), 1)
            precio = safe_float(item.get("precio_unitario", 0), 0)

            partidas_limpias.append({
                "tipo": "partida",
                "numero": safe_text(item.get("numero", contador)),
                "cantidad": cantidad,
                "sku": safe_text(item.get("sku", "")),
                "concepto": safe_text(item.get("concepto", "")),
                "precio_unitario": precio
            })

            contador += 1

    data_limpia = {
        "rfc_emisor": safe_text(data.get("rfc_emisor", "")),
        "email_emisor": safe_text(data.get("email_emisor", "")),
        "proveedor": safe_text(data.get("proveedor", "MAF Automation")),
        "fecha": safe_text(data.get("fecha", datetime.now().strftime("%d/%m/%Y"))),
        "numero_cotizacion": safe_text(data.get("numero_cotizacion", "001")),

        "cliente": {
            "razon_social": safe_text(cliente.get("razon_social", "")),
            "rfc": safe_text(cliente.get("rfc", "")),
            "direccion": safe_text(cliente.get("direccion", "")),
            "correo": safe_text(cliente.get("correo", "")),
            "atencion": safe_text(cliente.get("atencion", ""))
        },

        "vigencia": safe_text(data.get("vigencia", "30 días")),

        "condiciones_pago": [
            safe_text(condiciones_pago[0]),
            safe_text(condiciones_pago[1]),
            safe_text(condiciones_pago[2])
        ],

        "partidas": partidas_limpias,

        "nota": safe_text(data.get("nota", "")),
        "firma_nombre": safe_text(data.get("firma_nombre", "Ing. Alberto López Malváez")),
        "firma_cargo": safe_text(data.get("firma_cargo", "DIRECTOR GENERAL")),
        "iva_porciento": safe_float(data.get("iva_porciento", 16), 16)
    }

    return data_limpia


# =========================
# DB
# =========================

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS ot_trabajadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            activo INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS ot_ordenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE NOT NULL,
            solicitante TEXT,
            asignado_id INTEGER,
            asignado_nombre TEXT,
            area TEXT,
            fecha_hora TEXT,
            codigo_equipo TEXT,
            descripcion_servicio TEXT,
            trabajos_efectuados TEXT,
            observaciones TEXT,
            estado TEXT DEFAULT 'pendiente',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ot_refacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orden_id INTEGER NOT NULL,
            cantidad TEXT,
            unidad TEXT,
            descripcion TEXT,
            serie_no_parte TEXT,
            tipo TEXT DEFAULT 'nuevo'
        );
    ''')

    cur = conn.execute('SELECT COUNT(*) FROM ot_trabajadores')
    if cur.fetchone()[0] == 0:
        for w in ['Alberto Lopez', 'Trabajador 2', 'Trabajador 3', 'Trabajador 4', 'Trabajador 5']:
            conn.execute('INSERT INTO ot_trabajadores (nombre) VALUES (?)', (w,))

    conn.commit()
    conn.close()


def next_folio():
    conn = get_db()
    cur = conn.execute(
        "SELECT MAX(CAST(SUBSTR(folio,3) AS INTEGER)) FROM ot_ordenes WHERE folio LIKE 'OT%'"
    )
    n = (cur.fetchone()[0] or 0) + 1
    conn.close()
    return f'OT{n:04d}'


init_db()


# =========================
# PAGES
# =========================

@app.route('/')
def home():
    return send_from_directory(BASE, 'panel.html')


@app.route('/laser')
def laser():
    return send_from_directory(BASE, 'laser.html')


@app.route('/cotizador')
def cotizador_page():
    return send_from_directory(BASE, 'cotizador.html')


@app.route('/remision')
def remision_page():
    return send_from_directory(BASE, 'remision.html')


@app.route('/ordenes')
def ordenes_page():
    return send_from_directory(BASE, 'ordenes.html')


# =========================
# PDF COTIZACION
# =========================

@app.route('/generar', methods=['POST'])
@app.route('/generar_pdf', methods=['POST'])
@app.route('/generar-pdf', methods=['POST'])
def gen_pdf():
    path = None

    try:
        if request.is_json:
            data = request.get_json(force=True)
        else:
            data = {
                "rfc_emisor": request.form.get("rfc_emisor", ""),
                "email_emisor": request.form.get("email_emisor", ""),
                "proveedor": request.form.get("proveedor", "MAF Automation"),
                "fecha": request.form.get("fecha", datetime.now().strftime("%d/%m/%Y")),
                "numero_cotizacion": request.form.get("numero_cotizacion", "001"),

                "cliente": {
                    "razon_social": request.form.get("razon_social", ""),
                    "rfc": request.form.get("rfc", ""),
                    "direccion": request.form.get("direccion", ""),
                    "correo": request.form.get("correo", ""),
                    "atencion": request.form.get("atencion", "")
                },

                "vigencia": request.form.get("vigencia", "30 días"),

                "condiciones_pago": [
                    request.form.get("condicion_pago_1", "50% anticipo"),
                    request.form.get("condicion_pago_2", "50% contra entrega"),
                    request.form.get("condicion_pago_3", "")
                ],

                "partidas": [
                    {
                        "numero": request.form.get("numero", "1"),
                        "cantidad": request.form.get("cantidad", "1"),
                        "sku": request.form.get("sku", ""),
                        "concepto": request.form.get("concepto", ""),
                        "precio_unitario": request.form.get("precio_unitario", "0")
                    }
                ],

                "nota": request.form.get("nota", ""),
                "firma_nombre": request.form.get("firma_nombre", "Ing. Alberto López Malváez"),
                "firma_cargo": request.form.get("firma_cargo", "DIRECTOR GENERAL"),
                "iva_porciento": request.form.get("iva_porciento", 16)
            }

        data = limpiar_data_cotizacion(data)

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            path = tmp.name

        generar(data, path)

        with open(path, 'rb') as f:
            buf = io.BytesIO(f.read())

        buf.seek(0)

        if path and os.path.exists(path):
            os.unlink(path)

        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='COT_{}.pdf'.format(data.get('numero_cotizacion', 'ESHEN'))
        )

    except Exception as e:
        print("ERROR GENERANDO PDF:", repr(e))

        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except:
                pass

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# =========================
# PDF REMISION
# =========================

@app.route('/generar-remision', methods=['POST'])
@app.route('/generar_remision', methods=['POST'])
def gen_remision():
    data = request.get_json(force=True)
    sello_path = None
    evidencia_path = None
    temps = []

    def save_b64(b64_str, mime):
        ext = '.jpg' if 'jpeg' in mime or 'jpg' in mime else '.png'
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as t:
            t.write(base64.b64decode(b64_str))
            return t.name

    if data.get('sello_b64'):
        sello_path = save_b64(data['sello_b64'], data.get('sello_mime', 'image/jpeg'))
        temps.append(sello_path)

    if data.get('evidencia_b64'):
        evidencia_path = save_b64(data['evidencia_b64'], data.get('evidencia_mime', 'image/jpeg'))
        temps.append(evidencia_path)

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        out_path = tmp.name

    temps.append(out_path)

    try:
        generar_remision(data, out_path, sello_path=sello_path, evidencia_path=evidencia_path)

        with open(out_path, 'rb') as f:
            buf = io.BytesIO(f.read())

        buf.seek(0)

        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='REM_{}.pdf'.format(data.get('numero_remision', 'ESHEN'))
        )

    finally:
        for p in temps:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except:
                    pass


# =========================
# ORDENES API
# =========================

@app.route('/api/ot/trabajadores', methods=['GET'])
def ot_get_trabajadores():
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM ot_trabajadores WHERE activo=1 ORDER BY nombre'
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/ot/trabajadores', methods=['POST'])
def ot_add_trabajador():
    data = request.get_json()
    conn = get_db()
    conn.execute(
        'INSERT INTO ot_trabajadores (nombre) VALUES (?)',
        (data['nombre'],)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/ot/trabajadores/<int:tid>', methods=['DELETE'])
def ot_del_trabajador(tid):
    conn = get_db()
    conn.execute(
        'UPDATE ot_trabajadores SET activo=0 WHERE id=?',
        (tid,)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/ot/ordenes', methods=['GET'])
def ot_get_ordenes():
    conn = get_db()

    sql = '''
        SELECT o.*, t.nombre as asignado_nombre
        FROM ot_ordenes o
        LEFT JOIN ot_trabajadores t ON o.asignado_id = t.id
        WHERE 1=1
    '''
    params = []

    if request.args.get('asignado'):
        sql += ' AND o.asignado_id=?'
        params.append(request.args['asignado'])

    if request.args.get('estado'):
        sql += ' AND o.estado=?'
        params.append(request.args['estado'])

    sql += ' ORDER BY o.id DESC'

    rows = conn.execute(sql, params).fetchall()
    result = []

    for r in rows:
        d = dict(r)
        refs = conn.execute(
            'SELECT * FROM ot_refacciones WHERE orden_id=?',
            (r['id'],)
        ).fetchall()
        d['refacciones'] = [dict(ref) for ref in refs]
        result.append(d)

    conn.close()
    return jsonify(result)


@app.route('/api/ot/ordenes', methods=['POST'])
def ot_create_orden():
    data = request.get_json()
    folio = next_folio()
    now = datetime.now().strftime('%d/%m/%Y %H:%M')

    conn = get_db()
    cur = conn.execute('''
        INSERT INTO ot_ordenes
        (
            folio,
            solicitante,
            asignado_id,
            asignado_nombre,
            area,
            fecha_hora,
            codigo_equipo,
            descripcion_servicio,
            trabajos_efectuados,
            observaciones,
            estado
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        folio,
        data.get('solicitante', ''),
        None,
        data.get('asignado_nombre', ''),
        data.get('area', ''),
        data.get('fecha_hora', now),
        data.get('codigo_equipo', ''),
        data.get('descripcion_servicio', ''),
        data.get('trabajos_efectuados', ''),
        data.get('observaciones', ''),
        data.get('estado', 'pendiente')
    ))

    oid = cur.lastrowid

    for ref in data.get('refacciones', []):
        if ref.get('descripcion'):
            conn.execute('''
                INSERT INTO ot_refacciones
                (
                    orden_id,
                    cantidad,
                    unidad,
                    descripcion,
                    serie_no_parte,
                    tipo
                )
                VALUES (?,?,?,?,?,?)
            ''', (
                oid,
                ref.get('cantidad', ''),
                ref.get('unidad', ''),
                ref.get('descripcion', ''),
                ref.get('serie_no_parte', ''),
                ref.get('tipo', 'nuevo')
            ))

    conn.commit()
    conn.close()

    return jsonify({'ok': True, 'folio': folio, 'id': oid})


@app.route('/api/ot/ordenes/<int:oid>', methods=['PUT'])
def ot_update_orden(oid):
    data = request.get_json()
    now = datetime.now().strftime('%d/%m/%Y %H:%M')

    conn = get_db()

    conn.execute('''
        UPDATE ot_ordenes
        SET solicitante=?,
            asignado_nombre=?,
            area=?,
            codigo_equipo=?,
            descripcion_servicio=?,
            trabajos_efectuados=?,
            observaciones=?,
            estado=?,
            updated_at=?
        WHERE id=?
    ''', (
        data.get('solicitante', ''),
        data.get('asignado_nombre', ''),
        data.get('area', ''),
        data.get('codigo_equipo', ''),
        data.get('descripcion_servicio', ''),
        data.get('trabajos_efectuados', ''),
        data.get('observaciones', ''),
        data.get('estado', 'pendiente'),
        now,
        oid
    ))

    conn.execute('DELETE FROM ot_refacciones WHERE orden_id=?', (oid,))

    for ref in data.get('refacciones', []):
        if ref.get('descripcion'):
            conn.execute('''
                INSERT INTO ot_refacciones
                (
                    orden_id,
                    cantidad,
                    unidad,
                    descripcion,
                    serie_no_parte,
                    tipo
                )
                VALUES (?,?,?,?,?,?)
            ''', (
                oid,
                ref.get('cantidad', ''),
                ref.get('unidad', ''),
                ref.get('descripcion', ''),
                ref.get('serie_no_parte', ''),
                ref.get('tipo', 'nuevo')
            ))

    conn.commit()
    conn.close()

    return jsonify({'ok': True})


@app.route('/api/ot/ordenes/<int:oid>/estado', methods=['PATCH'])
def ot_update_estado(oid):
    data = request.get_json()
    now = datetime.now().strftime('%d/%m/%Y %H:%M')

    conn = get_db()
    conn.execute(
        'UPDATE ot_ordenes SET estado=?, updated_at=? WHERE id=?',
        (data['estado'], now, oid)
    )
    conn.commit()
    conn.close()

    return jsonify({'ok': True})


@app.route('/api/ot/ordenes/<int:oid>', methods=['DELETE'])
def ot_delete_orden(oid):
    conn = get_db()
    conn.execute('DELETE FROM ot_refacciones WHERE orden_id=?', (oid,))
    conn.execute('DELETE FROM ot_ordenes WHERE id=?', (oid,))
    conn.commit()
    conn.close()

    return jsonify({'ok': True})


@app.route('/api/ot/ordenes/<int:oid>/pdf', methods=['GET'])
def ot_pdf(oid):
    import sys
    sys.path.insert(0, BASE)

    from generar_ot import generar_ot_pdf

    conn = get_db()

    r = conn.execute('''
        SELECT o.*, t.nombre as asignado_nombre
        FROM ot_ordenes o
        LEFT JOIN ot_trabajadores t ON o.asignado_id = t.id
        WHERE o.id=?
    ''', (oid,)).fetchone()

    if not r:
        conn.close()
        return jsonify({'error': 'not found'}), 404

    d = dict(r)

    refs = conn.execute(
        'SELECT * FROM ot_refacciones WHERE orden_id=?',
        (oid,)
    ).fetchall()

    d['refacciones'] = [dict(ref) for ref in refs]

    conn.close()

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        out = tmp.name

    generar_ot_pdf(d, out)

    with open(out, 'rb') as f:
        buf = io.BytesIO(f.read())

    os.unlink(out)
    buf.seek(0)

    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='OT_{}.pdf'.format(d.get('folio', oid))
    )


@app.route('/api/ot/admin/login', methods=['POST'])
def ot_admin_login():
    data = request.get_json()

    if data.get('password') == ADMIN_PASS:
        session['ot_admin'] = True
        return jsonify({'ok': True})

    return jsonify({'ok': False}), 401


# =========================
# HEALTH
# =========================

@app.route('/health')
def health():
    return {'status': 'ok'}


# =========================
# START
# =========================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    print(f'\nPanel Industrial en http://localhost:{port}\n')
    app.run(host='0.0.0.0', port=port, debug=False)
