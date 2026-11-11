#!/usr/bin/env python
"""control_pos.py — ขับแอป pos_restructure เพื่อพิสูจน์พฤติกรรมที่ผู้ใช้เห็น

ทุกคำสั่งพิมพ์ JSON หนึ่งก้อนออก stdout และคืน exit code 0 เมื่อสำเร็จ 1 เมื่อไม่สำเร็จ
2 เมื่อเรียกใช้ผิด ความผิดพลาดทุกแบบตอบเป็น {"ok": false, "error", "hint", "next"} โดย
"next" คือคำสั่งที่ควรรันต่อ

หมวดคำสั่ง
  app      เปิด ปิด และรันตัวแอปสำหรับการตรวจ (อินสแตนซ์แยก ไม่แตะข้อมูลจริง)
  doctor   ตรวจอย่างเดียวว่าอินสแตนซ์ที่เปิดไว้ควรขับต่อหรือไม่
  api      ยิง HTTP ไปที่ API ของอินสแตนซ์นั้น ทั้งแบบเครื่องแม่ข่ายและแบบเครื่องในวง LAN
  browser  ขับหน้าเว็บจริงด้วย Edge หรือ Chrome headless ผ่าน CDP
  users    จัดการบัญชีผู้ใช้งานในฐานข้อมูลของอินสแตนซ์นั้น
  data     ใส่และล้างข้อมูลตั้งต้น

คำสั่งที่ลบหรือแก้ข้อมูลรับ --dry-run ทุกคำสั่ง  สองคำสั่งที่ย้อนกลับไม่ได้
(data reset, users remove) เป็น dry-run โดยค่าเริ่มต้นและต้องใส่ --apply จึงจะทำจริง
แบบเดียวกับ cleanup_orphans.py และ migrate_schema.py ของโปรเจกต์
"""

import argparse
import base64
import http.cookiejar
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath(os.path.join(SKILL_DIR, '..', '..', '..'))
STATE_ROOT = os.path.join(os.environ.get('TEMP') or '/tmp', 'pos-verify')
CURRENT_FILE = os.path.join(STATE_ROOT, 'current.json')
SEED_MARKER = 'ชุดตรวจ verify-pos-restructure'
READY_BADGE = 'เชื่อมต่อแล้ว'

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


class Fail(Exception):
    """ความล้มเหลวที่บอกได้ว่าควรทำอะไรต่อ"""

    def __init__(self, error, hint='', next_steps=(), **extra):
        super().__init__(error)
        self.error = error
        self.hint = hint
        self.next_steps = list(next_steps)
        self.extra = extra


def emit(payload, code=0):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(code)


# ── สถานะของการตรวจหนึ่งครั้ง ─────────────────────────────────────────────────
def repo_python():
    """python ของ .venv ถ้ามี เพราะ Flask กับ Werkzeug ที่แอปใช้อยู่ในนั้น"""
    venv = os.path.join(REPO_DIR, '.venv', 'Scripts', 'python.exe')
    return venv if os.path.isfile(venv) else sys.executable


def git_commit():
    try:
        out = subprocess.run(['git', '-C', REPO_DIR, 'rev-parse', '--short', 'HEAD'],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def app_version():
    try:
        with open(os.path.join(REPO_DIR, 'app.py'), encoding='utf-8') as fh:
            found = re.search(r"^APP_VERSION\s*=\s*'([^']+)'", fh.read(), re.M)
        return found.group(1) if found else None
    except OSError:
        return None


def resolve_run_dir(explicit):
    if explicit:
        return os.path.abspath(explicit)
    try:
        with open(CURRENT_FILE, encoding='utf-8') as fh:
            return json.load(fh)['run_dir']
    except (OSError, ValueError, KeyError):
        raise Fail(
            'ยังไม่มีอินสแตนซ์สำหรับการตรวจที่เปิดอยู่',
            hint=f'ตัวชี้อินสแตนซ์ล่าสุดอยู่ที่ {CURRENT_FILE}',
            next_steps=['control_pos.py app start'],
        )


def load_state(run_dir):
    path = os.path.join(run_dir, 'state.json')
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except OSError:
        raise Fail(
            f'ไม่พบ state.json ใน {run_dir}',
            hint='โฟลเดอร์นี้ไม่ใช่อินสแตนซ์ของการตรวจ หรือถูกลบไปแล้ว',
            next_steps=['control_pos.py app start'],
        )


def save_state(state):
    with open(os.path.join(state['run_dir'], 'state.json'), 'w', encoding='utf-8') as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    os.makedirs(STATE_ROOT, exist_ok=True)
    with open(CURRENT_FILE, 'w', encoding='utf-8') as fh:
        json.dump({'run_dir': state['run_dir']}, fh)


# ── โปรเซส ───────────────────────────────────────────────────────────────────
def process_image(pid):
    """ชื่อ executable ของ pid หรือ None ถ้าไม่มีโปรเซสนี้แล้ว

    ใช้ตรวจก่อนฆ่าทุกครั้ง เพราะ Windows เอาเลข pid กลับมาใช้ซ้ำได้ การฆ่าตามเลขที่
    จดไว้เฉยๆ อาจไปโดนโปรเซสอื่นที่มาเกิดใหม่ทับเลขเดิม
    """
    if not pid:
        return None
    try:
        out = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    first = out.stdout.strip().splitlines()[:1]
    if not first or not first[0].startswith('"'):
        return None
    return first[0].split('","')[0].strip('"')


def kill_tree(pid, expect_prefix):
    """ฆ่าเฉพาะโปรเซสที่การตรวจครั้งนี้เปิดไว้เอง และต้องเป็น executable ที่คาดไว้"""
    image = process_image(pid)
    if image is None:
        return {'pid': pid, 'result': 'ไม่มีโปรเซสนี้อยู่แล้ว'}
    if not image.lower().startswith(expect_prefix):
        return {'pid': pid, 'image': image,
                'result': f'ข้ามไว้ เลข pid นี้เป็นของ {image} ไม่ใช่โปรเซสที่เปิดไว้'}
    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                   capture_output=True, text=True, timeout=30)
    return {'pid': pid, 'image': image, 'result': 'ปิดแล้ว'}


