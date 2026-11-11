"""ตัวขับเบราว์เซอร์ผ่าน Chrome DevTools Protocol ด้วยไลบรารีมาตรฐานของ Python เท่านั้น

เครื่องที่รันแอปนี้มีแต่ Flask กับ pywebview ใน .venv ไม่มี Playwright หรือ Selenium และ
requirements.txt ก็ไม่ควรบวมขึ้นเพราะชุดตรวจ ไฟล์นี้จึงพูด WebSocket กับ CDP เองตรงๆ
ใช้ Edge หรือ Chrome ที่ติดตั้งอยู่แล้วแบบ headless ชุดเดียวกับที่ verify_offline.py ใช้

การคลิกและการพิมพ์ส่งผ่าน Input.dispatch* ซึ่งเป็น event ที่เบราว์เซอร์สร้างให้เหมือนคนทำจริง
ไม่ใช่การเรียก element.click() จาก JavaScript ข้อยกเว้นที่เลี่ยงไม่ได้คือ <select> กับ
<input type="date"> ที่ต้องตั้งค่าแล้วยิง event เอง เพราะหน้าต่างเลือกของสองอย่างนี้เป็น UI
ของระบบปฏิบัติการ ไม่ได้อยู่ในหน้าเว็บ ทุกคำสั่งจึงรายงาน method ที่ใช้จริงกลับมาด้วย
"""

import base64
import json
import os
import socket
import struct
import subprocess
import tempfile
import time
from urllib.parse import urlparse
from urllib.request import urlopen

BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]


class BrowserError(Exception):
    """ความผิดพลาดที่อธิบายให้ผู้เรียกได้ว่าควรทำอะไรต่อ"""

    def __init__(self, message, hint='', next_steps=()):
        super().__init__(message)
        self.hint = hint
        self.next_steps = list(next_steps)


