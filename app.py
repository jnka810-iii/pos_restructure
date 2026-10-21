"""
ระบบข้อมูลการปรับปรุงการกำหนดตำแหน่งในสำนักนายกรัฐมนตรี
Flask + SQLite3 + pywebview → Desktop App (.exe)

โครงสร้าง:
  project/
  ├── app.py
  ├── pos_restructure.db   (สร้างอัตโนมัติ)
  ├── pos_restructure.log  (สร้างอัตโนมัติ เก็บ error ที่ไม่คาดคิด)
  ├── uploads/             (สร้างอัตโนมัติ เสิร์ฟผ่าน /uploads/<ชื่อไฟล์> เท่านั้น)
  └── templates/
      └── index.html

ติดตั้ง:
  pip install flask pywebview pyinstaller

Build .exe (Windows):
  pyinstaller --noconfirm --onefile --windowed \
    --add-data "templates;templates" \
    --hidden-import webview \
    --name "PosRestructure" app.py
"""

import logging, os, socket, sys, sqlite3, threading, time, uuid
from contextlib import contextmanager
from datetime import datetime
from urllib.parse import urlparse
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.exceptions import HTTPException

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

app = Flask(__name__)
app.json.ensure_ascii = False  # jsonify ส่งอักษรไทยเป็น UTF-8 ตรงๆ ไม่ escape
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

