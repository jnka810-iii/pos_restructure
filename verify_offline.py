"""ตรวจว่าหน้าเว็บทำงานได้จริงบนเครื่องที่ไม่มีอินเทอร์เน็ต

รัน: .venv\\Scripts\\python.exe verify_offline.py [--assets local|cdn]

สคริปต์เปิด Flask ขึ้นมาบนพอร์ตว่าง แล้วสั่ง Edge หรือ Chrome แบบ headless ให้เปิดหน้านั้น
โดยใส่ --host-resolver-rules ที่ทำให้ทุกโฮสต์นอก 127.0.0.1 หาที่อยู่ไม่เจอ ซึ่งเป็นสภาพเดียวกับ
เครื่องที่ไม่มีเน็ต แล้ววัดจากในเบราว์เซอร์ว่าไลบรารีมาครบไหม

--assets cdn ชี้ไลบรารีกลับไปที่ CDN ชุดเดิมก่อนแก้ F10 ไว้เทียบว่าตอนนั้นพังอย่างไร
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from urllib.request import urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app

BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]

CDN_ASSETS = [
    'https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&display=swap',
    'https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.2/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js',
]

REACHABLE_WHILE_OFFLINE = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js'

PROBE_PAGE = """<!doctype html>
<html lang="th"><head><meta charset="UTF-8">
%(assets)s
</head><body style="font-family:'Sarabun',sans-serif">
<button id="btn" class="btn btn-primary">ปุ่ม</button>
<i id="icon" class="fa fa-landmark"></i>
<canvas id="canvas" width="120" height="120"></canvas>
<pre id="out">PROBE_DID_NOT_RUN</pre>
<script>
(async () => {
  const r = {};
  r.navigator_online = navigator.onLine;
  try {
    await fetch(%(external)s, {cache: 'no-store'});
    r.external_fetch = 'reached';
  } catch (e) {
    r.external_fetch = 'blocked';
  }
  r.chart_global = typeof Chart;
  r.button_radius = getComputedStyle(document.getElementById('btn')).borderRadius;
  r.icon_font = getComputedStyle(document.getElementById('icon'), '::before').fontFamily;
  try {
    await document.fonts.load('400 16px Sarabun');
    await document.fonts.load('700 16px Sarabun');
    await document.fonts.load('900 16px "Font Awesome 6 Free"');
  } catch (e) {}
  await document.fonts.ready;
  r.fonts = [...document.fonts].map(f => ({family: f.family, weight: f.weight, status: f.status}));
  const popup = window.open('', '_blank');
  if (!popup) {
    r.popup_font = 'POPUP_BLOCKED';
  } else {
    popup.document.write('<link rel="stylesheet" href=%(font)s>');
    r.popup_font = popup.document.querySelector('link').href;
    popup.close();
  }
  try {
    new Chart(document.getElementById('canvas'),
              {type: 'doughnut', data: {labels: ['ก'], datasets: [{data: [1]}]}});
    r.doughnut = 'drawn';
  } catch (e) {
    r.doughnut = e.name + ': ' + e.message;
  }
  document.getElementById('out').textContent = JSON.stringify(r);
})();
</script>
</body></html>
"""


def find_browser():
    paths = [os.environ['OFFLINE_BROWSER']] if os.environ.get('OFFLINE_BROWSER') else BROWSERS
    for path in paths:
        if os.path.isfile(path):
            return path
    raise SystemExit('ไม่พบ Edge หรือ Chrome ตั้ง OFFLINE_BROWSER ให้ชี้ไปที่ตัวที่ติดตั้งไว้')


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


PROBE = {'html': ''}


def start_app(port):
    tmp = tempfile.mkdtemp(prefix='offline_db_')
    app.DB_PATH = os.path.join(tmp, 'probe.db')
    app.init_db()
    app.app.add_url_rule('/__probe__', 'offline_probe', lambda: PROBE['html'])
    threading.Thread(
        target=lambda: app.app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False),
        daemon=True).start()
    if not app.wait_for_port(port):
        raise SystemExit(f'Flask ไม่ตอบที่พอร์ต {port}')
    return tmp


def asset_tags(page_html):
    css = re.findall(r"""<link[^>]+rel=["']stylesheet["'][^>]+href=["']([^"']+)""", page_html)
    css += re.findall(r"""<link[^>]+href=["']([^"']+)["'][^>]*rel=["']stylesheet""", page_html)
    js = re.findall(r"""<script[^>]+src=["']([^"']+)""", page_html)
    return sorted(set(css)), sorted(set(js))


def probe_html_for(urls):
    css = [u for u in urls if not u.endswith('.js')]
    js = [u for u in urls if u.endswith('.js')]
    tags = [f'<link rel="stylesheet" href="{u}">' for u in css]
    tags += [f'<script src="{u}"></script>' for u in js]
    font = next((u for u in css if 'sarabun' in u.lower()), css[0])
    return PROBE_PAGE % {'assets': '\n'.join(tags),
                         'external': json.dumps(REACHABLE_WHILE_OFFLINE),
                         'font': json.dumps(font)}


def run_offline(browser, url, extra):
    profile = tempfile.mkdtemp(prefix='offline_profile_')
    cmd = [browser, '--headless=new', '--disable-gpu', '--no-first-run',
           '--no-default-browser-check', '--disable-extensions', '--disable-popup-blocking',
           f'--user-data-dir={profile}',
           '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1',
           '--virtual-time-budget=10000'] + extra + [url]
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=180)
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def read_probe(browser, url):
    done = run_offline(browser, url, ['--dump-dom'])
    found = re.search(r'<pre id="out">(.*?)</pre>', done.stdout, re.S)
    if not found:
        raise SystemExit(f'อ่านผลจากหน้า probe ไม่ได้\n{done.stdout[:2000]}\n{done.stderr[:2000]}')
    if found.group(1) == 'PROBE_DID_NOT_RUN':
        raise SystemExit('สคริปต์ในหน้า probe ไม่ทำงาน')
    return json.loads(found.group(1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', choices=['local', 'cdn'], default='local')
    parser.add_argument('--shot', default=os.path.join(tempfile.gettempdir(), 'offline_page.png'))
    args = parser.parse_args()
    # เบราว์เซอร์เป็นคนละโปรเซส เส้นทางแบบสัมพัทธ์ของมันไม่ใช่ที่เดียวกับของสคริปต์
    args.shot = os.path.abspath(args.shot)

    browser = find_browser()
    port = free_port()
    tmp = start_app(port)
    base = f'http://127.0.0.1:{port}'
    page = urlopen(f'{base}/').read().decode('utf-8')
    css, js = asset_tags(page)
    assets = CDN_ASSETS if args.assets == 'cdn' else css + js
    PROBE['html'] = probe_html_for(assets)
    print(f'browser   {browser}')
    print(f'assets    {args.assets}')
    for url in assets:
        print(f'          {url}')

    got = read_probe(browser, f'{base}/__probe__')
    print('probe     ' + json.dumps(got, ensure_ascii=False))

    shot = run_offline(browser, f'{base}/',
                       ['--window-size=1280,900', f'--screenshot={args.shot}'])
    shutil.rmtree(tmp, ignore_errors=True)

    sarabun = {f['weight'] for f in got['fonts']
               if 'Sarabun' in f['family'] and f['status'] == 'loaded'}
    icons = [f for f in got['fonts']
             if 'Font Awesome' in f['family'] and f['status'] == 'loaded']

    checks = [
        ('the machine really is offline', got['external_fetch'] == 'blocked',
         f"fetch ออกนอกเครื่องได้ {got['external_fetch']} ชุดตรวจนี้วัดสภาพออฟไลน์ไม่ได้"),
        ('chart.js is loaded', got['chart_global'] == 'function',
         f"typeof Chart = {got['chart_global']} แท็บสรุปภาพรวมจะพังทั้งแท็บ"),
        ('a doughnut chart draws', got['doughnut'] == 'drawn', got['doughnut']),
        ('bootstrap css is applied', got['button_radius'] not in ('', '0px'),
         f"border-radius ของปุ่ม = {got['button_radius']!r} หน้าเว็บไม่มี style"),
        ('the icon webfont is loaded', bool(icons) and 'Font Awesome' in got['icon_font'],
         f"ไอคอนไม่มา ::before font-family = {got['icon_font']!r} ฟอนต์ที่โหลดได้ {icons}"),
        ('the thai webfont is loaded', {'400', '700'} <= sarabun,
         f'Sarabun ที่โหลดได้ {sorted(sarabun)} ฟอนต์ไทยตกไปใช้ fallback ของระบบ'),
        ('the pdf window resolves the font to this machine',
         got['popup_font'].startswith(base if args.assets == 'local' else 'https://'),
         f"หน้าต่าง PDF ชี้ฟอนต์ไปที่ {got['popup_font']}"),
        ('the screenshot was written',
         os.path.exists(args.shot) and os.path.getsize(args.shot) > 10000,
         f'{args.shot} ไม่ถูกสร้างหรือเล็กผิดปกติ '
         f'เบราว์เซอร์จบด้วย {shot.returncode} {shot.stderr.strip()[:300]}'),
    ]
    failed = 0
    for name, ok, why in checks:
        if ok:
            print(f'PASS  {name}')
        else:
            failed += 1
            print(f'FAIL  {name}\n        {why}')
    print(f'\n{len(checks) - failed}/{len(checks)} passed, screenshot {args.shot}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