def port_owner(port):
    """pid ที่ถือพอร์ตนี้อยู่ในสถานะ LISTENING"""
    try:
        out = subprocess.run(['netstat', '-ano', '-p', 'TCP'],
                             capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == 'LISTENING' and parts[1].endswith(f':{port}'):
            return int(parts[4])
    return None


def http_json(url, timeout=3.0):
    with urllib.request.urlopen(url, timeout=timeout) as fh:
        return json.loads(fh.read().decode('utf-8'))


def wait_usable(base_url, data_dir, lan=False, timeout=40.0):
    """รอจนอินสแตนซ์ใช้งานได้จริง ไม่ใช่แค่มีโปรเซสตอบพอร์ต

    พอร์ตเปิดก่อนที่ init_db() จะสร้างตารางเสร็จได้ จึงรอให้แอปตอบคำขอจริงและตาราง
    ถูกสร้างครบก่อนบอกว่าพร้อม

    โหมด LAN บังคับเข้าสู่ระบบกับทุกคนรวมถึง 127.0.0.1 คำขอที่ยังไม่เข้าสู่ระบบจึงได้ 401
    ซึ่งแปลว่าพร้อมแล้วและด่านทำงานอยู่ ไม่ใช่แปลว่ายังไม่พร้อม
    """
    deadline = time.monotonic() + timeout
    last = 'ยังไม่ได้ลอง'
    db_path = os.path.join(data_dir, 'pos_restructure.db')
    while time.monotonic() < deadline:
        try:
            if lan:
                try:
                    urllib.request.urlopen(f'{base_url}/api/ping', timeout=3)
                    raise RuntimeError('/api/ping ตอบ 200 ทั้งที่โหมด LAN ต้องเข้าสู่ระบบก่อน')
                except urllib.error.HTTPError as exc:
                    if exc.code != 401:
                        raise RuntimeError(f'/api/ping ตอบ {exc.code} ไม่ใช่ 401')
                with urllib.request.urlopen(f'{base_url}/login', timeout=3) as fh:
                    if 'id="login-form"' not in fh.read().decode('utf-8', 'replace'):
                        raise RuntimeError('หน้าเข้าสู่ระบบยังไม่มีฟอร์ม')
            else:
                if http_json(f'{base_url}/api/ping').get('ok') is not True:
                    raise RuntimeError('/api/ping ไม่ตอบ ok')
                if not isinstance(http_json(f'{base_url}/api/positions'), list):
                    raise RuntimeError('/api/positions ไม่ตอบเป็นรายการ')
            con = sqlite3.connect(db_path)
            try:
                names = {r[0] for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                con.close()
            missing = {'positions', 'users'} - names
            if missing:
                raise RuntimeError(f'ตารางยังไม่ครบ ขาด {sorted(missing)}')
            return True, 'ok'
        except Exception as exc:
            last = f'{type(exc).__name__}: {exc}'
            time.sleep(0.2)
    return False, last


def url_path(raw):
    """ทำให้เส้นทางเป็นรูป /xxx และจับกรณีที่เชลล์แปลงเส้นทางไปแล้ว

    Git Bash บน Windows แปลงอาร์กิวเมนต์ที่ขึ้นต้นด้วย / ให้เป็นเส้นทางของ Windows
    ก่อนที่ Python จะเห็น "/login" จึงมาถึงเป็น "C:/Program Files/Git/login" ถ้าปล่อยผ่าน
    จะได้ 404 ที่อธิบายไม่ถูกว่าเพราะอะไร จึงบอกตรงๆ ว่าควรพิมพ์อย่างไร
    """
    path = (raw or '/').strip().replace('\\', '/')
    if re.match(r'^[A-Za-z]:/', path):
        tail = path.rstrip('/').rsplit('/', 1)[-1]
        raise Fail(
            f'เส้นทาง {raw!r} ถูกเชลล์แปลงเป็นเส้นทางของ Windows ไปแล้ว',
            hint='Git Bash บน Windows แปลงอาร์กิวเมนต์ที่ขึ้นต้นด้วย / ให้เอง',
            next_steps=[f'เขียนโดยไม่มี / นำหน้า เช่น {tail or "(ละ --path ไว้)"}',
                        'หรือใส่ MSYS_NO_PATHCONV=1 ไว้หน้าคำสั่ง',
                        'หรือสั่งจาก PowerShell ซึ่งไม่แปลงเส้นทางให้'])
    return path if path.startswith('/') else '/' + path


def lan_ip():
    """ที่อยู่ IPv4 ที่เครื่องนี้ใช้ออกเครือข่าย ใช้แทนบทบาท "เครื่องในวง LAN"

    แอปแยกเครื่องแม่ข่ายจากเครื่องในวงด้วย request.remote_addr ที่ต้องไม่ใช่ loopback
    การต่อกลับมาที่ IP ของเครื่องตัวเองทำให้ remote_addr เป็น IP นั้น แอปจึงเห็นเป็น
    เครื่องในวงจริงๆ โดยที่ข้อมูลไม่ได้ออกไปนอกเครื่องเลย
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


# ── app ──────────────────────────────────────────────────────────────────────
def cmd_app_serve(args):
    """รันแอปในโฟลเดอร์ข้อมูลที่แยกไว้ คำสั่งนี้ไม่คืนค่า app start เป็นคนเรียก"""
    sys.path.insert(0, REPO_DIR)
    import logging
    import app as flask_app

    data_dir = os.path.abspath(args.data_dir)
    os.makedirs(data_dir, exist_ok=True)
    flask_app.DB_PATH = os.path.join(data_dir, 'pos_restructure.db')
    flask_app.UPLOAD_FOLDER = os.path.join(data_dir, 'uploads')
    flask_app.LOG_PATH = os.path.join(data_dir, 'pos_restructure.log')
    # app.py ผูก handler ไปที่ log ของโปรเจกต์ตอน import ย้ายมาที่โฟลเดอร์ของการตรวจ
    # เพื่อให้ error ของอินสแตนซ์นี้ไม่ไปปนกับ log ของข้อมูลจริง
    for handler in list(flask_app.app.logger.handlers):
        flask_app.app.logger.removeHandler(handler)
        handler.close()
    handler = logging.FileHandler(flask_app.LOG_PATH, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    flask_app.app.logger.addHandler(handler)
    if args.pid_file:
        # .venv\Scripts\python.exe เป็นตัวเรียกอีกชั้น โปรเซสที่ถือพอร์ตจริงคือลูกของมัน
        # ลูกจึงเป็นคนบอกเลข pid ของตัวเองไว้ ให้ app start จดเลขที่ถือพอร์ตจริงได้
        with open(args.pid_file, 'w', encoding='utf-8') as fh:
            fh.write(str(os.getpid()))
    host = '0.0.0.0' if args.lan else '127.0.0.1'
    print(f'[verify] serving on {host}:{args.port} data={data_dir}', flush=True)
    # ผ่าน app.serve ตัวเดียวกับที่ run_server.bat และ run_browser.bat เรียก นโยบาย
    # เข้าสู่ระบบจึงเป็นของจริง ไม่ใช่ของที่ชุดตรวจตั้งเอง
    sys.exit(flask_app.serve(host=host, port=args.port))


LAN_ACCOUNT = {'username': 'verify', 'display': 'ผู้ตรวจของชุดตรวจ', 'password': 'verify-pass-1'}

BOOTSTRAP_ACCOUNT = """
import sys, os
repo, data_dir, username, display, password = sys.argv[1:6]
sys.path.insert(0, repo)
import app
from werkzeug.security import generate_password_hash
app.DB_PATH = os.path.join(data_dir, 'pos_restructure.db')
app.UPLOAD_FOLDER = os.path.join(data_dir, 'uploads')
app.init_db()
con = app.get_db()
con.execute('INSERT INTO users (username, display_name, password_hash, created) VALUES (?,?,?,?)',
            [username, display, generate_password_hash(password), app.now_iso()])
con.commit()
con.close()
"""


def bootstrap_lan_account(python, data_dir, account):
    """สร้างบัญชีแรกของอินสแตนซ์ ก่อนเปิดเซิร์ฟเวอร์แบบ LAN

    app.serve ปฏิเสธที่จะเปิดโหมด LAN ตอนที่ยังไม่มีบัญชี เพราะเปิดไปก็ไม่มีใครเข้าได้เลย
    ชุดตรวจจึงสร้างบัญชีไว้ก่อน เหมือนที่ผู้ดูแลต้องรัน manage_users.py ก่อนเปิดเซิร์ฟเวอร์จริง
    """
    done = subprocess.run(
        [python, '-c', BOOTSTRAP_ACCOUNT, REPO_DIR, data_dir,
         account['username'], account['display'], account['password']],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    if done.returncode:
        raise Fail('สร้างบัญชีแรกสำหรับโหมด LAN ไม่สำเร็จ',
                   hint=(done.stderr or done.stdout)[-800:],
                   next_steps=['control_pos.py app start   # โหมดเครื่องแม่ข่ายอย่างเดียว'])
    return dict(account)


def spawn(cmd, log_path):
    """เปิดลูกแบบไม่ผูกกับคอนโซลของคำสั่งนี้ เพื่อให้ยังอยู่หลังคำสั่งนี้จบ"""
    flags = 0
    if os.name == 'nt':
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    log = open(log_path, 'ab')
    return subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                            cwd=REPO_DIR, creationflags=flags, close_fds=True)


def cmd_app_start(args):
    if not os.path.isfile(os.path.join(REPO_DIR, 'app.py')):
        raise Fail(f'ไม่พบ app.py ใน {REPO_DIR}',
                   hint='สคิลนี้ต้องอยู่ที่ <repo>/.claude/skills/verify-pos-restructure/',
                   next_steps=['ย้ายโฟลเดอร์สคิลกลับเข้าโปรเจกต์ pos_restructure'])

    # การเปิดทับอินสแตนซ์เดิมทำให้ตัวชี้ current.json ชี้ไปที่ตัวใหม่ แล้วเซิร์ฟเวอร์กับ
    # เบราว์เซอร์ของตัวเก่าค้างอยู่โดยไม่มีใครรู้ว่าต้องปิดอย่างไร จึงปฏิเสธไว้ก่อน
    if not args.run_dir and os.path.isfile(CURRENT_FILE):
        previous = None
        try:
            previous = load_state(resolve_run_dir(None))
        except Fail:
            previous = None
        if previous and (process_image(previous.get('server_pid')) or '').lower().startswith('python'):
            raise Fail(
                'มีอินสแตนซ์ของการตรวจเปิดอยู่แล้ว',
                hint=f"run_dir {previous['run_dir']} พอร์ต {previous['port']} "
                     f"pid {previous['server_pid']}",
                next_steps=['control_pos.py doctor',
                            'control_pos.py app stop   # ถ้าต้องการเริ่มใหม่'],
            )

    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    run_dir = os.path.abspath(args.run_dir) if args.run_dir else os.path.join(STATE_ROOT, f'run-{run_id}')
    data_dir = os.path.join(run_dir, 'data')
    evidence_dir = os.path.join(run_dir, 'evidence')
    profile_dir = os.path.join(run_dir, 'browser-profile')
    downloads_dir = os.path.join(run_dir, 'downloads')
    for path in (run_dir, data_dir, evidence_dir, downloads_dir):
        os.makedirs(path, exist_ok=True)

    port = args.port or cdp.free_port()
    ip = lan_ip() if args.lan else None
    if args.lan and not ip:
        raise Fail('หาที่อยู่ IPv4 ของเครื่องนี้ไม่ได้ จึงจำลองเครื่องในวง LAN ไม่ได้',
                   hint='เครื่องนี้อาจไม่มีเครือข่ายที่มี default gateway',
                   next_steps=['control_pos.py app start   # โหมดเครื่องแม่ข่ายอย่างเดียว'])

    state = {
        'run_id': run_id,
        'run_dir': run_dir,
        'repo': REPO_DIR,
        'started': datetime.now().isoformat(timespec='seconds'),
        'port': port,
        'lan': bool(args.lan),
        'base_url': f'http://127.0.0.1:{port}',
        'lan_url': f'http://{ip}:{port}' if ip else None,
        'data_dir': data_dir,
        'evidence_dir': evidence_dir,
        'downloads_dir': downloads_dir,
        'profile_dir': profile_dir,
        'server_log': os.path.join(run_dir, 'server.log'),
        'app_version': app_version(),
        'git_commit': git_commit(),
        'python': repo_python(),
    }

    account = bootstrap_lan_account(state['python'], data_dir, LAN_ACCOUNT) if args.lan else None

    pid_file = os.path.join(run_dir, 'server.pid')
    if os.path.isfile(pid_file):
        os.remove(pid_file)
    server_cmd = [state['python'], os.path.join(SKILL_DIR, 'control_pos.py'),
                  'app', 'serve', '--port', str(port), '--data-dir', data_dir,
                  '--pid-file', pid_file]
    if args.lan:
        server_cmd.append('--lan')
    server = spawn(server_cmd, state['server_log'])
    state['launcher_pid'] = server.pid
    state['server_pid'] = server.pid

    ready, why = wait_usable(state['base_url'], data_dir, lan=bool(args.lan))
    if ready:
        try:
            with open(pid_file, encoding='utf-8') as fh:
                state['server_pid'] = int(fh.read().strip())
        except (OSError, ValueError):
            pass
    if not ready:
        kill_tree(server.pid, 'python')
        tail = ''
        try:
            with open(state['server_log'], encoding='utf-8', errors='replace') as fh:
                tail = fh.read()[-1500:]
        except OSError:
            pass
        raise Fail(f'แอปไม่พร้อมใช้งานภายในเวลาที่รอ: {why}',
                   hint=f'ท้าย server.log:\n{tail}',
                   next_steps=[f'{state["python"]} test_api.py   # ตรวจว่าตัวแอปเองยังดีอยู่',
                               'control_pos.py app start'],
                   server_log=state['server_log'])

    devtools_port = cdp.free_port()
    browser_proc, browser_exe = cdp.launch(profile_dir, devtools_port)
    state['browser_pid'] = browser_proc.pid
    state['devtools_port'] = devtools_port
    state['browser'] = browser_exe
    try:
        page, target = cdp.attach(devtools_port, which='latest')
        state['main_target'] = target['id']
        page.close()
    except cdp.BrowserError:
        kill_tree(browser_proc.pid, 'msedge' if 'msedge' in browser_exe.lower() else 'chrome')
        kill_tree(server.pid, 'python')
        raise

    save_state(state)

    seeded = None
    if args.seed:
        seeded = seed_fixtures(state, apply_changes=True)

    emit({
        'ok': True,
        'command': 'app start',
        'run_dir': run_dir,
        'base_url': state['base_url'],
        'lan_url': state['lan_url'],
        'lan_mode': state['lan'],
        'server_pid': state['server_pid'],
        'browser_pid': state['browser_pid'],
        'devtools_port': devtools_port,
        'data_dir': data_dir,
        'evidence_dir': evidence_dir,
        'downloads_dir': downloads_dir,
        'app_version': state['app_version'],
        'git_commit': state['git_commit'],
        'seeded': seeded,
        'lan_account': account,
        'next': ['control_pos.py doctor',
                 'control_pos.py browser open --path /'],
    })


def cmd_app_stop(args):
    run_dir = resolve_run_dir(args.run_dir)
    state = load_state(run_dir)
    plan = [
        {'what': 'เซิร์ฟเวอร์ Flask', 'pid': state.get('server_pid'), 'image': 'python'},
        {'what': 'ตัวเรียกของ .venv', 'pid': state.get('launcher_pid'), 'image': 'python'},
        {'what': 'เบราว์เซอร์ headless', 'pid': state.get('browser_pid'),
         'image': 'msedge' if 'msedge' in (state.get('browser') or '').lower() else 'chrome'},
    ]
    plan = [p for i, p in enumerate(plan)
            if p['pid'] and p['pid'] not in [q['pid'] for q in plan[:i]]]
    removes = [state.get('profile_dir'), os.path.join(run_dir, 'scaffolding')]
    if args.dry_run:
        emit({
            'ok': True,
            'command': 'app stop',
            'dry_run': True,
            'would_stop': [{**p, 'running_as': process_image(p['pid'])} for p in plan],
            'would_remove': removes,
            'kept': {'evidence_dir': state.get('evidence_dir'),
                     'data_dir': state.get('data_dir'),
                     'server_log': state.get('server_log')},
            'next': ['control_pos.py app stop'],
        })

    stopped = [{**p, **kill_tree(p['pid'], p['image'])} for p in plan]
    removed, left_behind = [], []
    for path in removes:
        if not path or not os.path.isdir(path):
            continue
        # เบราว์เซอร์ที่เพิ่งถูกปิดยังถือไฟล์ใน profile อยู่อีกครู่ ลบรอบเดียวจึงไม่หมด
        for attempt in range(6):
            shutil.rmtree(path, ignore_errors=True)
            if not os.path.isdir(path):
                break
            time.sleep(0.3)
        (removed if not os.path.isdir(path) else left_behind).append(path)
    try:
        os.remove(CURRENT_FILE)
    except OSError:
        pass
    emit({
        'ok': True,
        'command': 'app stop',
        'stopped': stopped,
        'removed': removed,
        'left_behind': left_behind,
        'kept': {'evidence_dir': state.get('evidence_dir'),
                 'data_dir': state.get('data_dir'),
                 'server_log': state.get('server_log')},
        'note': 'หลักฐานและข้อมูลของการตรวจครั้งนี้ยังอยู่ ลบ run_dir ด้วยมือเมื่อไม่ต้องการแล้ว',
        'run_dir': run_dir,
        **({} if not left_behind else {
            'hint': 'โฟลเดอร์ที่ลบไม่หมดเป็นของเบราว์เซอร์ที่ยังปล่อยไฟล์ไม่เสร็จ ไม่กระทบหลักฐาน',
            'next': [f'ลบด้วยมือภายหลัง: {left_behind[0]}']}),
    })


# ── doctor ───────────────────────────────────────────────────────────────────
def cmd_doctor(args):
    run_dir = resolve_run_dir(args.run_dir)
    state = load_state(run_dir)
    checks = []

    def check(name, ok, detail, nxt=()):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail,
                       **({'next': list(nxt)} if nxt and not ok else {})})

    server_image = process_image(state.get('server_pid'))
    check('เซิร์ฟเวอร์ยังทำงานอยู่',
          (server_image or '').lower().startswith('python'),
          f"pid {state.get('server_pid')} เป็น {server_image}",
          ['control_pos.py app stop', 'control_pos.py app start'])

    owner = port_owner(state['port'])
    check('พอร์ตนี้เป็นของอินสแตนซ์ที่เปิดไว้เอง',
          owner == state.get('server_pid'),
          f"พอร์ต {state['port']} ถูกถือโดย pid {owner} ที่จดไว้คือ {state.get('server_pid')}",
          ['control_pos.py app stop',
           f"powershell -File stop_app.ps1 -Port {state['port']}   # ถ้ามีตัวอื่นค้างพอร์ตนี้"])

    # โหมด LAN บังคับเข้าสู่ระบบกับทุกคนรวมถึงเครื่องแม่ข่าย การตรวจจึงคาดคนละอย่างกัน
    # ตามโหมด และหน้าที่ใช้ดูเลขเวอร์ชันก็ต่างกัน เพราะ / ของโหมด LAN เด้งไป /login
    if state['lan']:
        try:
            with urllib.request.urlopen(f"{state['base_url']}/api/ping", timeout=5) as fh:
                check('เครื่องแม่ข่ายเองก็ต้องเข้าสู่ระบบในโหมด LAN', False,
                      f'/api/ping จาก 127.0.0.1 ตอบ {fh.status} ทั้งที่ยังไม่เข้าสู่ระบบ',
                      ['อ่าน serve และ require_login ใน app.py'])
        except urllib.error.HTTPError as exc:
            check('เครื่องแม่ข่ายเองก็ต้องเข้าสู่ระบบในโหมด LAN', exc.code == 401,
                  f'/api/ping จาก 127.0.0.1 ตอบ {exc.code}',
                  ['อ่าน serve และ require_login ใน app.py'])
        except Exception as exc:
            check('เครื่องแม่ข่ายเองก็ต้องเข้าสู่ระบบในโหมด LAN', False,
                  f'{type(exc).__name__}: {exc}',
                  ['control_pos.py app stop', 'control_pos.py app start --lan'])
        version_path, version_where = '/login', 'หน้าเข้าสู่ระบบ'
    else:
        try:
            ping = http_json(f"{state['base_url']}/api/ping")
            check('/api/ping ตอบ ok', ping.get('ok') is True, json.dumps(ping, ensure_ascii=False),
                  ['control_pos.py app stop', 'control_pos.py app start'])
        except Exception as exc:
            check('/api/ping ตอบ ok', False, f'{type(exc).__name__}: {exc}',
                  ['control_pos.py app stop', 'control_pos.py app start'])
        version_path, version_where = '/', 'หน้าแอป'

    try:
        with urllib.request.urlopen(f"{state['base_url']}{version_path}", timeout=5) as fh:
            page = fh.read().decode('utf-8', 'replace')
        version = (re.search(r'เวอร์ชัน\s+([0-9][0-9.]*)', page) or [None, None])[1]
        check('หน้าเว็บคือแอปตัวนี้และเป็นรุ่นที่คาดไว้',
              'การปรับปรุงการกำหนดตำแหน่ง' in page and version == state.get('app_version'),
              f"เจอรุ่น {version} ใน {version_where} ({version_path}) "
              f"ค่าที่คาดจาก app.py คือ {state.get('app_version')}",
              ['control_pos.py app stop', 'control_pos.py app start'])
    except Exception as exc:
        check('หน้าเว็บคือแอปตัวนี้และเป็นรุ่นที่คาดไว้', False, f'{type(exc).__name__}: {exc}',
              ['control_pos.py app stop', 'control_pos.py app start'])

    db_path = os.path.join(state['data_dir'], 'pos_restructure.db')
    real_db = os.path.join(REPO_DIR, 'pos_restructure.db')
    check('ฐานข้อมูลที่ขับอยู่เป็นของการตรวจ ไม่ใช่ข้อมูลจริง',
          os.path.isfile(db_path) and os.path.abspath(db_path) != os.path.abspath(real_db),
          f'ฐานข้อมูลของอินสแตนซ์ {db_path}',
          ['control_pos.py app start'])

    browser_image = process_image(state.get('browser_pid'))
    expect = 'msedge' if 'msedge' in (state.get('browser') or '').lower() else 'chrome'
    check('เบราว์เซอร์ที่ใช้ขับยังทำงานอยู่',
          (browser_image or '').lower().startswith(expect),
          f"pid {state.get('browser_pid')} เป็น {browser_image}",
          ['control_pos.py app stop', 'control_pos.py app start'])

    try:
        pages = cdp.page_targets(state['devtools_port'])
        ids = [p['id'] for p in pages]
        check('หน้าหลักของการตรวจยังเปิดอยู่',
              state.get('main_target') in ids,
              f"target ที่จดไว้ {state.get('main_target')} หน้าที่เปิดอยู่ {len(ids)} หน้า",
              ['control_pos.py app stop', 'control_pos.py app start'])
    except cdp.BrowserError as exc:
        check('หน้าหลักของการตรวจยังเปิดอยู่', False, str(exc),
              ['control_pos.py app stop', 'control_pos.py app start'])

    if state['lan']:
        try:
            with urllib.request.urlopen(f"{state['lan_url']}/api/ping", timeout=5) as fh:
                body = fh.read().decode('utf-8', 'replace')
            check('เส้นทางเครื่องในวง LAN ถูกปิดไว้จนกว่าจะเข้าสู่ระบบ', False,
                  f'/api/ping จาก {state["lan_url"]} ตอบ 200 ทั้งที่ยังไม่เข้าสู่ระบบ: {body}',
                  ['อ่าน require_login ใน app.py'])
        except urllib.error.HTTPError as exc:
            check('เส้นทางเครื่องในวง LAN ถูกปิดไว้จนกว่าจะเข้าสู่ระบบ', exc.code == 401,
                  f'/api/ping จาก {state["lan_url"]} ตอบ {exc.code}',
                  ['อ่าน require_login ใน app.py'])
        except Exception as exc:
            check('เส้นทางเครื่องในวง LAN ถูกปิดไว้จนกว่าจะเข้าสู่ระบบ', False,
                  f'{type(exc).__name__}: {exc}',
                  ['control_pos.py app stop', 'control_pos.py app start --lan'])

    failed = [c['check'] for c in checks if not c['ok']]
    emit({
        'ok': not failed,
        'command': 'doctor',
        'run_dir': run_dir,
        'base_url': state['base_url'],
        'lan_url': state['lan_url'],
        'lan_mode': state['lan'],
        'evidence_dir': state['evidence_dir'],
        'downloads_dir': state.get('downloads_dir'),
        'app_version': state['app_version'],
        'git_commit': state['git_commit'],
        'checks': checks,
        'failed': failed,
        **({} if not failed else {
            'error': f'ตรวจไม่ผ่าน {len(failed)} ข้อ อินสแตนซ์นี้ยังขับต่อไม่ได้',
            'hint': 'ดูรายละเอียดในแต่ละข้อที่ ok เป็น false',
            'next': ['control_pos.py app stop', 'control_pos.py app start'],
        }),
    }, 0 if not failed else 1)


# ── api ──────────────────────────────────────────────────────────────────────
WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def base_for(state, origin):
    if origin == 'lan':
        if not state['lan']:
            raise Fail('อินสแตนซ์นี้เปิดแบบเครื่องแม่ข่ายอย่างเดียว ยิงแบบเครื่องในวง LAN ไม่ได้',
                       hint='โหมดเครื่องในวงต้องให้แอป bind 0.0.0.0 แล้วเรียกผ่าน IP ของเครื่อง',
                       next_steps=['control_pos.py app stop',
                                   'control_pos.py app start --lan'])
        return state['lan_url']
    return state['base_url']


def opener_for(state, origin, fresh=False):
    """คุกกี้เซสชันเก็บเป็นไฟล์ใน run_dir คำสั่ง api จึงเรียกต่อกันในเซสชันเดียวได้

    ผลข้างเคียงคือเมื่อเข้าสู่ระบบไปแล้ว คำขอถัดไปจะไม่ได้ 401 อีก การพิสูจน์ว่า
    เครื่องในวงที่ยังไม่เข้าสู่ระบบถูกปฏิเสธ ต้องสั่งด้วย --fresh เพื่อทิ้งคุกกี้ก่อน
    """
    jar_path = os.path.join(state['run_dir'], f'cookies-{origin}.txt')
    if fresh and os.path.isfile(jar_path):
        os.remove(jar_path)
    jar = http.cookiejar.LWPCookieJar(jar_path)
    if os.path.isfile(jar_path):
        jar.load(ignore_discard=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    return opener, jar


def local_opener(state):
    """opener สำหรับคำขอจากเครื่องแม่ข่าย ที่เข้าสู่ระบบให้เองเมื่ออินสแตนซ์เป็นโหมด LAN

    โหมด LAN บังคับเข้าสู่ระบบกับทุกคนรวมถึงเครื่องแม่ข่าย คำสั่งที่ต้องเขียนข้อมูล
    อย่าง data seed กับ data reset จึงต้องมีเซสชันก่อน
    """
    opener, jar = opener_for(state, 'local')
    if state['lan'] and send(opener, state['base_url'] + '/api/ping', 'GET')[0] == 401:
        status, body, text = send(opener, state['base_url'] + '/login', 'POST',
                                  {'username': LAN_ACCOUNT['username'],
                                   'password': LAN_ACCOUNT['password']})
        if status != 200:
            raise Fail(f"เข้าสู่ระบบเป็น {LAN_ACCOUNT['username']} จากเครื่องแม่ข่ายไม่สำเร็จ ({status})",
                       hint=json.dumps(body or text, ensure_ascii=False),
                       next_steps=['control_pos.py users list',
                                   'control_pos.py app stop', 'control_pos.py app start --lan'])
        jar.save(ignore_discard=True)
    return opener, jar


def send(opener, url, method, payload=None, timeout=20.0):
    data = None
    headers = {'Accept': 'application/json'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=timeout) as fh:
            status, body = fh.status, fh.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read().decode('utf-8', 'replace')
    except urllib.error.URLError as exc:
        raise Fail(f'ต่อ {url} ไม่ได้: {exc.reason}',
                   hint='อินสแตนซ์อาจถูกปิดไปแล้ว',
                   next_steps=['control_pos.py doctor', 'control_pos.py app start'])
    try:
        return status, json.loads(body), None
    except ValueError:
        return status, None, body[:4000]


def cmd_api(args):
    run_dir = resolve_run_dir(args.run_dir)
    state = load_state(run_dir)
    method = args.method.upper()
    path = url_path(args.path)
    base = base_for(state, args.origin)
    url = base + path

    payload = None
    if args.data:
        raw = args.data
        if raw.startswith('@'):
            try:
                with open(raw[1:], encoding='utf-8') as fh:
                    raw = fh.read()
            except OSError as exc:
                raise Fail(f'อ่านไฟล์ข้อมูล {raw[1:]} ไม่ได้: {exc}',
                           next_steps=['ตรวจเส้นทางไฟล์ แล้วสั่งซ้ำ'])
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise Fail(f'--data ไม่ใช่ JSON ที่อ่านได้: {exc}',
                       hint='ใส่เป็น JSON เช่น --data \'{"p4_status":"อนุมัติ"}\' หรือ --data @file.json',
                       next_steps=['control_pos.py api --help'])

    if args.dry_run:
        emit({'ok': True, 'command': 'api', 'dry_run': True, 'method': method, 'url': url,
              'origin': args.origin, 'fresh': bool(args.fresh),
              'login_as': args.login.split(':', 1)[0] if args.login else None,
              'body': payload,
              'note': 'ยังไม่ได้ส่งคำขอนี้ สั่งซ้ำโดยไม่ใส่ --dry-run จึงจะส่งจริง'})

    opener, jar = opener_for(state, args.origin, fresh=args.fresh)
    login_result = None
    if args.login:
        if ':' not in args.login:
            raise Fail('--login ต้องเป็นรูป ชื่อผู้ใช้งาน:รหัสผ่าน',
                       next_steps=['control_pos.py api --help'])
        user, password = args.login.split(':', 1)
        status, body, text = send(opener, base + '/login', 'POST',
                                  {'username': user, 'password': password})
        login_result = {'status': status, 'json': body, 'text': text}
        if status != 200:
            jar.save(ignore_discard=True)
            emit({'ok': False, 'command': 'api', 'error': f'เข้าสู่ระบบเป็น {user} ไม่สำเร็จ',
                  'hint': json.dumps(body or text, ensure_ascii=False),
                  'login': login_result,
                  'next': ['control_pos.py users list',
                           'control_pos.py users add --username <ชื่อ> --display <ชื่อแสดงผล> '
                           '--password <รหัสผ่าน>']}, 1)

    status, body, text = send(opener, url, method, payload)
    jar.save(ignore_discard=True)
    ok = 200 <= status < 300
    out = {'ok': ok, 'command': 'api', 'method': method, 'url': url, 'origin': args.origin,
           'status': status, 'json': body, 'text': text, 'login': login_result,
           'cookie_jar': jar.filename}
    if not ok:
        out['error'] = f'{method} {path} ตอบ {status}'
        out['hint'] = (body or {}).get('error') if isinstance(body, dict) else text
        if status == 401:
            out['next'] = ['control_pos.py api GET /api/positions --from lan --login <ชื่อ>:<รหัสผ่าน>']
        elif status == 403 and method == 'DELETE' and path == '/api/positions':
            out['next'] = ['control_pos.py api DELETE /api/positions   # ลบทั้งหมดทำได้จากเครื่องแม่ข่ายเท่านั้น']
        elif status == 404:
            out['next'] = ['control_pos.py api GET /api/positions   # ดู id ที่มีอยู่จริง']
        else:
            out['next'] = ['control_pos.py doctor']
    emit(out, 0 if ok else 1)


# ── users ────────────────────────────────────────────────────────────────────
def run_db(state):
    """เปิดฐานข้อมูลของอินสแตนซ์ และปฏิเสธถ้าไม่ได้อยู่ใน run_dir

    ด่านนี้คือสิ่งที่กันไม่ให้คำสั่ง users ไปแก้บัญชีจริงของหน่วยงาน
    """
    db_path = os.path.abspath(os.path.join(state['data_dir'], 'pos_restructure.db'))
    if os.path.commonpath([db_path, os.path.abspath(state['run_dir'])]) != os.path.abspath(state['run_dir']):
        raise Fail(f'ฐานข้อมูล {db_path} อยู่นอกโฟลเดอร์ของการตรวจ จึงไม่แตะให้',
                   hint='คำสั่ง users แก้ได้เฉพาะฐานข้อมูลของอินสแตนซ์ที่การตรวจเปิดเอง',
                   next_steps=['control_pos.py app start'])
    if not os.path.isfile(db_path):
        raise Fail(f'ไม่พบฐานข้อมูล {db_path}',
                   next_steps=['control_pos.py app start'])
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con, db_path


def cmd_users(args):
    run_dir = resolve_run_dir(args.run_dir)
    state = load_state(run_dir)
    con, db_path = run_db(state)
    try:
        if args.users_cmd == 'list':
            rows = [dict(r) for r in con.execute(
                'SELECT id, username, display_name, created FROM users ORDER BY id')]
            emit({'ok': True, 'command': 'users list', 'db': db_path,
                  'count': len(rows), 'users': rows})

        if args.users_cmd == 'add':
            sys.path.insert(0, REPO_DIR)
            from werkzeug.security import generate_password_hash
            if not re.fullmatch(r'[a-z0-9._-]{3,32}', args.username):
                raise Fail(f'ชื่อผู้ใช้งาน {args.username!r} ไม่ผ่านกติกาของแอป',
                           hint='ใช้ได้เฉพาะ a-z 0-9 . _ - ยาว 3 ถึง 32 ตัว',
                           next_steps=['control_pos.py users add --username somchai '
                                       '--display "สมชาย ใจดี" --password verify-pass-1'])
            if len(args.password) < 8:
                raise Fail('รหัสผ่านสั้นกว่า 8 ตัว ซึ่งเป็นกติกาเดียวกับ manage_users.py',
                           next_steps=['สั่งซ้ำด้วยรหัสผ่านยาวอย่างน้อย 8 ตัว'])
            if args.dry_run:
                emit({'ok': True, 'command': 'users add', 'dry_run': True, 'db': db_path,
                      'would_add': {'username': args.username, 'display_name': args.display},
                      'note': 'ยังไม่ได้เพิ่มบัญชี สั่งซ้ำโดยไม่ใส่ --dry-run จึงจะเพิ่มจริง'})
            existing = con.execute('SELECT id FROM users WHERE username=?', [args.username]).fetchone()
            if existing:
                raise Fail(f'มีบัญชี {args.username} อยู่แล้วในฐานข้อมูลของการตรวจ',
                           next_steps=['control_pos.py users list',
                                       f'control_pos.py users remove --username {args.username} --apply'])
            con.execute(
                'INSERT INTO users (username, display_name, password_hash, created) VALUES (?,?,?,?)',
                [args.username, args.display, generate_password_hash(args.password),
                 datetime.now().strftime('%Y-%m-%dT%H:%M:%S')])
            con.commit()
            emit({'ok': True, 'command': 'users add', 'db': db_path,
                  'added': {'username': args.username, 'display_name': args.display},
                  'next': [f'control_pos.py api GET /api/positions --from lan '
                           f'--login {args.username}:<รหัสผ่าน>']})

        if args.users_cmd == 'remove':
            row = con.execute('SELECT id, username, display_name FROM users WHERE username=?',
                              [args.username]).fetchone()
            if not row:
                raise Fail(f'ไม่พบบัญชี {args.username} ในฐานข้อมูลของการตรวจ',
                           next_steps=['control_pos.py users list'])
            if not args.apply:
                emit({'ok': True, 'command': 'users remove', 'dry_run': True, 'db': db_path,
                      'would_remove': dict(row),
                      'note': 'คำสั่งนี้เป็น dry-run โดยค่าเริ่มต้น ใส่ --apply จึงจะลบจริง',
                      'next': [f'control_pos.py users remove --username {args.username} --apply']})
            con.execute('DELETE FROM users WHERE username=?', [args.username])
            con.commit()
            emit({'ok': True, 'command': 'users remove', 'db': db_path, 'removed': dict(row),
                  'note': 'ชื่อผู้บันทึกบนคำขอที่บัญชีนี้สร้างไว้ไม่เปลี่ยน (docs/adr/0002)'})
    finally:
        con.close()


# ── data ─────────────────────────────────────────────────────────────────────
def fixtures():
    return [
        {
            'sec1_rows': json.dumps([{
                's1_type': 'วิชาการ', 's1_level': 'ชำนาญการพิเศษ', 's1_no': '001',
                's1_group': 'กลุ่มสรรหาและบรรจุแต่งตั้ง', 's1_division': 'กองการเจ้าหน้าที่',
                's1_dept': 'สำนักงานปลัดสำนักนายกรัฐมนตรี'}], ensure_ascii=False),
            'sec2_rows': json.dumps([{
                's2_type': 'ทั่วไป', 's2_level': 'อาวุโส', 's2_no': '101',
                's2_group': 'กลุ่มบริหารงานบุคคล', 's2_division': 'กองการเจ้าหน้าที่',
                's2_dept': 'สำนักงานปลัดสำนักนายกรัฐมนตรี'}], ensure_ascii=False),
            'sec3_rows': json.dumps([{
                's3_type': 'ทั่วไป', 's3_level': 'ปฏิบัติงาน / ชำนาญงาน', 's3_no': '201',
                's3_group': '', 's3_division': 'กองการเจ้าหน้าที่', 's3_dept': ''}],
                ensure_ascii=False),
            'p4_round': '3/2567', 'p4_date': '2024-07-15', 'p4_resolution': 'เห็นควรอนุมัติ',
            'p4_status': 'อนุมัติ', 'p4_effective': '2024-08-01', 'p4_note': SEED_MARKER,
            'p5_salary': '45000.50', 'p5_round': '3/2567', 'p5_date': '2024-07-15',
        },
        {
            'sec1_rows': json.dumps([{
                's1_type': 'ทั่วไป', 's1_level': 'อาวุโส', 's1_no': '002',
                's1_group': 'กลุ่มงานคลัง', 's1_division': 'กองคลัง',
                's1_dept': 'กรมประชาสัมพันธ์'}], ensure_ascii=False),
            'sec2_rows': '[]',
            'sec3_rows': '[]',
            'p4_round': '4/2567', 'p4_date': '2024-09-02', 'p4_resolution': 'รอพิจารณาเพิ่มเติม',
            'p4_status': 'อยู่ระหว่างพิจารณา', 'p4_effective': '', 'p4_note': SEED_MARKER,
            'p5_salary': '28000', 'p5_round': '', 'p5_date': '',
        },
    ]


def seed_fixtures(state, apply_changes):
    """ใส่คำขอตั้งต้นผ่าน API เดียวกับที่หน้าเว็บใช้ ทำซ้ำได้ไม่เกิดของซ้ำ"""
    opener, jar = local_opener(state)
    status, existing, _ = send(opener, state['base_url'] + '/api/positions', 'GET')
    have = {r.get('p4_round') for r in (existing or []) if r.get('p4_note') == SEED_MARKER}
    todo = [f for f in fixtures() if f['p4_round'] not in have]
    if not apply_changes:
        return {'dry_run': True, 'existing_fixtures': sorted(have),
                'would_add': [f['p4_round'] for f in todo]}
    created = []
    for fixture in todo:
        status, body, text = send(opener, state['base_url'] + '/api/positions', 'POST', fixture)
        if status != 201:
            raise Fail(f'ใส่ข้อมูลตั้งต้นไม่สำเร็จ POST /api/positions ตอบ {status}',
                       hint=json.dumps(body or text, ensure_ascii=False),
                       next_steps=['control_pos.py doctor'])
        created.append({'id': body['id'], 'p4_round': fixture['p4_round'],
                        'p4_status': fixture['p4_status']})
    return {'created': created, 'already_present': sorted(have)}


def cmd_data(args):
    run_dir = resolve_run_dir(args.run_dir)
    state = load_state(run_dir)

    if args.data_cmd == 'seed':
        result = seed_fixtures(state, apply_changes=not args.dry_run)
        emit({'ok': True, 'command': 'data seed', 'dry_run': bool(args.dry_run), **result,
              'next': ['control_pos.py api GET /api/positions']})

    if args.data_cmd == 'reset':
        opener, _ = local_opener(state)
        status, rows, text = send(opener, state['base_url'] + '/api/positions', 'GET')
        uploads = os.path.join(state['data_dir'], 'uploads')
        files = sorted(os.listdir(uploads)) if os.path.isdir(uploads) else []
        if not args.apply:
            emit({'ok': True, 'command': 'data reset', 'dry_run': True,
                  'would_delete_requests': len(rows or []),
                  'would_delete_request_ids': [r['id'] for r in (rows or [])],
                  'would_delete_upload_files': files,
                  'scope': state['data_dir'],
                  'note': 'คำสั่งนี้เป็น dry-run โดยค่าเริ่มต้น ใส่ --apply จึงจะลบจริง '
                          'และลบเฉพาะข้อมูลของอินสแตนซ์นี้ ไม่แตะข้อมูลจริงในโปรเจกต์',
                  'next': ['control_pos.py data reset --apply']})
        status, body, text = send(opener, state['base_url'] + '/api/positions', 'DELETE')
        if status != 200:
            raise Fail(f'DELETE /api/positions ตอบ {status}',
                       hint=json.dumps(body or text, ensure_ascii=False),
                       next_steps=['control_pos.py doctor'])
        # ไฟล์ที่อัปโหลดแล้วแต่คำขอยังไม่ถูกบันทึกไม่ได้ถูกอ้างจากรายการไหน API จึงไม่ลบให้
        # (แบบเดียวกับที่ cleanup_orphans.py มีไว้สำหรับข้อมูลจริง) ที่นี่ทั้งโฟลเดอร์เป็น
        # ของอินสแตนซ์นี้เท่านั้น จึงกวาดที่เหลือออกให้หมดเพื่อให้เริ่มใหม่จากสภาพว่างจริงๆ
        orphans = []
        for name in (sorted(os.listdir(uploads)) if os.path.isdir(uploads) else []):
            target = os.path.join(uploads, name)
            if os.path.isfile(target):
                os.remove(target)
                orphans.append(name)
        left = sorted(os.listdir(uploads)) if os.path.isdir(uploads) else []
        emit({'ok': True, 'command': 'data reset', 'deleted_requests': len(rows or []),
              'upload_files_before': files, 'deleted_orphan_files': orphans,
              'upload_files_after': left,
              'scope': state['data_dir'],
              'next': ['control_pos.py data seed']})


# ── browser ──────────────────────────────────────────────────────────────────
RESOLVE_JS = r"""
(() => {
  // ช่องแนบไฟล์ของแอปนี้ถูกซ่อนไว้ด้วย display:none แบบที่หน้าเว็บสมัยนี้ทำกัน
  // คำสั่งที่ต้องแตะช่องแบบนั้นจึงส่ง anyVis มาเพื่อปิดการกรองด้วยการมองเห็น
  const vis = el => ARGS.anyVis ? true : !!el.getClientRects().length;
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const label = el => norm(el.innerText || el.value || el.getAttribute('aria-label') || '');
  let list = [], how = '';
  if (ARGS.select) {
    list = [...document.querySelectorAll(ARGS.select)].filter(vis);
    how = 'select';
  } else {
    const cand = [...document.querySelectorAll(
      'button,a,[role=button],[aria-label],summary,label,th,td,option,' +
      'input[type=submit],input[type=button],.tbtn')].filter(vis);
    const want = norm(ARGS.text);
    for (const [name, test] of [['text-exact', s => s === want],
                                ['text-prefix', s => s.startsWith(want)],
                                ['text-contains', s => s.includes(want)]]) {
      list = cand.filter(el => test(label(el)));
      how = name;
      if (list.length) break;
    }
  }
  const describe = el => ({
    tag: el.tagName.toLowerCase(), id: el.id || null, name: el.name || null,
    type: el.type || null, text: label(el).slice(0, 120),
    disabled: !!el.disabled, hidden: !vis(el),
    options: el.tagName === 'SELECT' ? [...el.options].map(o => o.value) : undefined,
  });
  return {
    how, count: list.length,
    all: list.slice(0, 12).map(describe),
  };
})()
"""

MARK_JS = r"""
(() => {
  const vis = el => ARGS.anyVis ? true : !!el.getClientRects().length;
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const label = el => norm(el.innerText || el.value || el.getAttribute('aria-label') || '');
  let list = [];
  if (ARGS.select) {
    list = [...document.querySelectorAll(ARGS.select)].filter(vis);
  } else {
    const cand = [...document.querySelectorAll(
      'button,a,[role=button],[aria-label],summary,label,th,td,option,' +
      'input[type=submit],input[type=button],.tbtn')].filter(vis);
    const want = norm(ARGS.text);
    for (const test of [s => s === want, s => s.startsWith(want), s => s.includes(want)]) {
      list = cand.filter(el => test(label(el)));
      if (list.length) break;
    }
  }
  const el = list[ARGS.nth];
  if (!el) return null;
  el.scrollIntoView({block: 'center', inline: 'center'});
  window.__verifyTarget = el;
  const r = el.getBoundingClientRect();
  return {
    tag: el.tagName.toLowerCase(), id: el.id || null, name: el.name || null,
    type: el.type || null, text: label(el).slice(0, 120), disabled: !!el.disabled,
    value: 'value' in el ? String(el.value) : null,
    options: el.tagName === 'SELECT' ? [...el.options].map(o => o.value) : null,
    x: r.left + r.width / 2, y: r.top + r.height / 2,
    width: r.width, height: r.height,
  };
})()
"""

RECT_JS = r"""
(() => {
  const el = window.__verifyTarget;
  if (!el) return null;
  const b = el.getBoundingClientRect();
  return {x: b.left + b.width / 2, y: b.top + b.height / 2,
          width: b.width, height: b.height,
          scroll_y: window.scrollY, viewport_h: window.innerHeight,
          viewport_w: window.innerWidth};
})()
"""

AIM_SCROLL_JS = "(window.__verifyTarget && " \
                "window.__verifyTarget.scrollIntoView({block: 'center', inline: 'center'}), null)"


def aim(page, element):
    """จุดที่จะคลิกจริง วัดซ้ำจนค่าหยุดนิ่งและอยู่ในกรอบที่มองเห็น

    ตำแหน่งที่วัดพร้อมกับคำสั่งเลื่อนจออาจเป็นค่าก่อนเลื่อน แล้วการคลิกจะไปลงที่ว่าง
    นอกจอ ซึ่งไม่เกิดอะไรขึ้นเลยและอ่านจากผลไม่ออกว่าพลาดเพราะอะไร
    """
    previous = None
    for attempt in range(12):
        rect = page.evaluate(RECT_JS)
        if rect is None:
            raise Fail('องค์ประกอบที่เล็งไว้หายไปจากหน้าเว็บแล้ว',
                       next_steps=['control_pos.py browser read'])
        stable = previous is not None and abs(rect['y'] - previous['y']) < 0.5 \
            and abs(rect['x'] - previous['x']) < 0.5
        inside = 0 <= rect['y'] <= rect['viewport_h'] and 0 <= rect['x'] <= rect['viewport_w']
        if stable and inside:
            return rect
        if stable and not inside:
            page.evaluate(AIM_SCROLL_JS)
        previous = rect
        time.sleep(0.08)
    if previous and 0 <= previous['y'] <= previous['viewport_h']:
        return previous
    raise Fail(
        f"เลื่อน {element.get('text') or element.get('id')} เข้ามาในกรอบที่มองเห็นไม่ได้",
        hint=f'ตำแหน่งล่าสุด {previous}',
        next_steps=['control_pos.py browser shot --name aim-failed --full-page'],
        element=element)


def click_point(page, rect):
    for kind in ('mousePressed', 'mouseReleased'):
        page.call('Input.dispatchMouseEvent', type=kind, x=rect['x'], y=rect['y'],
                  button='left', clickCount=1)


AFTER_JS = r"""
(() => {
  const txt = id => {
    const el = document.getElementById(id);
    return el ? el.textContent.replace(/\s+/g, ' ').trim() : null;
  };
  const errors = document.getElementById('form-errors');
  const toast = document.getElementById('myToast');
  return {
    url: location.href,
    toast: {shown: !!(toast && toast.classList.contains('show')), text: txt('toast-msg')},
    form_errors: {shown: !!(errors && !errors.hidden), text: txt('form-errors')},
    open_modal: [...document.querySelectorAll('.modal.show .modal-title')]
                  .map(e => e.textContent.trim()),
    active_tab: (document.querySelector('.tbtn.active') || {}).textContent
                  ? document.querySelector('.tbtn.active').textContent.replace(/\s+/g,' ').trim()
                  : null,
    active_element: document.activeElement
                      ? (document.activeElement.id || document.activeElement.tagName.toLowerCase())
                      : null,
  };
})()
"""

KEYS = {
    'Enter': (13, 'Enter', '\r'), 'Escape': (27, 'Escape', ''), 'Tab': (9, 'Tab', ''),
    'Backspace': (8, 'Backspace', ''), 'Delete': (46, 'Delete', ''),
    'ArrowDown': (40, 'ArrowDown', ''), 'ArrowUp': (38, 'ArrowUp', ''),
    'Space': (32, 'Space', ' '),
}


def open_page(state, which='main'):
    try:
        page, target = cdp.attach(state['devtools_port'], state.get('main_target'), which)
    except cdp.BrowserError as exc:
        raise Fail(str(exc), hint=exc.hint, next_steps=exc.next_steps or
                   ['control_pos.py doctor', 'control_pos.py app start'])
    page.call('Page.enable')
    page.call('Runtime.enable')
    # Export CSV กับ Export JSON ของหน้าเว็บสร้างไฟล์แล้วสั่งดาวน์โหลด เบราว์เซอร์ headless
    # ปฏิเสธการดาวน์โหลดโดยค่าเริ่มต้น ถ้าไม่เปิดทางให้ จะพิสูจน์สองปุ่มนั้นไม่ได้เลย
    folder = state.get('downloads_dir')
    if folder:
        os.makedirs(folder, exist_ok=True)
        try:
            page.call('Browser.setDownloadBehavior', behavior='allow', downloadPath=folder)
        except cdp.BrowserError:
            try:
                page.call('Page.setDownloadBehavior', behavior='allow', downloadPath=folder)
            except cdp.BrowserError:
                pass
    return page, target


def locate(page, args, required=True, any_visibility=False):
    if not args.select and not args.text:
        raise Fail('ต้องระบุ --select (CSS) หรือ --text (ข้อความที่ผู้ใช้เห็น) อย่างน้อยหนึ่งอย่าง',
                   next_steps=['control_pos.py browser read   # ดูว่ามีปุ่มอะไรให้กดบ้าง'])
    deadline = time.monotonic() + args.timeout / 1000.0
    found = None
    while True:
        found = page.evaluate(MARK_JS, {'select': args.select, 'text': args.text,
                                        'nth': args.nth, 'anyVis': any_visibility})
        if found or time.monotonic() > deadline:
            break
        time.sleep(0.1)
    if not found and required:
        survey = page.evaluate(RESOLVE_JS, {'select': args.select, 'text': args.text,
                                            'anyVis': any_visibility})
        raise Fail(
            f'หาองค์ประกอบที่ตรงกับ {args.select or args.text!r} ลำดับที่ {args.nth} ไม่เจอ '
            f'ภายใน {args.timeout} มิลลิวินาที',
            hint=f'ค้นด้วยวิธี {survey["how"]} เจอ {survey["count"]} รายการ',
            next_steps=['control_pos.py browser read   # ดูข้อความและปุ่มที่มีอยู่จริงบนหน้านี้',
                        'control_pos.py browser shot --name where-am-i'],
            candidates=survey['all'],
        )
    return found


def cmd_browser_open(args):
    state = load_state(resolve_run_dir(args.run_dir))
    base = base_for(state, args.origin)
    url = base + url_path(args.path)
    page, target = open_page(state)
    try:
        page.call('Page.navigate', url=url)
        deadline = time.monotonic() + args.timeout / 1000.0
        ready, detail = False, ''
        while time.monotonic() < deadline:
            info = page.evaluate("""({
                url: location.href, title: document.title,
                state: document.readyState,
                badge: (document.getElementById('mode-badge')||{}).innerText || null,
                login_form: !!document.getElementById('login-form'),
            })""")
            detail = info
            if info['state'] == 'complete' and (
                    (info['badge'] or '').strip().startswith(READY_BADGE) or info['login_form']
                    or args.no_wait):
                ready = True
                break
            time.sleep(0.15)
        out = {'ok': ready, 'command': 'browser open', 'url': url, 'origin': args.origin,
               'page': detail, 'target': target['id']}
        if not ready:
            out['error'] = f'หน้า {url} ยังไม่พร้อมภายใน {args.timeout} มิลลิวินาที'
            out['hint'] = (f'หน้าแอปพร้อมเมื่อป้ายสถานะขึ้น "{READY_BADGE}" '
                           'หน้าเข้าสู่ระบบพร้อมเมื่อมีฟอร์ม login-form')
            out['next'] = ['control_pos.py doctor',
                           'control_pos.py browser shot --name open-stuck']
        emit(out, 0 if ready else 1)
    finally:
        page.close()


def cmd_browser_click(args):
    state = load_state(resolve_run_dir(args.run_dir))
    page, _ = open_page(state)
    try:
        el = locate(page, args)
        if el['disabled']:
            raise Fail(f"องค์ประกอบ {el['text'] or el['id']} ถูกปิดการใช้งานอยู่ จึงคลิกไม่ได้",
                       hint='ปุ่มที่ถูกปิดมักรอให้กรอกช่องที่จำเป็นให้ครบก่อน',
                       next_steps=['control_pos.py browser read --select "#form-errors"'],
                       element=el)
        rect = aim(page, el)
        click_point(page, rect)
        time.sleep(args.settle / 1000.0)
        emit({'ok': True, 'command': 'browser click', 'method': 'Input.dispatchMouseEvent',
              'element': el, 'clicked_at': {'x': rect['x'], 'y': rect['y']},
              'after': page.evaluate(AFTER_JS)})
    finally:
        page.close()


FILL_JS = r"""
(() => {
  const el = window.__verifyTarget;
  if (!el) return {ok: false, error: 'no target'};
  const value = ARGS.value;
  if (el.tagName === 'SELECT') {
    const opts = [...el.options].map(o => o.value);
    if (!opts.includes(value)) return {ok: false, error: 'no-such-option', options: opts};
    el.value = value;
  } else {
    el.value = value;
  }
  el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true}));
  return {ok: true, value: String(el.value)};
})()
"""

SET_VALUE_TAGS = {'date', 'time', 'month', 'week', 'color', 'range'}


def cmd_browser_fill(args):
    state = load_state(resolve_run_dir(args.run_dir))
    page, _ = open_page(state)
    try:
        el = locate(page, args)
        if el['type'] == 'file':
            raise Fail('ช่องแนบไฟล์ตั้งค่าด้วย fill ไม่ได้',
                       next_steps=[f'control_pos.py browser attach --select '
                                   f'"{args.select or "#file_attach"}" --file <เส้นทางไฟล์>'])
        typed = el['tag'] not in ('select',) and (el['type'] or 'text') not in SET_VALUE_TAGS
        if typed:
            click_point(page, aim(page, el))
            for kind in ('keyDown', 'keyUp'):  # ctrl+a เลือกค่าเดิมทั้งหมดก่อนพิมพ์ทับ
                page.call('Input.dispatchKeyEvent', type=kind, modifiers=2, key='a',
                          code='KeyA', windowsVirtualKeyCode=65)
            if args.value == '':
                for kind in ('keyDown', 'keyUp'):
                    page.call('Input.dispatchKeyEvent', type=kind, key='Delete',
                              code='Delete', windowsVirtualKeyCode=46)
            else:
                page.call('Input.insertText', text=args.value)
            method = 'typed'
            result = {'ok': True}
        else:
            # <select> กับ <input type=date> เปิดหน้าต่างเลือกของระบบปฏิบัติการ ซึ่งไม่ได้อยู่
            # ในหน้าเว็บ จึงตั้งค่าแล้วยิง input กับ change ให้เหมือนที่เบราว์เซอร์ทำหลังผู้ใช้เลือก
            result = page.evaluate(FILL_JS, {'value': args.value})
            method = 'set-value+events'
            if not result.get('ok') and result.get('error') == 'no-such-option':
                raise Fail(f'ตัวเลือก {args.value!r} ไม่มีใน {el["id"] or el["name"]}',
                           hint=f'ตัวเลือกที่มีคือ {result["options"]}',
                           next_steps=[f'control_pos.py browser fill --select '
                                       f'"{args.select}" --value "{result["options"][1]}"'],
                           element=el)
        time.sleep(args.settle / 1000.0)
        readback = page.evaluate('window.__verifyTarget ? String(window.__verifyTarget.value) : null')
        ok = readback == args.value
        out = {'ok': ok, 'command': 'browser fill', 'method': method, 'element': el,
               'wanted': args.value, 'value_now': readback}
        if not ok:
            out['error'] = f'กรอกแล้วค่าในช่องเป็น {readback!r} ไม่ใช่ {args.value!r}'
            out['hint'] = 'หน้าเว็บอาจตัดช่องว่างหรือจัดรูปแบบค่าให้ใหม่'
            out['next'] = ['control_pos.py browser read --expr '
                           f'"document.querySelector({json.dumps(args.select or "")}).value"']
        emit(out, 0 if ok else 1)
    finally:
        page.close()


MINIMAL_PDF = (b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
               b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
               b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n'
               b'trailer<</Root 1 0 R>>\n%%EOF\n')


def sample_file(state, kind):
    """ไฟล์ตัวอย่างสำหรับทดสอบการแนบ เป็นของประกอบการตรวจ ไม่ใช่ข้อมูลจริง

    วางไว้ใน <run_dir>/scaffolding/ ซึ่ง app stop ลบทิ้งให้ แอปตรวจชนิดไฟล์จากนามสกุล
    ไฟล์จึงไม่ต้องเป็นเอกสารจริง และ sample.txt ใช้พิสูจน์ทางที่ต้องถูกปฏิเสธ
    """
    folder = os.path.join(state['run_dir'], 'scaffolding')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f'sample.{kind}')
    if not os.path.isfile(path):
        with open(path, 'wb') as fh:
            fh.write(MINIMAL_PDF if kind == 'pdf'
                     else f'ไฟล์ตัวอย่างของชุดตรวจ ชนิด {kind}\n'.encode('utf-8'))
    return path


def cmd_browser_attach(args):
    state = load_state(resolve_run_dir(args.run_dir))
    if bool(args.file) == bool(args.sample):
        raise Fail('ต้องเลือกอย่างใดอย่างหนึ่งระหว่าง --file กับ --sample',
                   next_steps=['control_pos.py browser attach --select "#file_attach" --sample pdf'])
    path = os.path.abspath(args.file) if args.file else sample_file(state, args.sample)
    if not os.path.isfile(path):
        raise Fail(f'ไม่พบไฟล์ {path}',
                   next_steps=['control_pos.py browser attach --select "#file_attach" --sample pdf'])
    page, _ = open_page(state)
    try:
        el = locate(page, args, any_visibility=True)
        if el['type'] != 'file':
            raise Fail(f"{args.select or args.text} ไม่ใช่ช่องแนบไฟล์ (type={el['type']})",
                       next_steps=['control_pos.py browser attach --select "#file_attach" '
                                   '--file <เส้นทางไฟล์>'])
        doc = page.call('DOM.getDocument', depth=0)
        node = page.call('DOM.querySelector', nodeId=doc['root']['nodeId'],
                         selector=args.select or '#file_attach')
        # DOM.setFileInputFiles คือสิ่งที่เบราว์เซอร์ทำหลังผู้ใช้เลือกไฟล์ในหน้าต่างของระบบ
        # ช่องนี้มี onchange อยู่แล้ว หน้าเว็บจึงอัปโหลดต่อเองเหมือนผู้ใช้เลือกจริง
        page.call('DOM.setFileInputFiles', files=[path], nodeId=node['nodeId'])
        deadline = time.monotonic() + args.timeout / 1000.0
        info = {}
        while time.monotonic() < deadline:
            info = page.evaluate("""({
                shown: (document.getElementById('file-name-display')||{}).innerText || '',
                zone: (document.getElementById('upload-zone')||{}).innerText || '',
                toast: (document.getElementById('toast-msg')||{}).innerText || '',
            })""")
            if os.path.basename(path) in (info['shown'] or '') or 'ไม่' in (info['toast'] or ''):
                break
            time.sleep(0.15)
        ok = os.path.basename(path) in (info.get('shown') or '')
        out = {'ok': ok, 'command': 'browser attach', 'method': 'DOM.setFileInputFiles',
               'file': path, 'element': el, 'after': info}
        if not ok:
            out['error'] = f'หน้าเว็บยังไม่แสดงชื่อไฟล์ {os.path.basename(path)} หลังแนบ'
            out['hint'] = 'ไฟล์อาจเป็นนามสกุลที่ไม่รองรับ (รองรับ pdf doc docx xls xlsx) หรือใหญ่เกิน 10 MB'
            out['next'] = ['control_pos.py browser read --select "#upload-zone"']
        emit(out, 0 if ok else 1)
    finally:
        page.close()


def cmd_browser_press(args):
    state = load_state(resolve_run_dir(args.run_dir))
    page, _ = open_page(state)
    try:
        el = None
        if args.select or args.text:
            el = locate(page, args)
            click_point(page, aim(page, el))
        key = args.key
        if key in KEYS:
            code, name, text = KEYS[key]
        elif len(key) == 1:
            code, name, text = ord(key.upper()), key, key
        else:
            raise Fail(f'ไม่รู้จักปุ่ม {key!r}',
                       hint=f'ปุ่มพิเศษที่รองรับคือ {sorted(KEYS)} นอกนั้นใส่อักขระเดียว',
                       next_steps=['control_pos.py browser press --key Enter'])
        page.call('Input.dispatchKeyEvent', type='keyDown', key=name, code=name,
                  windowsVirtualKeyCode=code, text=text or '')
        if text:
            page.call('Input.dispatchKeyEvent', type='char', key=name, text=text)
        page.call('Input.dispatchKeyEvent', type='keyUp', key=name, code=name,
                  windowsVirtualKeyCode=code)
        time.sleep(args.settle / 1000.0)
        emit({'ok': True, 'command': 'browser press', 'key': key, 'focused': el,
              'after': page.evaluate(AFTER_JS)})
    finally:
        page.close()


READ_JS = r"""
(() => {
  const norm = s => (s || '').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  const vis = el => !!el.getClientRects().length;
  const scope = ARGS.select ? document.querySelector(ARGS.select) : document.body;
  if (!scope) return {missing: ARGS.select};
  const out = {
    url: location.href,
    title: document.title,
    badge: norm((document.getElementById('mode-badge')||{}).innerText),
    user: norm((document.getElementById('user-name')||{}).innerText),
    counts: {
      badge_count: norm((document.getElementById('badge-count')||{}).innerText),
      shown: norm((document.getElementById('rec-shown')||{}).innerText),
      total: norm((document.getElementById('rec-total')||{}).innerText),
    },
    active_tab: norm((document.querySelector('.tbtn.active')||{}).innerText),
    // ข้อความแจ้งเตือนกับสรุปข้อผิดพลาดถูกซ่อนไว้ตอนไม่ใช้ innerText ของสิ่งที่ซ่อนอยู่
    // เป็นค่าว่างเสมอ จึงอ่าน textContent คู่กับสถานะว่าตอนนี้แสดงอยู่หรือไม่
    toast: {
      shown: !!(document.getElementById('myToast')||{classList:{contains:()=>false}})
               .classList.contains('show'),
      text: norm((document.getElementById('toast-msg')||{}).textContent),
    },
    form_errors: {
      shown: !!(document.getElementById('form-errors') &&
                !document.getElementById('form-errors').hidden),
      text: norm((document.getElementById('form-errors')||{}).textContent),
    },
    open_modal: [...document.querySelectorAll('.modal.show .modal-title')].map(e => norm(e.innerText)),
    text: norm(scope.innerText).slice(0, ARGS.limit),
    controls: [...scope.querySelectorAll('button,a,[role=button],.tbtn')]
      .filter(vis).map(e => norm(e.innerText) || e.getAttribute('aria-label') || '')
      .filter(Boolean).slice(0, 60),
  };
  if (ARGS.table) {
    const t = document.querySelector(ARGS.table);
    out.table = t ? {
      headers: [...t.querySelectorAll('thead th')].map(e => norm(e.innerText)),
      rows: [...t.querySelectorAll('tbody tr')].map(
        tr => [...tr.children].map(td => norm(td.innerText) ||
               (td.querySelector('[aria-label]') ? '[' +
                [...td.querySelectorAll('[aria-label]')].map(b =>
                  b.getAttribute('aria-label')).join('|') + ']' : ''))),
    } : {missing: ARGS.table};
  }
  return out;
})()
"""


def cmd_browser_read(args):
    state = load_state(resolve_run_dir(args.run_dir))
    page, target = open_page(state, args.window)
    try:
        deadline = time.monotonic() + args.timeout / 1000.0
        waited = None
        while True:
            data = page.evaluate(READ_JS, {'select': args.select, 'table': args.table,
                                           'limit': args.limit})
            if not args.wait_text:
                break
            waited = args.wait_text in json.dumps(data, ensure_ascii=False)
            if waited or time.monotonic() > deadline:
                break
            time.sleep(0.15)
        out = {'ok': True, 'command': 'browser read', 'window': args.window,
               'target': target['id'], 'page': data}
        if args.expr:
            out['expr'] = args.expr
            out['value'] = page.evaluate(f'({args.expr})')
        if args.wait_text and not waited:
            out.update({
                'ok': False,
                'error': f'ไม่พบข้อความ {args.wait_text!r} บนหน้านี้ภายใน {args.timeout} มิลลิวินาที',
                'hint': 'ดู page.text กับ page.controls ว่าหน้านี้แสดงอะไรอยู่จริง',
                'next': ['control_pos.py browser shot --name wait-failed'],
            })
            emit(out, 1)
        emit(out)
    finally:
        page.close()


def cmd_browser_shot(args):
    state = load_state(resolve_run_dir(args.run_dir))
    page, target = open_page(state, args.window)
    try:
        name = re.sub(r'[^A-Za-z0-9._-]+', '-', args.name).strip('-') or 'shot'
        path = os.path.join(state['evidence_dir'], f'{name}.png')
        os.makedirs(state['evidence_dir'], exist_ok=True)
        shot = page.call('Page.captureScreenshot', format='png',
                         captureBeyondViewport=bool(args.full_page))
        raw = base64.b64decode(shot['data'])
        with open(path, 'wb') as fh:
            fh.write(raw)
        info = page.evaluate("({url: location.href, title: document.title})")
        text_path = None
        if args.with_text:
            data = page.evaluate(READ_JS, {'select': None, 'table': '#tbl', 'limit': 20000})
            text_path = os.path.join(state['evidence_dir'], f'{name}.json')
            with open(text_path, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        emit({'ok': True, 'command': 'browser shot', 'window': args.window,
              'target': target['id'], 'png': path, 'bytes': len(raw),
              'snapshot': text_path, 'page': info,
              'note': 'หลักฐานอยู่ใน evidence_dir และไม่ถูกลบตอน app stop'})
    finally:
        page.close()


# ── CLI ──────────────────────────────────────────────────────────────────────
EPILOG = """ลำดับที่ใช้บ่อย
  control_pos.py app start                     เปิดอินสแตนซ์แยกพร้อมข้อมูลตั้งต้นและเบราว์เซอร์
  control_pos.py doctor                        ตรวจก่อนขับทุกครั้งที่สงสัยว่ามีอะไรผิด
  control_pos.py browser open --path /         เปิดหน้าแอปและรอจนพร้อมใช้งาน
  control_pos.py browser click --text "คำขอทั้งหมด"
  control_pos.py browser read --table "#tbl"
  control_pos.py browser shot --name list      เขียนภาพหน้าจอลง evidence_dir
  control_pos.py app stop                      ปิดเฉพาะโปรเซสที่การตรวจนี้เปิดไว้