BASE_DIR     = os.path.dirname(sys.executable if getattr(sys,'frozen',False) else os.path.abspath(__file__))
DB_PATH      = os.path.join(BASE_DIR, 'pos_restructure.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
LOG_PATH     = os.path.join(BASE_DIR, 'pos_restructure.log')
ALLOWED_EXT  = {'pdf', 'doc', 'docx', 'xls', 'xlsx'}

# แอปที่ build เป็น .exe แบบ windowed ไม่มี console ให้ดู error ไฟล์ log จึงเป็นทางเดียว
# ที่จะรู้ว่าเกิดอะไรขึ้น เพราะข้อความที่ส่งกลับไปให้ผู้ใช้ตั้งใจให้ไม่มีรายละเอียดภายใน
_handler = logging.FileHandler(LOG_PATH, encoding='utf-8')
_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
app.logger.addHandler(_handler)
app.logger.setLevel(logging.INFO)

def file_ext(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def allowed_file(filename):
    return file_ext(filename) in ALLOWED_EXT

def now_iso():
    """ทุก timestamp เก็บเป็น ISO 8601 ค.ศ. เพื่อให้เรียงลำดับใน SQL ได้ หน้าเว็บแปลงเป็นรูปแบบไทยตอนแสดงผล"""
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

# ── DB ──────────────────────────────────────────────────────────────────────
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con

@contextmanager
def db():
    """commit เมื่อบล็อกจบปกติ และปิด connection เสมอแม้มี exception"""
    con = get_db()
    try:
        yield con
        con.commit()
    finally:
        con.close()

COLUMNS = {
    'sec1_rows'     : "TEXT DEFAULT '[]'",
    'sec2_rows'     : "TEXT DEFAULT '[]'",
    'sec3_rows'     : "TEXT DEFAULT '[]'",
    'p4_round'      : 'TEXT',
    'p4_date'       : 'TEXT',
    'p4_resolution' : 'TEXT',
    'p4_status'     : 'TEXT',
    'p4_effective'  : 'TEXT',
    'p4_note'       : 'TEXT',
    'p5_salary'     : 'TEXT',
    'p5_round'      : 'TEXT',
    'p5_date'       : 'TEXT',
    'file_name'     : 'TEXT',
    'file_orig_name': 'TEXT',
    'created'       : 'TEXT',
    'updated'       : 'TEXT',
}

ALLOWED = set(COLUMNS) - {'created', 'updated'}

def init_db():
    con = get_db()
    decls = ', '.join(f'{name} {decl}' for name, decl in COLUMNS.items())
    con.execute(f'CREATE TABLE IF NOT EXISTS positions (id INTEGER PRIMARY KEY AUTOINCREMENT, {decls})')
    existing = {r[1] for r in con.execute('PRAGMA table_info(positions)')}
    for name, decl in COLUMNS.items():
        if name not in existing:
            con.execute(f'ALTER TABLE positions ADD COLUMN {name} {decl}')
    migrate_timestamps(con)
    con.commit(); con.close()
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def migrate_timestamps(con):
    """แปลง created กับ updated ที่เก็บเป็น DD/MM/YYYY HH:MM ของเดิมให้เป็น ISO 8601

    ทำซ้ำได้ เพราะ LIKE จับได้แค่รูปแบบเก่า ค่าที่เป็น ISO อยู่แล้วหรือค่าว่างจะไม่ถูกแตะ
    """
    iso = ("substr({c},7,4) || '-' || substr({c},4,2) || '-' || substr({c},1,2)"
           " || 'T' || substr({c},12,5) || ':00'")
    for col in ('created', 'updated'):
        con.execute(f'UPDATE positions SET {col} = {iso.format(c=col)} '
                    f"WHERE {col} LIKE '__/__/____ __:__'")

def drop_upload(name):
    if not name:
        return
    try:
        os.remove(os.path.join(UPLOAD_FOLDER, os.path.basename(name)))
    except FileNotFoundError:
        pass

# ── Error handling ───────────────────────────────────────────────────────────
# ข้อความที่ผู้ใช้เห็นเป็นภาษาไทยและไม่เปิดเผยรายละเอียดภายใน รายละเอียดจริงไปอยู่ใน log
HTTP_MESSAGES = {
    400: 'คำขอไม่ถูกต้อง',
    403: 'คำขอนี้ถูกปฏิเสธ',
    404: 'ไม่พบรายการที่ต้องการ',
    405: 'วิธีเรียกใช้ไม่ถูกต้อง',
    413: f"ไฟล์ใหญ่เกินกำหนด อัปโหลดได้ไม่เกิน {app.config['MAX_CONTENT_LENGTH'] // (1024*1024)} MB",
}

def wants_json():
    return request.path.startswith('/api/')

@app.errorhandler(HTTPException)
def on_http_error(e):
    """HTTPException มี status code ที่ถูกต้องมาแล้ว ส่งต่อโดยเปลี่ยนเป็นข้อความไทย"""
    if not wants_json():
        return e
    return jsonify({'ok': False, 'error': HTTP_MESSAGES.get(e.code, 'คำขอไม่ถูกต้อง')}), e.code

@app.errorhandler(Exception)
def on_unexpected_error(e):
    if not wants_json():
        raise e  # หน้าเว็บได้หน้า error ของ Flask ตามปกติ ซึ่ง log ให้อยู่แล้ว
    app.logger.exception('unhandled error on %s %s', request.method, request.path)
    return jsonify({'ok': False, 'error': 'เกิดข้อผิดพลาดภายในระบบ กรุณาลองใหม่'}), 500

@app.before_request
def block_cross_site_writes():
    """เบราว์เซอร์ส่ง Origin มากับทุกคำขอที่เปลี่ยนข้อมูล และหน้าเว็บอื่นปลอม Origin ไม่ได้

    คำขอที่ไม่มี Origin เลยคือ client ที่ไม่ใช่เบราว์เซอร์ เช่น curl หรือ test client
    ซึ่งไม่ใช่ช่องทาง CSRF จึงปล่อยผ่าน การป้องกันการเข้าถึงจากภายนอกเป็นเรื่องของ F02
    """
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return None
    origin = request.headers.get('Origin')
    if origin and urlparse(origin).netloc != request.host:
        app.logger.warning('cross-site %s %s from origin %s', request.method, request.path, origin)
        return jsonify({'ok': False, 'error': 'คำขอข้ามเว็บไซต์ถูกปฏิเสธ'}), 403
    return None

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/positions', methods=['GET'])
def get_all():
    cols = ','.join(['id', *COLUMNS])
    with db() as con:
        rows = con.execute(f'SELECT {cols} FROM positions ORDER BY id DESC').fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/positions', methods=['POST'])
def add_rec():
    d = {k:v for k,v in request.get_json(force=True).items() if k in ALLOWED}
    d['created'] = now_iso()
    d['updated'] = ''
    cols = ','.join(d.keys()); plh = ','.join(['?']*len(d))
    with db() as con:
        cur = con.execute(f'INSERT INTO positions ({cols}) VALUES ({plh})', list(d.values()))
        rid = cur.lastrowid
    return jsonify({'id':rid,'ok':True}), 201

@app.route('/api/positions/<int:rid>', methods=['PUT'])
def upd_rec(rid):
    d = {k:v for k,v in request.get_json(force=True).items() if k in ALLOWED}
    d['updated'] = now_iso()
    sets = ','.join([f'{k}=?' for k in d.keys()])
    with db() as con:
        prev = con.execute('SELECT file_name FROM positions WHERE id=?', [rid]).fetchone()
        changed = con.execute(f'UPDATE positions SET {sets} WHERE id=?', [*d.values(),rid]).rowcount
    if not changed:
        return jsonify({'ok':False,'error':'ไม่พบรายการที่ต้องการแก้ไข'}), 404
    if 'file_name' in d and prev and prev['file_name'] != d['file_name']:
        drop_upload(prev['file_name'])
    return jsonify({'ok':True})

@app.route('/api/positions/<int:rid>', methods=['DELETE'])
def del_rec(rid):
    with db() as con:
        row = con.execute('SELECT file_name FROM positions WHERE id=?',[rid]).fetchone()
        con.execute('DELETE FROM positions WHERE id=?',[rid])
    if row: drop_upload(row['file_name'])
    return jsonify({'ok':True})

@app.route('/api/positions', methods=['DELETE'])
def del_all():
    with db() as con:
        names = [r['file_name'] for r in con.execute('SELECT file_name FROM positions')]
        con.execute('DELETE FROM positions')
    for name in names: drop_upload(name)
    return jsonify({'ok':True})

@app.route('/api/ping')
def ping(): return jsonify({'ok':True})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'ok':False,'error':'ไม่พบไฟล์ในคำขอ'}), 400
    f = request.files['file']
    if not f or f.filename == '':
        return jsonify({'ok':False,'error':'ชื่อไฟล์ว่างเปล่า'}), 400
    if not allowed_file(f.filename):
        return jsonify({'ok':False,'error':'ประเภทไฟล์ไม่รองรับ รองรับเฉพาะ PDF, Word, Excel'}), 400
    unique_name = f'{uuid.uuid4().hex}.{file_ext(f.filename)}'
    f.save(os.path.join(UPLOAD_FOLDER, unique_name))
    return jsonify({'ok':True,'file_name':unique_name,'orig_name':f.filename})

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ── Desktop ───────────────────────────────────────────────────────────────────
PORT = 5050

