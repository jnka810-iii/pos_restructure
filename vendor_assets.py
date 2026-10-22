"""ดาวน์โหลดไลบรารีหน้าเว็บมาเก็บไว้ใน static/vendor เพื่อให้แอปทำงานได้บนเครื่องที่ไม่มีเน็ต

รัน: .venv\\Scripts\\python.exe vendor_assets.py

ไฟล์ทุกไฟล์ใต้ static/vendor สร้างจากสคริปต์นี้ ไม่ต้องแก้ด้วยมือ รันซ้ำได้ผลเหมือนเดิม
และเป็นที่เดียวที่บอกว่าแต่ละไฟล์มาจาก URL ไหนและเวอร์ชันอะไร

เปลี่ยนเวอร์ชันไลบรารี: แก้ที่ตาราง ASSETS แล้วรันใหม่ จากนั้นแก้ชื่อไฟล์ใน templates/index.html
ให้ตรงกัน แล้วรัน verify_offline.py
"""

import os
import re
import shutil
import sys
import tempfile
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(HERE, 'static', 'vendor')

CDNJS = 'https://cdnjs.cloudflare.com/ajax/libs/'
SARABUN_CSS = 'https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&display=swap'

# Google ส่ง CSS คนละชุดตาม User-Agent เบราว์เซอร์เก่าจะได้ ttf ที่ใหญ่กว่า woff2 หลายเท่า
CHROME_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

SOURCE_MAP = re.compile(rb'/[*/]# sourceMappingURL=[^\n]*')
TTF_FALLBACK = re.compile(r',\s*url\(\.\./webfonts/[^)]+\.ttf\)\s*format\("truetype"\)')
WEBFONT_REF = re.compile(r'\.\./webfonts/([^)"\']+\.woff2)')
FONT_FACE = re.compile(r'/\*\s*([\w-]+)\s*\*/\s*@font-face\s*{([^}]*)}')

build_dir = None


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': CHROME_UA}), timeout=60) as res:
        return res.read()


def save(rel_path, data):
    path = os.path.join(build_dir, rel_path.replace('/', os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(data)
    return len(data)


def as_is(data, rel_path):
    return SOURCE_MAP.sub(b'', data)


def font_awesome(data, rel_path):
    """ดึง webfont ที่ CSS อ้างถึงมาด้วย และตัด ttf ทิ้งเพราะเบราว์เซอร์เลือก woff2 อยู่แล้ว"""
    css = TTF_FALLBACK.sub('', SOURCE_MAP.sub(b'', data).decode('utf-8'))
    base = os.path.dirname(os.path.dirname(rel_path))
    for name in sorted(set(WEBFONT_REF.findall(css))):
        save(f'{base}/webfonts/{name}', fetch(f'{CDNJS}font-awesome/6.4.2/webfonts/{name}'))
    return css.encode('utf-8')


def sarabun(data, rel_path):
    """ตั้งชื่อไฟล์ฟอนต์ตามน้ำหนักและช่วงอักษร ชื่อจาก Google เป็นแฮชที่เปลี่ยนได้ทุกเมื่อ"""
    css = data.decode('utf-8')
    base = os.path.dirname(rel_path)
    for subset, body in FONT_FACE.findall(css):
        weight = re.search(r'font-weight:\s*(\d+)', body).group(1)
        url = re.search(r'url\((https://[^)]+)\)', body).group(1)
        name = f'sarabun-{weight}-{subset}.woff2'
        save(f'{base}/{name}', fetch(url))
        css = css.replace(url, name)
    return css.encode('utf-8')


ASSETS = [
    ('bootstrap/css/bootstrap.min.css', CDNJS + 'bootstrap/5.3.2/css/bootstrap.min.css', as_is),
    ('bootstrap/js/bootstrap.bundle.min.js', CDNJS + 'bootstrap/5.3.2/js/bootstrap.bundle.min.js', as_is),
    ('fontawesome/css/all.min.css', CDNJS + 'font-awesome/6.4.2/css/all.min.css', font_awesome),
    ('chartjs/chart.umd.min.js', CDNJS + 'Chart.js/4.4.1/chart.umd.min.js', as_is),
    ('sarabun/sarabun.css', SARABUN_CSS, sarabun),
]


def main():
    global build_dir
    build_dir = tempfile.mkdtemp(prefix='vendor_build_', dir=HERE)
    try:
        for rel_path, url, rewrite in ASSETS:
            save(rel_path, rewrite(fetch(url), rel_path))
        shutil.rmtree(VENDOR_DIR, ignore_errors=True)
        os.makedirs(os.path.dirname(VENDOR_DIR), exist_ok=True)
        os.replace(build_dir, VENDOR_DIR)
    except BaseException:
        shutil.rmtree(build_dir, ignore_errors=True)
        raise

    total = 0
    for root, _, files in os.walk(VENDOR_DIR):
        for name in sorted(files):
            path = os.path.join(root, name)
            size = os.path.getsize(path)
            total += size
            print(f'{size:>9,}  {os.path.relpath(path, HERE)}')
    print(f'{total:>9,}  รวม')
    return 0


if __name__ == '__main__':
    sys.exit(main())