โหมดเครื่องในวง LAN (พิสูจน์การเข้าสู่ระบบ)
  control_pos.py app start --lan
  control_pos.py users add --username somchai --display "สมชาย ใจดี" --password verify-pass-1
  control_pos.py api GET /api/positions --from lan                      คาดว่าได้ 401
  control_pos.py api GET /api/positions --from lan --login somchai:verify-pass-1
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog='control_pos.py',
        description='ขับแอป pos_restructure เพื่อพิสูจน์พฤติกรรมที่ผู้ใช้เห็น '
                    'ทุกคำสั่งพิมพ์ JSON หนึ่งก้อนและคืน exit code 0 เมื่อสำเร็จ',
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run-dir', help='โฟลเดอร์ของอินสแตนซ์ที่ต้องการสั่ง '
                                          'ค่าเริ่มต้นคืออินสแตนซ์ที่ app start เปิดไว้ล่าสุด')
    groups = parser.add_subparsers(dest='group', metavar='<หมวด>')

    # app
    app_p = groups.add_parser('app', help='เปิด ปิด และรันอินสแตนซ์สำหรับการตรวจ',
                              description='จัดการอินสแตนซ์ที่แยกฐานข้อมูล ไฟล์แนบ และ log '
                                          'ออกจากข้อมูลจริงของโปรเจกต์',
                              formatter_class=argparse.RawDescriptionHelpFormatter)
    app_sub = app_p.add_subparsers(dest='app_cmd', metavar='<คำสั่ง>', required=True)

    start = app_sub.add_parser('start', help='เปิดเซิร์ฟเวอร์ ข้อมูลตั้งต้น และเบราว์เซอร์ headless',
                               description='เปิดแอปในโฟลเดอร์ข้อมูลใหม่ รอจนใช้งานได้จริง '
                                           'แล้วเปิดเบราว์เซอร์ headless ที่พร้อมรับคำสั่ง browser')
    start.add_argument('--port', type=int, help='พอร์ตของแอป ค่าเริ่มต้นสุ่มพอร์ตว่าง '
                                                'เพื่อไม่ชนกับพอร์ต 5020 ที่ผู้ใช้อาจเปิดอยู่')
    start.add_argument('--lan', action='store_true',
                       help='ให้แอป bind 0.0.0.0 ด้วย เพื่อเรียกผ่าน IP ของเครื่องแล้วถูกนับเป็น '
                            'เครื่องในวง LAN ที่ต้องเข้าสู่ระบบ')
    start.add_argument('--no-seed', dest='seed', action='store_false',
                       help='ไม่ใส่คำขอตั้งต้น เริ่มจากฐานข้อมูลว่าง')
    start.set_defaults(seed=True, func=cmd_app_start)

    stop = app_sub.add_parser('stop', help='ปิดเฉพาะโปรเซสที่การตรวจนี้เปิดไว้',
                              description='ปิดเซิร์ฟเวอร์และเบราว์เซอร์ตามเลข pid ที่จดไว้ '
                                          'และลบ browser profile หลักฐานกับข้อมูลยังอยู่ครบ')
    stop.add_argument('--dry-run', action='store_true', help='แสดงว่าจะปิดอะไรและลบอะไรโดยไม่ทำ')
    stop.set_defaults(func=cmd_app_stop)

    serve = app_sub.add_parser('serve', help='รันแอปในโฟลเดอร์ข้อมูลที่กำหนด (app start เป็นคนเรียก)',
                               description='รันค้างอยู่หน้าจอ ไม่คืนค่า ปกติไม่ต้องเรียกเอง '
                                           'app start เรียกคำสั่งนี้เป็นลูก')
    serve.add_argument('--port', type=int, required=True)
    serve.add_argument('--data-dir', required=True)
    serve.add_argument('--lan', action='store_true')
    serve.add_argument('--pid-file', help='เขียนเลข pid ของโปรเซสที่ถือพอร์ตจริงลงไฟล์นี้')
    serve.set_defaults(func=cmd_app_serve)

    # doctor
    doctor = groups.add_parser('doctor', help='ตรวจอย่างเดียวว่าอินสแตนซ์นี้ควรขับต่อหรือไม่',
                               description='ไม่แก้อะไรทั้งนั้น ตรวจว่าโปรเซสยังอยู่ พอร์ตเป็นของเรา '
                                           'รุ่นของแอปตรงกับโค้ด และฐานข้อมูลไม่ใช่ข้อมูลจริง')
    doctor.set_defaults(func=cmd_doctor)

    # api
    api = groups.add_parser('api', help='ยิง HTTP ไปที่ API ของอินสแตนซ์',
                            description='เรียก API ได้ทั้งแบบเครื่องแม่ข่าย (--from local) '
                                        'และแบบเครื่องในวง LAN (--from lan) '
                                        'คุกกี้เซสชันเก็บไว้ใน run_dir จึงเรียกต่อกันได้',
                            epilog='ตัวอย่าง\n'
                                   '  control_pos.py api GET /api/positions\n'
                                   '  control_pos.py api POST /api/positions --data @req.json\n'
                                   '  control_pos.py api DELETE /api/positions/3 --dry-run\n'
                                   '  control_pos.py api GET /api/positions --from lan '
                                   '--login somchai:verify-pass-1\n',
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    api.add_argument('method', help='GET POST PUT DELETE')
    api.add_argument('path', help='เส้นทาง เช่น /api/positions '
                                  '(ใน Git Bash เขียนแบบไม่มี / นำหน้า เช่น api/positions)')
    api.add_argument('--data', help="เนื้อคำขอเป็น JSON หรือ @ชื่อไฟล์")
    api.add_argument('--from', dest='origin', choices=['local', 'lan'], default='local',
                     help='local = เครื่องแม่ข่าย (ไม่ต้องเข้าสู่ระบบ) '
                          'lan = เครื่องในวง (ต้องเข้าสู่ระบบ) ต้องเปิดด้วย app start --lan')
    api.add_argument('--login', metavar='ชื่อผู้ใช้งาน:รหัสผ่าน',
                     help='เข้าสู่ระบบก่อนยิงคำขอ และเก็บคุกกี้ไว้ใช้คำสั่งถัดไป')
    api.add_argument('--fresh', action='store_true',
                     help='ทิ้งคุกกี้เซสชันของ origin นี้ก่อนส่ง ใช้พิสูจน์ว่าคำขอที่ยังไม่ '
                          'เข้าสู่ระบบถูกปฏิเสธ เพราะคุกกี้จากคำสั่งก่อนหน้าถูกเก็บไว้ใช้ต่อ')
    api.add_argument('--dry-run', action='store_true',
                     help='แสดงคำขอที่จะส่งโดยไม่ส่ง ใช้กับคำขอที่เปลี่ยนข้อมูล')
    api.set_defaults(func=cmd_api)

    # browser
    browser = groups.add_parser('browser', help='ขับหน้าเว็บจริงด้วย Edge หรือ Chrome headless',
                                description='คลิกและพิมพ์ผ่าน Input.dispatch* ซึ่งเป็น event '
                                            'ที่เบราว์เซอร์สร้างให้เหมือนคนทำจริง '
                                            'ทุกคำสั่งรายงาน method ที่ใช้จริงกลับมาด้วย')
    bsub = browser.add_subparsers(dest='browser_cmd', metavar='<คำสั่ง>', required=True)

    def add_locator(p, timeout=5000):
        p.add_argument('--select', help='CSS selector เช่น "#p4_status"')
        p.add_argument('--text', help='ข้อความที่ผู้ใช้เห็นบนปุ่มหรือลิงก์ เช่น "บันทึกคำขอ" '
                                      'เทียบแบบตรงตัวก่อน แล้วค่อยขึ้นต้นด้วย แล้วค่อยมีคำนี้อยู่')
        p.add_argument('--nth', type=int, default=0, help='ลำดับเมื่อตรงหลายรายการ เริ่มจาก 0')
        p.add_argument('--timeout', type=int, default=timeout, help='รอองค์ประกอบกี่มิลลิวินาที')
        p.add_argument('--settle', type=int, default=400,
                       help='รอหลังลงมือกี่มิลลิวินาที ก่อนอ่านผลที่เกิดขึ้น')

    b_open = bsub.add_parser('open', help='เปิดหน้าหนึ่งและรอจนหน้านั้นพร้อมใช้งาน',
                             description=f'พร้อมหมายถึงป้ายสถานะขึ้น "{READY_BADGE}" '
                                         'หรือหน้าเข้าสู่ระบบแสดงฟอร์มแล้ว ไม่ใช่แค่โหลดเสร็จ')
    b_open.add_argument('--path', default='/', help='เส้นทาง เช่น / หรือ /login '
                        '(ใน Git Bash เขียนแบบไม่มี / นำหน้า เช่น login)')
    b_open.add_argument('--from', dest='origin', choices=['local', 'lan'], default='local')
    b_open.add_argument('--timeout', type=int, default=20000)
    b_open.add_argument('--no-wait', action='store_true',
                        help='ไม่รอสัญญาณพร้อม ใช้ตอนตั้งใจดูหน้าที่พังหรือหน้า error')
    b_open.set_defaults(func=cmd_browser_open)

    b_click = bsub.add_parser('click', help='คลิกองค์ประกอบด้วยเมาส์จริง',
                              description='เลื่อนองค์ประกอบเข้ากลางจอ แล้วส่ง mousePressed '
                                          'กับ mouseReleased ที่จุดกลางขององค์ประกอบนั้น')
    add_locator(b_click)
    b_click.set_defaults(func=cmd_browser_click)

    b_fill = bsub.add_parser('fill', help='กรอกค่าในช่องกรอก รวมถึง select และ input วันที่',
                             description='ช่องข้อความพิมพ์ด้วยคีย์บอร์ดจริง (Input.insertText) '
                                         'ส่วน select กับ input วันที่ตั้งค่าแล้วยิง input/change '
                                         'เพราะหน้าต่างเลือกของสองอย่างนี้เป็น UI ของระบบปฏิบัติการ')
    add_locator(b_fill)
    b_fill.add_argument('--value', required=True, help='ค่าที่ต้องการ ใส่ "" เพื่อล้างช่อง')
    b_fill.set_defaults(func=cmd_browser_fill)

    b_attach = bsub.add_parser('attach', help='แนบไฟล์เข้าช่องเลือกไฟล์',
                               description='ป้อนไฟล์ให้ <input type=file> แบบเดียวกับที่เบราว์เซอร์ '
                                           'ทำหลังผู้ใช้เลือกไฟล์ในหน้าต่างของระบบ แล้วรอให้หน้าเว็บ '
                                           'อัปโหลดและแสดงชื่อไฟล์')
    add_locator(b_attach, timeout=15000)
    b_attach.add_argument('--file', help='เส้นทางไฟล์ที่จะแนบ')
    b_attach.add_argument('--sample', choices=['pdf', 'docx', 'xlsx', 'txt'],
                          help='สร้างไฟล์ตัวอย่างใน <run_dir>/scaffolding/ แล้วแนบไฟล์นั้น '
                               'txt คือชนิดที่แอปต้องปฏิเสธ ใช้พิสูจน์ทางที่ควรล้มเหลว')
    b_attach.set_defaults(func=cmd_browser_attach)

    b_press = bsub.add_parser('press', help='กดปุ่มคีย์บอร์ด',
                              description='ใส่ --select หรือ --text เพื่อโฟกัสองค์ประกอบก่อนกด')
    add_locator(b_press)
    b_press.add_argument('--key', required=True,
                         help=f'ปุ่มพิเศษ {sorted(KEYS)} หรืออักขระเดียว เช่น /')
    b_press.set_defaults(func=cmd_browser_press)

    b_read = bsub.add_parser('read', help='อ่านสิ่งที่หน้าเว็บแสดงอยู่',
                             description='คืนที่อยู่ ชื่อหน้า ป้ายสถานะ แท็บที่เปิด ข้อความ '
                                         'ปุ่มที่กดได้ และตารางถ้าขอ ใช้ --wait-text เพื่อรอ '
                                         'ให้ข้อความหนึ่งปรากฏแทนการนอนรอตามเวลา')
    b_read.add_argument('--select', help='จำกัดข้อความไว้ใน CSS selector นี้')
    b_read.add_argument('--table', help='CSS selector ของตารางที่จะแปลงเป็นแถวและคอลัมน์ เช่น "#tbl"')
    b_read.add_argument('--expr', help='JavaScript expression ที่จะประเมินและคืนค่า '
                                       'ใช้ตอนต้องการค่าที่ไม่มีในผลปกติ')
    b_read.add_argument('--wait-text', help='รอจนข้อความนี้ปรากฏในผลที่อ่านได้')
    b_read.add_argument('--limit', type=int, default=4000, help='ตัดข้อความที่ยาวเกินกี่ตัวอักษร')
    b_read.add_argument('--timeout', type=int, default=10000)
    b_read.add_argument('--window', choices=['main', 'latest'], default='main',
                        help='main = หน้าหลักของการตรวจ latest = หน้าที่เพิ่งเปิดล่าสุด '
                             'เช่นหน้าต่างพิมพ์ PDF')
    b_read.set_defaults(func=cmd_browser_read)

    b_shot = bsub.add_parser('shot', help='บันทึกภาพหน้าจอลง evidence_dir',
                             description='เขียน <evidence_dir>/<name>.png และคืนเส้นทางไฟล์ '
                                         'ไฟล์เหล่านี้ไม่ถูกลบตอน app stop')
    b_shot.add_argument('--name', required=True, help='ชื่อไฟล์โดยไม่ต้องมีนามสกุล')
    b_shot.add_argument('--full-page', action='store_true', help='เก็บทั้งหน้า ไม่ใช่แค่ส่วนที่เห็น')
    b_shot.add_argument('--with-text', action='store_true',
                        help='เขียน <name>.json ที่เป็นข้อความและตารางของหน้านั้นคู่กันไปด้วย')
    b_shot.add_argument('--window', choices=['main', 'latest'], default='main')
    b_shot.set_defaults(func=cmd_browser_shot)

    # users
    users = groups.add_parser('users', help='บัญชีผู้ใช้งานในฐานข้อมูลของอินสแตนซ์',
                              description='แก้ได้เฉพาะฐานข้อมูลที่การตรวจเปิดเอง '
                                          'ถ้าเส้นทางหลุดออกนอก run_dir คำสั่งจะปฏิเสธ '
                                          'บัญชีจริงของหน่วยงานจัดการด้วย manage_users.py เท่านั้น')
    usub = users.add_subparsers(dest='users_cmd', metavar='<คำสั่ง>', required=True)
    u_list = usub.add_parser('list', help='รายชื่อบัญชีในฐานข้อมูลของอินสแตนซ์')
    u_list.set_defaults(func=cmd_users)
    u_add = usub.add_parser('add', help='เพิ่มบัญชีแบบไม่ถามรหัสผ่านทางแป้นพิมพ์',
                            description='manage_users.py ถามรหัสผ่านทางแป้นพิมพ์ซึ่งขับอัตโนมัติไม่ได้ '
                                        'คำสั่งนี้ใช้กติกาเดียวกันแต่รับรหัสผ่านมาเป็นอาร์กิวเมนต์')
    u_add.add_argument('--username', required=True, help='a-z 0-9 . _ - ยาว 3 ถึง 32 ตัว')
    u_add.add_argument('--display', required=True, help='ชื่อแสดงผล ภาษาไทยได้')
    u_add.add_argument('--password', required=True, help='ยาวอย่างน้อย 8 ตัว')
    u_add.add_argument('--dry-run', action='store_true', help='แสดงบัญชีที่จะเพิ่มโดยไม่เพิ่ม')
    u_add.set_defaults(func=cmd_users)
    u_rm = usub.add_parser('remove', help='ลบบัญชี (dry-run โดยค่าเริ่มต้น)',
                           description='เป็น dry-run โดยค่าเริ่มต้นแบบเดียวกับ cleanup_orphans.py '
                                       'ต้องใส่ --apply จึงจะลบจริง')
    u_rm.add_argument('--username', required=True)
    u_rm.add_argument('--apply', action='store_true', help='ลบจริง')
    u_rm.add_argument('--dry-run', action='store_true', help='แสดงสิ่งที่จะลบ (เป็นค่าเริ่มต้นอยู่แล้ว)')
    u_rm.set_defaults(func=cmd_users)

    # data
    data = groups.add_parser('data', help='ข้อมูลตั้งต้นของอินสแตนซ์',
                             description='ใส่และล้างคำขอผ่าน API เดียวกับที่หน้าเว็บใช้')
    dsub = data.add_subparsers(dest='data_cmd', metavar='<คำสั่ง>', required=True)
    d_seed = dsub.add_parser('seed', help='ใส่คำขอตั้งต้นสองใบ ทำซ้ำได้ไม่เกิดของซ้ำ',
                             description=f'คำขอตั้งต้นมี p4_note เป็น "{SEED_MARKER}" '
                                         'คำสั่งนี้จึงรู้ว่าใบไหนใส่ไปแล้ว')
    d_seed.add_argument('--dry-run', action='store_true', help='แสดงว่าจะใส่อะไรโดยไม่ใส่')
    d_seed.set_defaults(func=cmd_data)
    d_reset = dsub.add_parser('reset', help='ลบคำขอทั้งหมดของอินสแตนซ์ (dry-run โดยค่าเริ่มต้น)',
                              description='ลบเฉพาะข้อมูลในโฟลเดอร์ของอินสแตนซ์นี้ '
                                          'ย้อนกลับไม่ได้ จึงต้องใส่ --apply')
    d_reset.add_argument('--apply', action='store_true', help='ลบจริง')
    d_reset.add_argument('--dry-run', action='store_true',
                         help='แสดงสิ่งที่จะลบ (เป็นค่าเริ่มต้นอยู่แล้ว)')
    d_reset.set_defaults(func=cmd_data)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, 'func', None):
        parser.print_help()
        return 2
    try:
        args.func(args)
    except Fail as exc:
        emit({'ok': False, 'command': ' '.join(sys.argv[1:3]), 'error': exc.error,
              'hint': exc.hint, 'next': exc.next_steps, **exc.extra}, 1)
    except cdp.BrowserError as exc:
        emit({'ok': False, 'command': ' '.join(sys.argv[1:3]), 'error': str(exc),
              'hint': exc.hint,
              'next': exc.next_steps or ['control_pos.py doctor', 'control_pos.py app start']}, 1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