def run_flask():
    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)

def wait_for_port(port, timeout=20.0, host='127.0.0.1'):
    """รอจน Flask bind port เสร็จจริง แล้วค่อยเปิดหน้าต่าง

    การนอนตามเวลาที่กำหนดไว้ล่วงหน้าเป็นการเดา เครื่องที่ cold start หรือกำลังถูก
    แอนตี้ไวรัสสแกนอาจใช้เวลานานกว่านั้น แล้วหน้าต่างจะเปิดขึ้นมาเป็นหน้า error
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.05)
    return False

def main():
    init_db()
    if HAS_WEBVIEW:
        threading.Thread(target=run_flask, daemon=True).start()
        if not wait_for_port(PORT):
            print(f'[PosRestructure] เซิร์ฟเวอร์ไม่ตอบที่พอร์ต {PORT} ภายใน 20 วินาที')
            return 1
        webview.create_window(
            title='ระบบข้อมูลการปรับปรุงการกำหนดตำแหน่งในสำนักนายกรัฐมนตรี',
            url=f'http://127.0.0.1:{PORT}',
            width=1300, height=840, min_size=(960,620), resizable=True,
        )
        webview.start(debug=False)
    else:
        print(f'[PosRestructure] http://127.0.0.1:{PORT}  (Ctrl+C to stop)')
        app.run(host='127.0.0.1', port=PORT, debug=False)

if __name__ == '__main__':
    sys.exit(main() or 0)