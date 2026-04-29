"""
ระบบข้อมูลการปรับปรุงการกำหนดตำแหน่งในสำนักนายกรัฐมนตรี
Flask + SQLite3 + pywebview → Desktop App (.exe)

โครงสร้าง:
  project/
  ├── app.py
  ├── pos_restructure.db   (สร้างอัตโนมัติ)
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

import os, sys, sqlite3, threading, time, uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

BASE_DIR     = os.path.dirname(sys.executable if getattr(sys,'frozen',False) else os.path.abspath(__file__))
DB_PATH      = os.path.join(BASE_DIR, 'pos_restructure.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXT  = {'pdf', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

# ── DB ──────────────────────────────────────────────────────────────────────
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con

def init_db():
    con = get_db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            sec1_rows    TEXT DEFAULT '[]',
            sec2_rows    TEXT DEFAULT '[]',
            sec3_rows    TEXT DEFAULT '[]',
            p4_round     TEXT,
            p4_date      TEXT,
            p4_resolution TEXT,
            p4_status    TEXT,
            p4_effective TEXT,
            p4_note      TEXT,
            p5_salary    TEXT,
            p5_round     TEXT,
            p5_date      TEXT,
            file_name    TEXT,
            file_data    TEXT,
            created      TEXT,
            updated      TEXT
        )
    """)
    migrate_cols = [
        "sec1_rows TEXT DEFAULT '[]'", "sec2_rows TEXT DEFAULT '[]'", "sec3_rows TEXT DEFAULT '[]'",
        'p4_round TEXT', 'p4_date TEXT', 'p4_resolution TEXT',
        'p4_status TEXT', 'p4_effective TEXT', 'p4_note TEXT',
        'p5_salary TEXT', 'p5_round TEXT', 'p5_date TEXT',
        'file_name TEXT', 'file_data TEXT', 'file_orig_name TEXT',
        'created TEXT', 'updated TEXT',
    ]
    for col_def in migrate_cols:
        try: con.execute(f'ALTER TABLE positions ADD COLUMN {col_def}')
        except: pass
    con.commit(); con.close()
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED = {'sec1_rows','sec2_rows','sec3_rows',
           'p4_round','p4_date','p4_resolution','p4_status','p4_effective','p4_note',
           'p5_salary','p5_round','p5_date',
           'file_name','file_orig_name'}

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/positions', methods=['GET'])
def get_all():
    con = get_db()
    rows = con.execute('SELECT * FROM positions ORDER BY id DESC').fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/positions', methods=['POST'])
def add_rec():
    try:
        d = {k:v for k,v in request.get_json(force=True).items() if k in ALLOWED}
        d['created'] = datetime.now().strftime('%d/%m/%Y %H:%M')
        d['updated'] = ''
        cols = ','.join(d.keys()); plh = ','.join(['?']*len(d))
        con = get_db()
        cur = con.execute(f'INSERT INTO positions ({cols}) VALUES ({plh})', list(d.values()))
        con.commit(); rid = cur.lastrowid; con.close()
        return jsonify({'id':rid,'ok':True}), 201
    except Exception as e:
        return jsonify({'ok':False,'error':str(e)}), 500

@app.route('/api/positions/<int:rid>', methods=['PUT'])
def upd_rec(rid):
    try:
        d = {k:v for k,v in request.get_json(force=True).items() if k in ALLOWED}
        d['updated'] = datetime.now().strftime('%d/%m/%Y %H:%M')
        sets = ','.join([f'{k}=?' for k in d.keys()])
        con = get_db()
        con.execute(f'UPDATE positions SET {sets} WHERE id=?', [*d.values(),rid])
        con.commit(); con.close()
        return jsonify({'ok':True})
    except Exception as e:
        return jsonify({'ok':False,'error':str(e)}), 500

@app.route('/api/positions/<int:rid>', methods=['DELETE'])
def del_rec(rid):
    try:
        con = get_db(); con.execute('DELETE FROM positions WHERE id=?',[rid])
        con.commit(); con.close(); return jsonify({'ok':True})
    except Exception as e:
        return jsonify({'ok':False,'error':str(e)}), 500

@app.route('/api/positions', methods=['DELETE'])
def del_all():
    try:
        con = get_db(); con.execute('DELETE FROM positions')
        con.commit(); con.close(); return jsonify({'ok':True})
    except Exception as e:
        return jsonify({'ok':False,'error':str(e)}), 500

@app.route('/api/ping')
def ping(): return jsonify({'ok':True})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'ok':False,'error':'ไม่พบไฟล์ในคำขอ'}), 400
        f = request.files['file']
        if not f or f.filename == '':
            return jsonify({'ok':False,'error':'ชื่อไฟล์ว่างเปล่า'}), 400
        if not allowed_file(f.filename):
            return jsonify({'ok':False,'error':'ประเภทไฟล์ไม่รองรับ รองรับเฉพาะ PDF, Word, Excel'}), 400
        safe_orig = secure_filename(f.filename)
        ext = safe_orig.rsplit('.', 1)[1].lower()
        unique_name = f'{uuid.uuid4().hex}.{ext}'
        f.save(os.path.join(UPLOAD_FOLDER, unique_name))
        return jsonify({'ok':True,'file_name':unique_name,'orig_name':safe_orig})
    except Exception as e:
        return jsonify({'ok':False,'error':str(e)}), 500

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ── Desktop ───────────────────────────────────────────────────────────────────
PORT = 5050

def run_flask():
    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)

def main():
    init_db()
    if HAS_WEBVIEW:
        threading.Thread(target=run_flask, daemon=True).start()
        time.sleep(0.8)
        webview.create_window(
            title='ระบบข้อมูลการปรับปรุงการกำหนดตำแหน่งในสำนักนายกรัฐมนตรี',
            url=f'http://127.0.0.1:{PORT}',
            width=1300, height=840, min_size=(960,620), resizable=True,
        )
        webview.start(debug=False)
    else:
        print(f'[PosRestructure] http://127.0.0.1:{PORT}  (Ctrl+C to stop)')
        app.run(host='0.0.0.0', port=PORT, debug=True)

if __name__ == '__main__':
    main()