def find_browser():
    paths = [os.environ['OFFLINE_BROWSER']] if os.environ.get('OFFLINE_BROWSER') else BROWSERS
    for path in paths:
        if os.path.isfile(path):
            return path
    raise BrowserError(
        'ไม่พบ Microsoft Edge หรือ Google Chrome บนเครื่องนี้',
        hint='ตัวขับเบราว์เซอร์ใช้ Edge หรือ Chrome ที่ติดตั้งอยู่แล้วแบบ headless',
        next_steps=['ตั้ง OFFLINE_BROWSER ให้ชี้ไปที่ msedge.exe หรือ chrome.exe แล้วสั่ง app start ใหม่'],
    )


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ── WebSocket ────────────────────────────────────────────────────────────────
class WebSocket:
    """WebSocket client ขนาดเล็กเท่าที่ CDP ต้องใช้ (RFC 6455 text frame)"""

    def __init__(self, url, timeout=30.0):
        parts = urlparse(url)
        self.sock = socket.create_connection((parts.hostname, parts.port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b''
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f'GET {path} HTTP/1.1\r\n'
            f'Host: {parts.hostname}:{parts.port}\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n'
        ).encode())
        head = self._read_until(b'\r\n\r\n')
        if b'101' not in head.split(b'\r\n', 1)[0]:
            raise BrowserError(f'เบราว์เซอร์ไม่ยอมรับการเชื่อมต่อ WebSocket: {head[:120]!r}')

    def _read_until(self, marker):
        while marker not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise BrowserError('เบราว์เซอร์ปิดการเชื่อมต่อระหว่างต่อ WebSocket')
            self.buf += chunk
        head, self.buf = self.buf.split(marker, 1)
        return head + marker

    def _read_exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self.buf)))
            if not chunk:
                raise BrowserError('เบราว์เซอร์ปิดการเชื่อมต่อระหว่างอ่านข้อมูล')
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text):
        payload = text.encode('utf-8')
        n = len(payload)
        header = b'\x81'
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += b'\xfe' + struct.pack('>H', n)
        else:
            header += b'\xff' + struct.pack('>Q', n)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def recv(self):
        """คืน text ของหนึ่ง message ต่อ fragment ให้เองและตอบ ping ให้เอง"""
        chunks = []
        while True:
            b0, b1 = self._read_exact(2)
            fin, opcode = b0 & 0x80, b0 & 0x0F
            length = b1 & 0x7F
            if length == 126:
                length = struct.unpack('>H', self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack('>Q', self._read_exact(8))[0]
            data = self._read_exact(length) if length else b''
            if opcode == 0x8:
                raise BrowserError('เบราว์เซอร์ปิดการเชื่อมต่อ (close frame)')
            if opcode == 0x9:
                self.sock.sendall(b'\x8a' + bytes([0x80]) + os.urandom(4))
                continue
            if opcode == 0xA:
                continue
            chunks.append(data)
            if fin:
                return b''.join(chunks).decode('utf-8', 'replace')

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# ── CDP ──────────────────────────────────────────────────────────────────────
class Page:
    """หนึ่งการเชื่อมต่อไปยังหนึ่ง page target"""

    def __init__(self, ws_url, timeout=30.0):
        self.ws = WebSocket(ws_url, timeout=timeout)
        self.next_id = 0
        self.events = []

    def call(self, method, **params):
        self.next_id += 1
        mid = self.next_id
        self.ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') != mid:
                self.events.append(msg)
                continue
            if 'error' in msg:
                raise BrowserError(f"CDP {method} ล้มเหลว: {msg['error'].get('message')}")
            return msg.get('result', {})

    def evaluate(self, expression, args=None):
        """รัน JavaScript แล้วคืนค่าที่ JSON แปลงได้ args ฝังเข้าไปเป็น ARGS"""
        if args is not None:
            expression = f'(ARGS => ({expression}))({json.dumps(args)})'
        res = self.call('Runtime.evaluate', expression=expression,
                        returnByValue=True, awaitPromise=True, userGesture=True)
        if 'exceptionDetails' in res:
            detail = res['exceptionDetails']
            text = (detail.get('exception') or {}).get('description') or detail.get('text')
            raise BrowserError(f'JavaScript ในหน้าเว็บโยน error: {text}')
        return res.get('result', {}).get('value')

    def close(self):
        self.ws.close()


def launch(profile_dir, devtools_port, extra_args=()):
    """เปิดเบราว์เซอร์ headless ที่เปิด CDP ไว้ คืน (process, executable path)"""
    browser = find_browser()
    os.makedirs(profile_dir, exist_ok=True)
    cmd = [
        browser,
        '--headless=new',
        '--disable-gpu',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-extensions',
        '--disable-popup-blocking',
        '--window-size=1400,1000',
        f'--user-data-dir={profile_dir}',
        f'--remote-debugging-port={devtools_port}',
        *extra_args,
        'about:blank',
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc, browser


def devtools_targets(port, timeout=20.0):
    """รอจนเบราว์เซอร์เปิดพอร์ต CDP แล้วคืนรายการ target"""
    deadline = time.monotonic() + timeout
    last = ''
    while time.monotonic() < deadline:
        try:
            with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=2) as fh:
                return json.loads(fh.read().decode('utf-8'))
        except Exception as exc:  # เบราว์เซอร์ยังไม่เปิดพอร์ต
            last = f'{type(exc).__name__}: {exc}'
            time.sleep(0.15)
    raise BrowserError(
        f'เบราว์เซอร์ไม่เปิดพอร์ต DevTools {port} ภายใน {timeout:.0f} วินาที ({last})',
        hint='เบราว์เซอร์อาจถูกปิดไปแล้ว หรือ profile ที่ใช้ค้างอยู่',
        next_steps=['control_pos.py app stop', 'control_pos.py app start'],
    )


def page_targets(port):
    return [t for t in devtools_targets(port) if t.get('type') == 'page']


def attach(port, target_id=None, which='main', timeout=30.0):
    """ต่อไปยัง page target: target_id ที่ระบุไว้ หรือหน้าที่เปิดล่าสุดเมื่อ which='latest'"""
    pages = page_targets(port)
    if not pages:
        raise BrowserError(
            'ไม่พบหน้าเว็บในเบราว์เซอร์ที่เปิดไว้',
            next_steps=['control_pos.py app stop', 'control_pos.py app start'],
        )
    if which == 'latest':
        chosen = pages[0]  # /json/list เรียงหน้าที่เพิ่งใช้งานไว้บนสุด
    else:
        chosen = next((t for t in pages if t['id'] == target_id), None)
        if chosen is None:
            raise BrowserError(
                f'ไม่พบหน้าหลักของการตรวจครั้งนี้ (target {target_id})',
                hint='หน้าหลักอาจถูกปิดไปแล้ว',
                next_steps=['control_pos.py app stop', 'control_pos.py app start'],
            )
    page = Page(chosen['webSocketDebuggerUrl'], timeout=timeout)
    return page, chosen


def temp_profile():
    return tempfile.mkdtemp(prefix='pos_verify_profile_')
