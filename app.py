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

import os, sys, sqlite3, threading, time
from datetime import datetime
from flask import Flask, request, jsonify, render_template

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

BASE_DIR = os.path.dirname(sys.executable if getattr(sys,'frozen',False) else os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'pos_restructure.db')

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
            -- ส่วนที่ 1-3 เก็บเป็น JSON array string
            sec1_rows    TEXT DEFAULT '[]',
            sec2_rows    TEXT DEFAULT '[]',
            sec3_rows    TEXT DEFAULT '[]',
            -- ส่วนที่ 4
            p4_round     TEXT,
            p4_date      TEXT,
            p4_resolution TEXT,
            p4_status    TEXT,
            p4_effective TEXT,
            p4_note      TEXT,
            -- ส่วนที่ 5
            p5_salary    TEXT,
            p5_round     TEXT,
            p5_date      TEXT,
            -- metadata
            created      TEXT,
            updated      TEXT
        )
    """)
    con.commit(); con.close()

ALLOWED = {'sec1_rows','sec2_rows','sec3_rows',
           'p4_round','p4_date','p4_resolution','p4_status','p4_effective','p4_note',
           'p5_salary','p5_round','p5_date'}

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
    d = {k:v for k,v in request.get_json(force=True).items() if k in ALLOWED}
    d['created'] = datetime.now().strftime('%d/%m/%Y %H:%M')
    d['updated'] = ''
    cols = ','.join(d.keys()); plh = ','.join(['?']*len(d))
    con = get_db()
    cur = con.execute(f'INSERT INTO positions ({cols}) VALUES ({plh})', list(d.values()))
    con.commit(); rid = cur.lastrowid; con.close()
    return jsonify({'id':rid,'ok':True}), 201

@app.route('/api/positions/<int:rid>', methods=['PUT'])
def upd_rec(rid):
    d = {k:v for k,v in request.get_json(force=True).items() if k in ALLOWED}
    d['updated'] = datetime.now().strftime('%d/%m/%Y %H:%M')
    sets = ','.join([f'{k}=?' for k in d.keys()])
    con = get_db()
    con.execute(f'UPDATE positions SET {sets} WHERE id=?', [*d.values(),rid])
    con.commit(); con.close()
    return jsonify({'ok':True})

@app.route('/api/positions/<int:rid>', methods=['DELETE'])
def del_rec(rid):
    con = get_db(); con.execute('DELETE FROM positions WHERE id=?',[rid])
    con.commit(); con.close(); return jsonify({'ok':True})

@app.route('/api/positions', methods=['DELETE'])
def del_all():
    con = get_db(); con.execute('DELETE FROM positions')
    con.commit(); con.close(); return jsonify({'ok':True})

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