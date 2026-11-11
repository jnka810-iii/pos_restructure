"""
ระบบข้อมูลการปรับปรุงการกำหนดตำแหน่งในสำนักนายกรัฐมนตรี
Flask + SQLite3 + pywebview → Desktop App (.exe)

โครงสร้าง:
  project/
  ├── app.py
  ├── pos_restructure.db   (สร้างอัตโนมัติ)
  ├── pos_restructure.log  (สร้างอัตโนมัติ เก็บ error ที่ไม่คาดคิด)
  ├── uploads/             (สร้างอัตโนมัติ เสิร์ฟผ่าน /uploads/<ชื่อไฟล์> เท่านั้น)
  ├── static/vendor/       (ไลบรารีหน้าเว็บในเครื่อง สร้างด้วย vendor_assets.py)
  └── templates/
      └── index.html

ติดตั้ง:
  pip install flask pywebview pyinstaller

Build .exe (Windows):
  pyinstaller --noconfirm --onefile --windowed \
    --add-data "templates;templates" \
    --add-data "static;static" \
    --hidden-import webview \
    --name "PosRestructure" app.py
"""

import logging, os, re, secrets, socket, sys, sqlite3, threading, time, uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse
from flask import Flask, g, request, jsonify, redirect, render_template, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

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
APP_VERSION  = '1.0.0'  # แสดงที่ footer ของหน้าเว็บ

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
    'created_by'    : 'TEXT',
    'updated_by'    : 'TEXT',
}

# เวลาและชื่อผู้บันทึกมาจากเซิร์ฟเวอร์เสมอ หน้าเว็บส่งค่าเหล่านี้มาเองไม่ได้
ALLOWED = set(COLUMNS) - {'created', 'updated', 'created_by', 'updated_by'}

USER_COLUMNS = {
    'username'     : 'TEXT NOT NULL UNIQUE',
    'display_name' : 'TEXT NOT NULL',
    'password_hash': 'TEXT NOT NULL',
    'created'      : 'TEXT',
    'role'         : "TEXT NOT NULL DEFAULT 'staff'",
    'updated'      : 'TEXT',
}

# บทบาทของบัญชีผู้ใช้งาน และสิ่งที่แต่ละบทบาททำได้ การตรวจสิทธิ์ทุกจุดอ่านจากตารางนี้ผ่าน can()
# เหตุผลอยู่ที่ docs/adr/0004-roles-and-user-management-in-the-web.md
ROLES = {'admin': 'ผู้ดูแลระบบ', 'staff': 'เจ้าหน้าที่'}
PERMISSIONS = {
    'admin': frozenset({'delete_request', 'delete_all', 'manage_users'}),
    'staff': frozenset(),
}

# หน้าเว็บได้ตารางนี้ไปทั้งตาราง แล้วซ่อนปุ่มที่บทบาทปัจจุบันไม่มีสิทธิ์ กติกาว่าใครทำอะไรได้
# จึงเขียนไว้ที่เดียวคือ PERMISSIONS การตรวจสิทธิ์จริงยังอยู่ที่ requires() ของทุก route
# การซ่อนปุ่มเป็นเรื่องของหน้าตา ไม่ใช่การป้องกัน
PAGE_PERMISSIONS = {role: sorted(perms) for role, perms in PERMISSIONS.items()}

# กติกาของบัญชีที่ทั้งหน้าจัดการผู้ใช้งานและ manage_users.py ใช้ร่วมกัน
USERNAME_RULE = re.compile(r'^[a-z0-9][a-z0-9._-]{2,31}$')
MIN_PASSWORD  = 8

def create_table(con, table, columns):
    """สร้างตารางถ้ายังไม่มี และเพิ่มคอลัมน์ที่ฐานข้อมูลเก่ายังขาดอยู่"""
    decls = ', '.join(f'{name} {decl}' for name, decl in columns.items())
    con.execute(f'CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, {decls})')
    existing = {r[1] for r in con.execute(f'PRAGMA table_info({table})')}
    for name, decl in columns.items():
        if name not in existing:
            con.execute(f'ALTER TABLE {table} ADD COLUMN {name} {decl}')

