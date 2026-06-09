import os, sys, io, tempfile, base64, sqlite3, json
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

#  DB 
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
            cantidad TEXT, unidad TEXT,
            descripcion TEXT, serie_no_parte TEXT,
            tipo TEXT DEFAULT 'nuevo'
        );
    ''')
    cur = conn.execute('SELECT COUNT(*) FROM ot_trabajadores')
    if cur.fetchone()[0] == 0:
        for w in ['Alberto Lopez','Trabajador 2','Trabajador 3','Trabajador 4','Trabajador 5']:
            conn.execute('INSERT INTO ot_trabajadores (nombre) VALUES (?)', (w,))
    conn.commit(); conn.close()

def next_folio():
    conn = get_db()
    cur = conn.execute("SELECT MAX(CAST(SUBSTR(folio,3) AS INTEGER)) FROM ot_ordenes WHERE folio LIKE 'OT%'")
    n = (cur.fetchone()[0] or 0) + 1
    conn.close()
    return f'OT{n:04d}'

init_db()

#  PAGES 
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

#  PDF ROUTES 
@app.route('/generar', methods=['POST'])
def gen_pdf():
    data = request.get_json(force=True)
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        path = tmp.name
    generar(data, path)
    with open(path, 'rb') as f:
        buf = io.BytesIO(f.read())
    os.unlink(path)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name='COT_{}.pdf'.format(data.get('numero_cotizacion','ESHEN')))

@app.route('/generar-remision', methods=['POST'])
def gen_remision():
    data = request.get_json(force=True)
    sello_path = evidencia_path = None
    temps = []

    def save_b64(b64_str, mime):
        ext = '.jpg' if 'jpeg' in mime or 'jpg' in mime else '.png'
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as t:
            t.write(base64.b64decode(b64_str)); return t.name

    if data.get('sello_b64'):
        sello_path = save_b64(data['sello_b64'], data.get('sello_mime','image/jpeg'))
        temps.append(sello_path)
    if data.get('evidencia_b64'):
        evidencia_path = save_b64(data['evidencia_b64'], data.get('evidencia_mime','image/jpeg'))
        temps.append(evidencia_path)

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        out_path = tmp.name
    temps.append(out_path)

    try:
        generar_remision(data, out_path, sello_path=sello_path, evidencia_path=evidencia_path)
        with open(out_path, 'rb') as f:
            buf = io.BytesIO(f.read())
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True,
                         download_name='REM_{}.pdf'.format(data.get('numero_remision','ESHEN')))
    finally:
        for p in temps:
            if p and os.path.exists(p):
                try: os.unlink(p)
                except: pass

#  ORDENES API 
@app.route('/api/ot/trabajadores', methods=['GET'])
def ot_get_trabajadores():
    conn = get_db()
    rows = conn.execute('SELECT * FROM ot_trabajadores WHERE activo=1 ORDER BY nombre').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/ot/trabajadores', methods=['POST'])
def ot_add_trabajador():
    data = request.get_json()
    conn = get_db()
    conn.execute('INSERT INTO ot_trabajadores (nombre) VALUES (?)', (data['nombre'],))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/ot/trabajadores/<int:tid>', methods=['DELETE'])
def ot_del_trabajador(tid):
    conn = get_db()
    conn.execute('UPDATE ot_trabajadores SET activo=0 WHERE id=?', (tid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/ot/ordenes', methods=['GET'])
def ot_get_ordenes():
    conn = get_db()
    sql = '''SELECT o.*, t.nombre as asignado_nombre
             FROM ot_ordenes o LEFT JOIN ot_trabajadores t ON o.asignado_id=t.id
             WHERE 1=1'''
    params = []
    if request.args.get('asignado'):
        sql += ' AND o.asignado_id=?'; params.append(request.args['asignado'])
    if request.args.get('estado'):
        sql += ' AND o.estado=?'; params.append(request.args['estado'])
    sql += ' ORDER BY o.id DESC'
    rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        refs = conn.execute('SELECT * FROM ot_refacciones WHERE orden_id=?', (r['id'],)).fetchall()
        d['refacciones'] = [dict(ref) for ref in refs]
        result.append(d)
    conn.close()
    return jsonify(result)

@app.route('/api/ot/ordenes', methods=['POST'])
def ot_create_orden():
    data = request.get_json()
    folio = next_folio()
    now   = datetime.now().strftime('%d/%m/%Y %H:%M')
    conn  = get_db()
    cur   = conn.execute('''INSERT INTO ot_ordenes
        (folio,solicitante,asignado_id,area,fecha_hora,codigo_equipo,
         descripcion_servicio,trabajos_efectuados,observaciones,estado)
        VALUES (?,?,?,?,?,?,?,?,?,?)''',
        (folio, data.get('solicitante',''), data.get('asignado_id') or None,
         data.get('area',''), data.get('fecha_hora', now),
         data.get('codigo_equipo',''), data.get('descripcion_servicio',''),
         data.get('trabajos_efectuados',''), data.get('observaciones',''),
         data.get('estado','pendiente')))
    oid = cur.lastrowid
    for ref in data.get('refacciones', []):
        if ref.get('descripcion'):
            conn.execute('INSERT INTO ot_refacciones (orden_id,cantidad,unidad,descripcion,serie_no_parte,tipo) VALUES (?,?,?,?,?,?)',
                (oid, ref.get('cantidad',''), ref.get('unidad',''),
                 ref.get('descripcion',''), ref.get('serie_no_parte',''), ref.get('tipo','nuevo')))
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'folio': folio, 'id': oid})

@app.route('/api/ot/ordenes/<int:oid>', methods=['PUT'])
def ot_update_orden(oid):
    data = request.get_json()
    now  = datetime.now().strftime('%d/%m/%Y %H:%M')
    conn = get_db()
    conn.execute('''UPDATE ot_ordenes SET solicitante=?,asignado_id=?,area=?,
        codigo_equipo=?,descripcion_servicio=?,trabajos_efectuados=?,
        observaciones=?,estado=?,updated_at=? WHERE id=?''',
        (data.get('solicitante',''), data.get('asignado_id') or None,
         data.get('area',''), data.get('codigo_equipo',''),
         data.get('descripcion_servicio',''), data.get('trabajos_efectuados',''),
         data.get('observaciones',''), data.get('estado','pendiente'), now, oid))
    conn.execute('DELETE FROM ot_refacciones WHERE orden_id=?', (oid,))
    for ref in data.get('refacciones', []):
        if ref.get('descripcion'):
            conn.execute('INSERT INTO ot_refacciones (orden_id,cantidad,unidad,descripcion,serie_no_parte,tipo) VALUES (?,?,?,?,?,?)',
                (oid, ref.get('cantidad',''), ref.get('unidad',''),
                 ref.get('descripcion',''), ref.get('serie_no_parte',''), ref.get('tipo','nuevo')))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/ot/ordenes/<int:oid>/estado', methods=['PATCH'])
def ot_update_estado(oid):
    data = request.get_json()
    now  = datetime.now().strftime('%d/%m/%Y %H:%M')
    conn = get_db()
    conn.execute('UPDATE ot_ordenes SET estado=?,updated_at=? WHERE id=?',
                 (data['estado'], now, oid))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/ot/ordenes/<int:oid>', methods=['DELETE'])
def ot_delete_orden(oid):
    conn = get_db()
    conn.execute('DELETE FROM ot_refacciones WHERE orden_id=?', (oid,))
    conn.execute('DELETE FROM ot_ordenes WHERE id=?', (oid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/ot/ordenes/<int:oid>/pdf', methods=['GET'])
def ot_pdf(oid):
    import sys
    sys.path.insert(0, BASE)
    from generar_ot import generar_ot_pdf
    conn = get_db()
    r = conn.execute(
        'SELECT o.*,t.nombre as asignado_nombre FROM ot_ordenes o '
        'LEFT JOIN ot_trabajadores t ON o.asignado_id=t.id WHERE o.id=?', (oid,)).fetchone()
    if not r:
        return jsonify({'error':'not found'}), 404
    d = dict(r)
    refs = conn.execute('SELECT * FROM ot_refacciones WHERE orden_id=?', (oid,)).fetchall()
    d['refacciones'] = [dict(ref) for ref in refs]
    conn.close()
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        out = tmp.name
    generar_ot_pdf(d, out)
    with open(out,'rb') as f:
        buf = io.BytesIO(f.read())
    os.unlink(out)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name='OT_{}.pdf'.format(d.get('folio',oid)))

@app.route('/api/ot/admin/login', methods=['POST'])
def ot_admin_login():
    data = request.get_json()
    if data.get('password') == ADMIN_PASS:
        session['ot_admin'] = True
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 401

@app.route('/health')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    print(f'\n  Panel Industrial en http://localhost:{port}\n')
    app.run(host='0.0.0.0', port=port, debug=False)