def init_db():
    con = get_db()
    create_table(con, 'positions', COLUMNS)
    create_table(con, 'users', USER_COLUMNS)
    migrate_timestamps(con)
    ensure_an_admin(con)
    con.commit(); con.close()
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.secret_key = load_secret_key()

def ensure_an_admin(con):
    """ถ้ามีบัญชีแต่ไม่มีผู้ดูแลระบบเลย ให้บัญชีที่เก่าที่สุดเป็นผู้ดูแลระบบ

    ฐานข้อมูลจากก่อนมีบทบาทได้บัญชีทุกตัวเป็นเจ้าหน้าที่ ถ้าไม่ตั้งใครขึ้นมา จะไม่มีใครเปิด
    แท็บจัดการผู้ใช้งานได้เลย บัญชีแรกมักเป็นของคนที่ตั้งระบบ จึงเลือกบัญชีนั้น
    รันซ้ำได้ เมื่อมีผู้ดูแลระบบอยู่แล้วคำสั่งนี้ไม่แตะอะไร
    """
    con.execute("UPDATE users SET role='admin' WHERE id=(SELECT MIN(id) FROM users)"
                " AND NOT EXISTS (SELECT 1 FROM users WHERE role='admin')")

# ใส่ไว้ใน WHERE ของคำสั่งที่ลดบทบาทหรือลบบัญชี เพื่อให้การตรวจกับการเขียนเป็นคำสั่งเดียวกัน
# สองคนที่กดลดบทบาทของกันและกันพร้อมกันจึงทำให้ระบบไม่เหลือผู้ดูแลระบบไม่ได้
NOT_THE_LAST_ADMIN = "(role != 'admin' OR (SELECT COUNT(*) FROM users WHERE role='admin') > 1)"

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
    401: 'กรุณาเข้าสู่ระบบ',
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
    ซึ่งไม่ใช่ช่องทาง CSRF จึงปล่อยผ่าน การกันคนนอกเข้าถึงเป็นเรื่องของ require_login
    """
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return None
    origin = request.headers.get('Origin')
    if origin and urlparse(origin).netloc != request.host:
        app.logger.warning('cross-site %s %s from origin %s', request.method, request.path, origin)
        return jsonify({'ok': False, 'error': 'คำขอข้ามเว็บไซต์ถูกปฏิเสธ'}), 403
    return None


# ── การเข้าสู่ระบบ ────────────────────────────────────────────────────────────
# คำขอที่มาจากเครื่องแม่ข่ายเองไม่ต้องเข้าสู่ระบบ
# เหตุผลอยู่ที่ docs/adr/0001-login-only-for-other-machines.md
LOOPBACK        = {'127.0.0.1', '::1'}
SESSION_HOURS   = 12
LOCAL_RECORDER  = 'เครื่องแม่ข่าย'   # ชื่อผู้บันทึกเมื่อบันทึกจากเครื่องแม่ข่ายโดยไม่ได้เข้าสู่ระบบ
OPEN_ENDPOINTS  = {'login', 'static'}

# คำขอจากเครื่องนี้เองผ่านด่านได้หรือไม่ serve() ตั้งค่านี้จาก host ที่ผูกจริง
# ค่าตั้งต้นเป็น True สำหรับโหมดเดสก์ท็อปและไฟล์ .exe ซึ่งเสิร์ฟให้ 127.0.0.1 เท่านั้น
TRUST_LOCAL     = True

app.permanent_session_lifetime = timedelta(hours=SESSION_HOURS)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

def secret_key_path():
    """เก็บไว้ข้างฐานข้อมูล เทสที่ย้าย DB_PATH ไปโฟลเดอร์ชั่วคราวจึงได้กุญแจของตัวเองไปด้วย"""
    return os.path.join(os.path.dirname(DB_PATH), 'secret_key')

def load_secret_key():
    """อ่านกุญแจที่ใช้เซ็นคุกกี้จากไฟล์ ถ้ายังไม่มีก็สร้างใหม่แล้วเก็บไว้

    ถ้าสุ่มกุญแจใหม่ทุกครั้งที่เปิดแอป ทุกคนในวงจะหลุดออกจากระบบทันทีที่เครื่องแม่ข่าย
    รีสตาร์ท รวมถึงคนที่กรอกแบบ บอ.1 ค้างไว้ยังไม่ได้บันทึก
    """
    path = secret_key_path()
    try:
        with open(path, encoding='utf-8') as fh:
            key = fh.read().strip()
        if key:
            return key
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(key)
    return key

def from_this_machine():
    return request.remote_addr in LOOPBACK

def walks_in_without_a_login():
    """คำขอที่ผ่านด่านได้โดยไม่ต้องเข้าสู่ระบบ

    ทั้งด่านและหน้าเข้าสู่ระบบต้องตอบคำถามนี้ตรงกัน ถ้าด่านส่งเครื่องแม่ข่ายไป /login
    แต่ /login ส่งกลับมาที่ / เครื่องแม่ข่ายจะวนไม่รู้จบ
    """
    return TRUST_LOCAL and from_this_machine()

def current_account():
    """แถวบัญชีของผู้ใช้งานที่เข้าสู่ระบบอยู่ หรือ None ถ้ายังไม่เข้า เซสชันหมดอายุ หรือบัญชีถูกลบไปแล้ว

    อ่านจากฐานข้อมูลทุกคำขอ ไม่เก็บชื่อหรือบทบาทไว้ในคุกกี้ ผู้ดูแลระบบลดบทบาทหรือลบบัญชีแล้ว
    จึงมีผลกับเซสชันที่เปิดค้างอยู่ตั้งแต่คำขอถัดไป

    อายุเซสชันตรวจที่ฝั่งเซิร์ฟเวอร์ ไม่พึ่งวันหมดอายุของคุกกี้อย่างเดียว เพราะวันหมดอายุ
    ของคุกกี้เป็นเรื่องที่เบราว์เซอร์เลือกจะเชื่อฟังหรือไม่ก็ได้
    """
    if 'account' not in g:
        g.account = load_account()
    return g.account

def load_account():
    since, username = session.get('since'), session.get('username')
    if not since or not username:
        return None
    if datetime.now() - datetime.strptime(since, '%Y-%m-%dT%H:%M:%S') > timedelta(hours=SESSION_HOURS):
        session.clear()
        return None
    with db() as con:
        row = con.execute('SELECT id, username, display_name, role FROM users WHERE username=?',
                          [username]).fetchone()
    if not row:
        session.clear()
    return row

def session_user():
    """ชื่อแสดงผลของผู้ใช้งานที่เข้าสู่ระบบอยู่ หรือค่าว่างถ้ายังไม่ได้เข้าสู่ระบบ"""
    account = current_account()
    return account['display_name'] if account else ''

def current_role():
    """เครื่องแม่ข่ายในโหมดเดสก์ท็อปนับเป็นผู้ดูแลระบบ เพราะเจ้าของเครื่องเปิดไฟล์ฐานข้อมูลได้อยู่แล้ว"""
    if walks_in_without_a_login():
        return 'admin'
    account = current_account()
    return account['role'] if account else None

def can(perm):
    return perm in PERMISSIONS.get(current_role(), frozenset())

def me_for_page():
    """ตัวตนของผู้ใช้งานเท่าที่หน้าเว็บต้องรู้เพื่อซ่อนปุ่มที่บทบาทนี้กดไม่ได้

    id เป็น None เมื่อเปิดจากเครื่องแม่ข่ายในโหมดเดสก์ท็อป ซึ่งนับเป็นผู้ดูแลระบบโดยไม่มีบัญชี
    หน้าเว็บใช้ id เทียบว่าแถวไหนคือบัญชีของตัวเอง เพื่อไม่โชว์ปุ่มลบบัญชีที่กำลังใช้งานอยู่
    """
    account = current_account()
    return {'id': account['id'] if account else None,
            'name': session_user(),
            'role': current_role()}

def requires(perm):
    """ปิด route ไว้สำหรับบทบาทที่มีสิทธิ์ perm ใน PERMISSIONS เท่านั้น"""
    def wrap(view):
        @wraps(view)
        def guarded(*args, **kwargs):
            if not can(perm):
                return jsonify({'ok': False, 'error': 'บทบาทของคุณไม่มีสิทธิ์ทำรายการนี้'}), 403
            return view(*args, **kwargs)
        return guarded
    return wrap

def recorder():
    """ชื่อที่คัดลอกลงช่องผู้บันทึกของคำขอ เป็นข้อความ ไม่ใช่ตัวอ้างอิงไปยังบัญชี
    เหตุผลอยู่ที่ docs/adr/0002-recorder-is-a-copied-name.md"""
    return session_user() or (LOCAL_RECORDER if from_this_machine() else '')

@app.before_request
def require_login():
    """ปิดทุก route ยกเว้นหน้าเข้าสู่ระบบกับไฟล์ static

    ไฟล์แนบใน /uploads/ ก็อยู่ในด่านนี้ด้วย ชื่อไฟล์เป็น UUID ที่เดายาก แต่ชื่อนั้น
    ปรากฏอยู่ในคำตอบของ GET /api/positions การเดายากจึงไม่ใช่การป้องกัน
    """
    if request.endpoint in OPEN_ENDPOINTS or walks_in_without_a_login():
        return None
    if session_user():
        return None
    if wants_json():
        return jsonify({'ok': False, 'error': 'กรุณาเข้าสู่ระบบ'}), 401
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if walks_in_without_a_login() or session_user():
            return redirect('/')
        return render_template('login.html', version=APP_VERSION)

    cred = request.get_json(silent=True) or {}
    with db() as con:
        row = con.execute('SELECT id, username, display_name, role, password_hash FROM users WHERE username=?',
                          [cred.get('username', '')]).fetchone()
    if not row or not check_password_hash(row['password_hash'], cred.get('password', '')):
        # หน่วงไว้หนึ่งวินาที การไล่เดารหัสผ่านเป็นหมื่นครั้งจึงไม่คุ้มอีกต่อไป
        # ไม่ล็อกบัญชีหลังผิดหลายครั้ง เพราะเปิดช่องให้ใครก็ได้ในวงล็อกเพื่อนร่วมงานออกจากระบบ
        time.sleep(1)
        app.logger.warning('failed login as %r from %s', cred.get('username', ''), request.remote_addr)
        return jsonify({'ok': False, 'error': 'ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง'}), 401

    session.clear()
    session.permanent = True
    session['username'] = row['username']
    session['since']    = now_iso()
    return jsonify({'ok': True, 'id': row['id'], 'display_name': row['display_name'],
                    'role': row['role']})

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION, user=session_user(),
                           me=me_for_page(), roles=ROLES, permissions=PAGE_PERMISSIONS)

@app.route('/api/positions', methods=['GET'])
def get_all():
    cols = ','.join(['id', *COLUMNS])
    with db() as con:
        rows = con.execute(f'SELECT {cols} FROM positions ORDER BY id DESC').fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/positions', methods=['POST'])
def add_rec():
    d = {k:v for k,v in request.get_json(force=True).items() if k in ALLOWED}
    d['created']    = now_iso()
    d['updated']    = ''
    d['created_by'] = recorder()
    d['updated_by'] = ''
    cols = ','.join(d.keys()); plh = ','.join(['?']*len(d))
    with db() as con:
        cur = con.execute(f'INSERT INTO positions ({cols}) VALUES ({plh})', list(d.values()))
        rid = cur.lastrowid
    return jsonify({'id':rid,'ok':True}), 201

@app.route('/api/positions/<int:rid>', methods=['PUT'])
def upd_rec(rid):
    d = {k:v for k,v in request.get_json(force=True).items() if k in ALLOWED}
    d['updated']    = now_iso()
    d['updated_by'] = recorder()
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
@requires('delete_request')
def del_rec(rid):
    with db() as con:
        row = con.execute('SELECT file_name FROM positions WHERE id=?',[rid]).fetchone()
        con.execute('DELETE FROM positions WHERE id=?',[rid])
    if row: drop_upload(row['file_name'])
    return jsonify({'ok':True})

@app.route('/api/positions', methods=['DELETE'])
@requires('delete_all')
def del_all():
    # การลบทุกคำขอในครั้งเดียวย้อนกลับไม่ได้ และไม่มีเหตุให้ทำจากเครื่องอื่น
    if not from_this_machine():
        return jsonify({'ok': False, 'error': 'ลบคำขอทั้งหมดทำได้จากเครื่องแม่ข่ายเท่านั้น'}), 403
    with db() as con:
        names = [r['file_name'] for r in con.execute('SELECT file_name FROM positions')]
        con.execute('DELETE FROM positions')
    for name in names: drop_upload(name)
    return jsonify({'ok':True})

@app.route('/api/ping')
def ping(): return jsonify({'ok':True})

# ── บัญชีผู้ใช้งาน ────────────────────────────────────────────────────────────
USER_FIELDS = 'id, username, display_name, role, created, updated'

ACCOUNT_RULES = {
    'display_name': (lambda v: bool(v), 'กรุณากรอกชื่อ-นามสกุล'),
    'username'    : (lambda v: bool(USERNAME_RULE.match(v)),
                     'ชื่อผู้ใช้ใช้ได้เฉพาะ a-z 0-9 . _ - ยาว 3 ถึง 32 ตัว และขึ้นต้นด้วยตัวอักษรหรือตัวเลข'),
    'role'        : (lambda v: v in ROLES, 'กรุณาเลือกบทบาทเป็นผู้ดูแลระบบหรือเจ้าหน้าที่'),
    'password'    : (lambda v: len(v) >= MIN_PASSWORD, f'รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD} ตัวอักษร'),
}
LAST_ADMIN_MESSAGE = 'ระบบต้องมีผู้ดูแลระบบอย่างน้อยหนึ่งคน ตั้งคนอื่นเป็นผู้ดูแลระบบก่อน'

def account_fields(*names):
    """อ่านช่องที่ต้องการจาก JSON ของคำขอ คืน (ค่า, ข้อความของช่องแรกที่ไม่ผ่าน หรือ None)

    ไล่ตรวจตามลำดับใน names ซึ่งผู้เรียกส่งมาตามลำดับช่องบนหน้าจอ
    รหัสผ่านไม่ตัดช่องว่าง เพราะช่องว่างเป็นส่วนหนึ่งของรหัสผ่านได้
    """
    body = request.get_json(silent=True) or {}
    values = {}
    for name in names:
        raw = body.get(name)
        raw = raw if isinstance(raw, str) else ''
        values[name] = raw if name == 'password' else raw.strip()
    for name in names:
        ok, message = ACCOUNT_RULES[name]
        if not ok(values[name]):
            return values, message
    return values, None

def account_row(con, uid):
    return con.execute(f'SELECT {USER_FIELDS} FROM users WHERE id=?', [uid]).fetchone()

def not_found_or_last_admin(con, uid):
    """คำสั่งที่มีเงื่อนไข NOT_THE_LAST_ADMIN ไม่โดนแถวไหนเลย บอกให้ถูกว่าเพราะอะไร"""
    if not account_row(con, uid):
        return jsonify({'ok': False, 'error': 'ไม่พบบัญชีผู้ใช้งานนี้'}), 404
    return jsonify({'ok': False, 'error': LAST_ADMIN_MESSAGE}), 409

@app.route('/api/users', methods=['GET'])
@requires('manage_users')
def list_users():
    with db() as con:
        rows = con.execute(f'SELECT {USER_FIELDS} FROM users ORDER BY id').fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/users', methods=['POST'])
@requires('manage_users')
def add_user():
    d, problem = account_fields('display_name', 'username', 'role', 'password')
    if problem:
        return jsonify({'ok': False, 'error': problem}), 400
    try:
        with db() as con:
            uid = con.execute('INSERT INTO users (username, display_name, role, password_hash, created)'
                              ' VALUES (?,?,?,?,?)',
                              [d['username'], d['display_name'], d['role'],
                               generate_password_hash(d['password']), now_iso()]).lastrowid
            ensure_an_admin(con)
            row = account_row(con, uid)
    except sqlite3.IntegrityError:
        return jsonify({'ok': False, 'error': f"มีชื่อผู้ใช้ {d['username']} อยู่แล้ว"}), 409
    return jsonify({'ok': True, 'user': dict(row)}), 201

@app.route('/api/users/<int:uid>', methods=['PUT'])
@requires('manage_users')
def update_user(uid):
    """ชื่อผู้ใช้เปลี่ยนไม่ได้ เพราะเป็นสิ่งที่เจ้าของบัญชีพิมพ์ตอนเข้าสู่ระบบ"""
    d, problem = account_fields('display_name', 'role')
    if problem:
        return jsonify({'ok': False, 'error': problem}), 400
    with db() as con:
        changed = con.execute('UPDATE users SET display_name=?, role=?, updated=?'
                              f" WHERE id=? AND (?='admin' OR {NOT_THE_LAST_ADMIN})",
                              [d['display_name'], d['role'], now_iso(), uid, d['role']]).rowcount
        if not changed:
            return not_found_or_last_admin(con, uid)
        row = account_row(con, uid)
    return jsonify({'ok': True, 'user': dict(row)})

@app.route('/api/users/<int:uid>/password', methods=['PUT'])
@requires('manage_users')
def reset_password(uid):
    d, problem = account_fields('password')
    if problem:
        return jsonify({'ok': False, 'error': problem}), 400
    with db() as con:
        changed = con.execute('UPDATE users SET password_hash=?, updated=? WHERE id=?',
                              [generate_password_hash(d['password']), now_iso(), uid]).rowcount
    if not changed:
        return jsonify({'ok': False, 'error': 'ไม่พบบัญชีผู้ใช้งานนี้'}), 404
    return jsonify({'ok': True})

@app.route('/api/users/<int:uid>', methods=['DELETE'])
@requires('manage_users')
def delete_user(uid):
    """ชื่อผู้บันทึกบนคำขอเดิมไม่เปลี่ยน ดู docs/adr/0002-recorder-is-a-copied-name.md"""
    me = current_account()
    if me and me['id'] == uid:
        return jsonify({'ok': False, 'error': 'ลบบัญชีที่กำลังใช้งานอยู่ไม่ได้'}), 409
    with db() as con:
        if not con.execute(f'DELETE FROM users WHERE id=? AND {NOT_THE_LAST_ADMIN}', [uid]).rowcount:
            return not_found_or_last_admin(con, uid)
    return jsonify({'ok': True})

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
PORT = 5020

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

def serve(host='127.0.0.1', port=PORT):
    """เปิดเซิร์ฟเวอร์ และตั้งนโยบายเข้าสู่ระบบจาก host ที่ผูกจริง

    host ที่ไม่ใช่ loopback แปลว่าเครื่องอื่นเข้าถึงแอปได้ ทุกคนจึงต้องเข้าสู่ระบบ รวมถึง
    คนที่นั่งอยู่หน้าเครื่องแม่ข่าย เพราะเมื่อเปิดรับจากภายนอกแล้ว เซิร์ฟเวอร์ไม่มีทางรู้ว่า
    คำขอที่มาจาก 127.0.0.1 เป็นคนที่นั่งอยู่หน้าเครื่องจริง หรือถูกส่งต่อมาจากที่อื่น
    นโยบายจึงมาจากสิ่งเดียวที่รู้แน่ คือเราเปิดให้ใครเข้าถึงได้บ้าง

    คืน 0 เมื่อเซิร์ฟเวอร์ปิดตามปกติ และคืน 1 เมื่อปฏิเสธที่จะเปิด
    """
    global TRUST_LOCAL
    TRUST_LOCAL = host in LOOPBACK
    init_db()
    if not TRUST_LOCAL:
        with db() as con:
            accounts = con.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if not accounts:
            print('[PosRestructure] ยังไม่มีบัญชีผู้ใช้งาน จึงเปิดเซิร์ฟเวอร์ให้ไม่ได้')
            print('[PosRestructure] โหมดนี้ทุกคนต้องเข้าสู่ระบบ รวมถึงเครื่องนี้ '
                  'ถ้าเปิดตอนนี้จะไม่มีใครเข้าได้เลย')
            print('[PosRestructure] สร้างบัญชีแรกก่อนด้วย  '
                  'python manage_users.py add <ชื่อผู้ใช้งาน> "<ชื่อแสดงผล>"')
            return 1
    app.run(host=host, port=port, debug=False)
    return 0

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