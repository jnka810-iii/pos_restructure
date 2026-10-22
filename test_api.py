"""Regression checks for the API. Run: .venv\\Scripts\\python.exe test_api.py"""

import io
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import tempfile
from datetime import datetime, timezone
from urllib.parse import urljoin

TMP = tempfile.mkdtemp(prefix='pos_test_')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app

HERE = os.path.dirname(os.path.abspath(__file__))

app.DB_PATH = os.path.join(TMP, 'test.db')
app.UPLOAD_FOLDER = os.path.join(TMP, 'uploads')
app.init_db()

client = app.app.test_client()
APP_SOURCE = open(os.path.join(HERE, 'app.py'), encoding='utf-8').read()
PAGE_SOURCE = open(os.path.join(HERE, 'templates', 'index.html'), encoding='utf-8').read()

UUID_NAME = re.compile(r'^[0-9a-f]{32}\.[a-z]+$')
ISO_STAMP = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$')


def post_file(filename, data=b'%PDF-1.4 test'):
    return client.post('/api/upload',
                       data={'file': (io.BytesIO(data), filename)},
                       content_type='multipart/form-data')


def js_function(name):
    """ตัดซอร์สของฟังก์ชันหนึ่งตัวออกมาจาก index.html โดยนับปีกกาให้สมดุล"""
    start = PAGE_SOURCE.index(f'function {name}(')
    depth, i = 0, PAGE_SOURCE.index('{', start)
    while True:
        if PAGE_SOURCE[i] == '{':
            depth += 1
        elif PAGE_SOURCE[i] == '}':
            depth -= 1
            if depth == 0:
                return PAGE_SOURCE[start:i + 1]
        i += 1


def run_js(names, body):
    """รันฟังก์ชันจากหน้าเว็บจริงด้วย Node แล้วอ่านผลกลับมาเป็น JSON"""
    script = '\n'.join([js_function(n) for n in names] + [body])
    path = os.path.join(TMP, 'probe.mjs')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(script)
    out = subprocess.run([NODE, path], capture_output=True, text=True, encoding='utf-8')
    assert out.returncode == 0, f'node failed: {out.stderr.strip()}'
    return json.loads(out.stdout)


NODE = shutil.which('node')


class Skipped(Exception):
    """เครื่องมือที่เทสต้องใช้ไม่มีในเครื่องนี้ รายงานเป็น SKIP ไม่ใช่ FAIL"""


def upload_accepts_a_thai_filename():
    r = post_file('เอกสารคำขอ.pdf')
    assert r.status_code == 200, f'expected 200, got {r.status_code} {r.get_json()}'
    body = r.get_json()
    assert body['ok'] is True, body
    assert body['orig_name'] == 'เอกสารคำขอ.pdf', f"display name mangled: {body['orig_name']}"
    assert UUID_NAME.match(body['file_name']), f"stored name not a uuid: {body['file_name']}"
    assert os.path.exists(os.path.join(app.UPLOAD_FOLDER, body['file_name'])), 'file missing on disk'


def upload_keeps_the_extension_when_the_name_has_several_dots():
    r = post_file('บอ.1 ปรับปรุงตำแหน่ง.xlsx', b'fake xlsx')
    assert r.status_code == 200, f'expected 200, got {r.status_code} {r.get_json()}'
    assert r.get_json()['file_name'].endswith('.xlsx'), r.get_json()['file_name']


def upload_rejects_an_extension_outside_the_allowlist():
    r = post_file('payload.exe', b'MZ')
    assert r.status_code == 400, f'expected 400, got {r.status_code}'
    assert r.get_json()['ok'] is False


def upload_never_writes_outside_the_upload_folder():
    r = post_file('../../escape.pdf')
    assert r.status_code == 200, f'expected 200, got {r.status_code} {r.get_json()}'
    stored = r.get_json()['file_name']
    assert UUID_NAME.match(stored), f'traversal survived into the stored name: {stored}'
    resolved = os.path.realpath(os.path.join(app.UPLOAD_FOLDER, stored))
    assert resolved.startswith(os.path.realpath(app.UPLOAD_FOLDER)), resolved


def put_reports_404_for_a_record_that_does_not_exist():
    r = client.put('/api/positions/999999', json={'p4_status': 'อนุมัติ'})
    assert r.status_code == 404, f'expected 404, got {r.status_code} {r.get_json()}'
    assert r.get_json()['ok'] is False, r.get_json()


def put_writes_the_value_for_a_record_that_does_exist():
    rid = client.post('/api/positions', json={'p4_status': 'อยู่ระหว่างพิจารณา'}).get_json()['id']
    r = client.put(f'/api/positions/{rid}', json={'p4_status': 'อนุมัติ'})
    assert r.status_code == 200, f'expected 200, got {r.status_code} {r.get_json()}'
    row = [x for x in client.get('/api/positions').get_json() if x['id'] == rid][0]
    assert row['p4_status'] == 'อนุมัติ', row['p4_status']
    assert row['updated'], 'updated timestamp not written'


def post_drops_keys_outside_the_allowlist():
    r = client.post('/api/positions', json={'id': 4242, 'evil': 1, 'p4_status': 'อนุมัติ'})
    assert r.status_code == 201, f'expected 201, got {r.status_code} {r.get_json()}'
    rid = r.get_json()['id']
    assert rid != 4242, 'client-supplied id reached the insert'
    row = [x for x in client.get('/api/positions').get_json() if x['id'] == rid][0]
    assert 'evil' not in row, 'unlisted column reached the insert'


def the_bundled_entry_point_never_enables_the_werkzeug_debugger():
    assert 'debug=True' not in APP_SOURCE, 'debug=True would expose the debugger console'


def the_bundled_entry_point_binds_loopback_only():
    assert "'0.0.0.0'" not in APP_SOURCE, 'app.py binds every interface, use run_server.bat for LAN'


def deleting_a_record_removes_its_attached_file():
    stored = post_file('ใบแนบ.pdf').get_json()['file_name']
    rid = client.post('/api/positions', json={'p4_status': 'อนุมัติ', 'file_name': stored}).get_json()['id']
    path = os.path.join(app.UPLOAD_FOLDER, stored)
    assert os.path.exists(path), 'setup failed, file never landed'
    client.delete(f'/api/positions/{rid}')
    assert not os.path.exists(path), 'attachment outlived its record'


def deleting_every_record_removes_every_attached_file():
    paths = []
    for name in ('หนึ่ง.pdf', 'สอง.pdf'):
        stored = post_file(name).get_json()['file_name']
        client.post('/api/positions', json={'p4_status': 'อนุมัติ', 'file_name': stored})
        paths.append(os.path.join(app.UPLOAD_FOLDER, stored))
    client.delete('/api/positions')
    left = [p for p in paths if os.path.exists(p)]
    assert not left, f'{len(left)} attachment(s) stranded by delete-all'


def replacing_an_attachment_removes_the_previous_file():
    first = post_file('เก่า.pdf').get_json()['file_name']
    rid = client.post('/api/positions', json={'p4_status': 'อนุมัติ', 'file_name': first}).get_json()['id']
    second = post_file('ใหม่.pdf').get_json()['file_name']
    client.put(f'/api/positions/{rid}', json={'file_name': second})
    assert not os.path.exists(os.path.join(app.UPLOAD_FOLDER, first)), 'replaced attachment stranded'
    assert os.path.exists(os.path.join(app.UPLOAD_FOLDER, second)), 'new attachment missing'


def the_record_list_returns_only_declared_columns():
    client.post('/api/positions', json={'p4_status': 'อนุมัติ'})
    row = client.get('/api/positions').get_json()[0]
    expected = {'id', *app.COLUMNS}
    assert set(row) == expected, f'unexpected columns: {set(row) ^ expected}'
    assert 'file_data' not in row, 'base64 column still reaches the client'


def a_fresh_database_declares_no_legacy_columns():
    import sqlite3
    con = sqlite3.connect(app.DB_PATH)
    cols = {r[1] for r in con.execute('PRAGMA table_info(positions)')}
    con.close()
    legacy = {c for c in cols if c.startswith(('p1_', 'p2_', 'p3_'))} | {'p4_supervisor', 'p5_remain', 'p5_annual', 'file_data'}
    assert not (cols & legacy), f'legacy columns present: {sorted(cols & legacy)}'


def the_page_keeps_sqlite_as_its_only_store():
    page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'index.html'),
                encoding='utf-8').read()
    assert 'localStorage' not in page, 'the LocalStorage fallback is back, records can diverge again'
    assert 'readAsDataURL' not in page, 'base64 attachments are back, the server drops that field'


def the_api_stores_markup_verbatim_so_escaping_stays_at_the_render_boundary():
    payload = '[{"s1_type": "<img src=x onerror=1>", "s1_no": "001"}]'
    rid = client.post('/api/positions', json={'p4_status': 'อนุมัติ', 'sec1_rows': payload}).get_json()['id']
    row = [x for x in client.get('/api/positions').get_json() if x['id'] == rid][0]
    assert '<img src=x onerror=1>' in row['sec1_rows'], 'the API altered stored markup'


def new_records_store_timestamps_as_iso_8601():
    rid = client.post('/api/positions', json={'p4_status': 'อนุมัติ'}).get_json()['id']
    client.put(f'/api/positions/{rid}', json={'p4_status': 'ถอนคำขอ'})
    row = [x for x in client.get('/api/positions').get_json() if x['id'] == rid][0]
    assert ISO_STAMP.match(row['created']), f"created is not ISO 8601: {row['created']}"
    assert ISO_STAMP.match(row['updated']), f"updated is not ISO 8601: {row['updated']}"


def iso_timestamps_let_sqlite_sort_by_recency():
    con = sqlite3.connect(app.DB_PATH)
    stamps = [r[0] for r in con.execute(
        'SELECT created FROM positions WHERE created != "" ORDER BY created DESC')]
    con.close()
    assert stamps == sorted(stamps, reverse=True), 'ORDER BY created did not produce a sorted result'


def legacy_slash_timestamps_are_migrated_and_the_migration_is_idempotent():
    con = sqlite3.connect(app.DB_PATH)
    con.execute("INSERT INTO positions (p4_status, created, updated) VALUES (?,?,?)",
                ['อนุมัติ', '29/04/2026 14:03', ''])
    rid = con.execute('SELECT last_insert_rowid()').fetchone()[0]
    con.commit()
    app.migrate_timestamps(con)
    con.commit()
    first = con.execute('SELECT created, updated FROM positions WHERE id=?', [rid]).fetchone()
    assert first[0] == '2026-04-29T14:03:00', f'migration produced {first[0]!r}'
    assert first[1] == '', f'an empty updated must stay empty, got {first[1]!r}'
    app.migrate_timestamps(con)
    con.commit()
    again = con.execute('SELECT created, updated FROM positions WHERE id=?', [rid]).fetchone()
    con.close()
    assert tuple(again) == tuple(first), f'second pass changed the value: {tuple(again)}'


def the_page_renders_iso_timestamps_in_thai_format():
    if not NODE:
        raise Skipped('node is not on PATH')
    got = run_js(['fmtStamp'], "console.log(JSON.stringify(["
                 "fmtStamp('2026-04-29T14:03:00'),"
                 "fmtStamp('2026-10-20T09:05:00'),"
                 "fmtStamp(''), fmtStamp(null)]))")
    assert got == ['29/04/2026 14:03', '20/10/2026 09:05', '', ''], got


def the_csv_export_neutralises_spreadsheet_formulas():
    if not NODE:
        raise Skipped('node is not on PATH')
    got = run_js(['csvCell'], "console.log(JSON.stringify(["
                 "csvCell('=1+1'), csvCell('+41'), csvCell('-2'), csvCell('@SUM(A1)'),"
                 "csvCell('ปกติ')]))")
    assert got[:4] == ['"\'=1+1"', '"\'+41"', '"\'-2"', '"\'@SUM(A1)"'], got
    assert got[4] == '"ปกติ"', f'an ordinary value was quoted with a formula guard: {got[4]}'


def the_csv_export_keeps_a_zero_instead_of_blanking_it():
    if not NODE:
        raise Skipped('node is not on PATH')
    got = run_js(['csvCell'], "console.log(JSON.stringify(["
                 "csvCell(0), csvCell('0'), csvCell(null), csvCell(undefined), csvCell('')]))")
    assert got == ['"0"', '"0"', '""', '""', '""'], got


def requirements_txt_is_utf8_without_a_bom():
    raw = open(os.path.join(HERE, 'requirements.txt'), 'rb').read()
    assert not raw.startswith(b'\xff\xfe'), 'still UTF-16LE'
    assert not raw.startswith(b'\xef\xbb\xbf'), 'a UTF-8 BOM is still in front'
    assert b'\x00' not in raw, 'the file still holds NUL bytes, so it is not UTF-8'
    assert 'Flask==' in raw.decode('utf-8'), raw[:40]


def the_api_sends_thai_characters_unescaped():
    assert 'JSON_AS_ASCII' not in APP_SOURCE, 'the dead Flask 2 config key is back'
    client.post('/api/positions', json={'p4_status': 'อนุมัติ'})
    raw = client.get('/api/positions').get_data()
    assert 'อนุมัติ'.encode('utf-8') in raw, 'Thai text is still escaped into \\uXXXX'
    assert b'\\u0e2d' not in raw, 'the response still carries escape sequences'


def uploads_are_served_by_exactly_one_route():
    assert "'static', 'uploads'" not in APP_SOURCE, 'the upload folder is back under static/'
    assert '/static/uploads/' not in PAGE_SOURCE, 'the page still links through the static route'
    static_root = os.path.realpath(app.app.static_folder)
    assert not os.path.isdir(os.path.join(static_root, 'uploads')), \
        f'uploads reachable twice, also at {static_root}/uploads'
    rules = sorted(str(r) for r in app.app.url_map.iter_rules() if 'upload' in str(r))
    assert rules == ['/api/upload', '/uploads/<path:filename>'], rules


def an_oversize_upload_reports_413_in_thai():
    limit = app.app.config['MAX_CONTENT_LENGTH']
    r = post_file('ใหญ่เกิน.pdf', b'x' * (limit + 1024))
    assert r.status_code == 413, f'expected 413, got {r.status_code} {r.get_data()[:120]}'
    body = r.get_json()
    assert body['ok'] is False, body
    assert 'MB' in body['error'] and 'ไฟล์' in body['error'], body['error']
    assert 'Request Entity Too Large' not in body['error'], body['error']


def an_internal_failure_reports_a_thai_message_without_internals():
    r = client.post('/api/positions', json={'p4_status': {'not': 'a scalar'}})
    assert r.status_code == 500, f'expected 500, got {r.status_code} {r.get_data()[:120]}'
    body = r.get_json()
    assert body['ok'] is False, body
    assert body['error'] == 'เกิดข้อผิดพลาดภายในระบบ กรุณาลองใหม่', body['error']
    assert 'parameter' not in body['error'], 'the driver message leaked to the client'


def a_failed_query_still_closes_its_connection():
    opened = []
    real_connect = sqlite3.connect

    def tracking(*a, **kw):
        con = real_connect(*a, **kw)
        opened.append(con)
        return con

    sqlite3.connect = tracking
    try:
        client.post('/api/positions', json={'p4_status': {'not': 'a scalar'}})
    finally:
        sqlite3.connect = real_connect
    assert opened, 'the request never opened a connection, the probe missed'
    for con in opened:
        try:
            con.execute('SELECT 1')
        except sqlite3.ProgrammingError:
            continue
        raise AssertionError('a connection outlived the failed request')


def a_cross_site_write_is_rejected():
    r = client.post('/api/positions',
                    json={'p4_status': 'อนุมัติ'},
                    headers={'Origin': 'http://evil.example'})
    assert r.status_code == 403, f'expected 403, got {r.status_code} {r.get_json()}'
    assert r.get_json()['ok'] is False, r.get_json()
    r = post_file('แนบ.pdf')
    assert r.status_code == 200, 'a request without an Origin header must still work'
    with client:
        same = client.post('/api/positions',
                           json={'p4_status': 'อนุมัติ'},
                           headers={'Origin': 'http://localhost'})
    assert same.status_code == 201, f'a same-origin write was blocked: {same.status_code}'


def a_cross_site_upload_never_reaches_the_disk():
    before = len(os.listdir(app.UPLOAD_FOLDER))
    r = client.post('/api/upload',
                    data={'file': (io.BytesIO(b'%PDF-1.4'), 'ยิงข้ามเว็บ.pdf')},
                    content_type='multipart/form-data',
                    headers={'Origin': 'http://evil.example'})
    assert r.status_code == 403, f'expected 403, got {r.status_code} {r.get_json()}'
    assert r.get_json()['ok'] is False, r.get_json()
    assert len(os.listdir(app.UPLOAD_FOLDER)) == before, 'the rejected upload still landed on disk'


def reading_is_never_blocked_by_the_origin_check():
    r = client.get('/api/positions', headers={'Origin': 'http://evil.example'})
    assert r.status_code == 200, f'a GET was blocked: {r.status_code}'


def an_unknown_page_still_answers_with_html_not_json():
    r = client.get('/ไม่มีหน้านี้')
    assert r.status_code == 404, r.status_code
    assert 'text/html' in r.headers['Content-Type'], r.headers['Content-Type']
    r = client.get('/api/ไม่มีหน้านี้')
    assert r.status_code == 404, r.status_code
    assert r.get_json()['error'] == 'ไม่พบรายการที่ต้องการ', r.get_json()


def the_entry_point_waits_for_the_port_instead_of_sleeping():
    assert 'time.sleep(0.8)' not in APP_SOURCE, 'the fixed sleep is back'
    port = 5099
    assert app.wait_for_port(port, timeout=0.4) is False, 'reported a closed port as open'
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', port))
    srv.listen(1)
    threading.Thread(target=lambda: srv.accept(), daemon=True).start()
    try:
        assert app.wait_for_port(port, timeout=3.0) is True, 'did not notice the port opening'
    finally:
        srv.close()


def the_table_and_dashboard_read_every_position():
    for name in ('renderTable', 'renderDashboard'):
        src = js_function(name)
        assert '[0]' not in src, f'{name} still indexes only the first position'
        assert 'filledRows' in src, f'{name} does not read section 1 through filledRows'


def blank_position_rows_are_neither_counted_nor_displayed():
    if not NODE:
        raise Skipped('node is not on PATH')
    rows = json.dumps([
        {'s1_type': 'ข้าราชการ', 's1_level': 'ชำนาญการ', 's1_no': '001'},
        {'s1_type': 'ข้าราชการ', 's1_level': 'ปฏิบัติการ', 's1_no': '002'},
        {'s1_type': 'พนักงานราชการ', 's1_level': '', 's1_no': '003'},
        {'s1_type': '', 's1_level': '', 's1_no': ''},
    ], ensure_ascii=False)
    got = run_js(['filledRows', 'cell', 'colList'], f'''
const rows = filledRows({json.dumps(rows, ensure_ascii=False)});
console.log(JSON.stringify({{
  kept: rows.length,
  types: colList(rows, 's1_type'),
  levels: colList(rows, 's1_level'),
  empty: colList(filledRows('[]'), 's1_type'),
  broken: filledRows('not json at all').length
}}));''')
    assert got['kept'] == 3, f"blank row was counted: {got['kept']} rows kept"
    assert got['types'] == 'ข้าราชการ, ข้าราชการ, พนักงานราชการ', got['types']
    assert got['levels'] == 'ชำนาญการ, ปฏิบัติการ, -', got['levels']
    assert got['empty'] == '-', got['empty']
    assert got['broken'] == 0, 'malformed JSON must degrade to an empty list'


def external_asset_urls(text):
    """URL ทุกตัวที่สั่งให้เบราว์เซอร์ไปโหลดจากนอกเครื่อง ทั้ง src href และ url() ใน CSS"""
    found = re.findall(r"""(?:src|href)\s*=\s*["'](//[^"']+|https?://[^"']+)""", text)
    found += re.findall(r"""url\(\s*["']?(//[^)"']+|https?://[^)"']+)""", text)
    return sorted(set(found))


def the_page_never_loads_a_resource_from_the_internet():
    """แอปนี้ build เป็น .exe ไว้ใช้บนเครื่องที่ไม่มีเน็ต ทุกไฟล์ที่หน้าเว็บใช้ต้องมาจากเครื่องเอง"""
    page = client.get('/').get_data(as_text=True)
    outside = external_asset_urls(page)
    assert not outside, 'หน้าเว็บยังโหลดจากอินเทอร์เน็ต ' + ', '.join(outside)


def every_asset_the_page_asks_for_is_served_from_disk():
    """ไล่ตามไฟล์ที่หน้าเว็บอ้างรวมถึง url() ชั้นในของ CSS ว่าเสิร์ฟได้จริงและไม่ใช่ไฟล์เปล่า"""
    page = client.get('/').get_data(as_text=True)
    queue = sorted(set(re.findall(r"""(?:src|href)\s*=\s*["'](/static/[^"']+)""", page)))
    assert queue, 'หน้าเว็บไม่ได้อ้างไฟล์ใน static เลย ไลบรารียังไม่ได้ย้ายลงเครื่อง'
    seen = set()
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        res = client.get(path)
        assert res.status_code == 200, f'{path} ตอบ {res.status_code}'
        assert len(res.get_data()) > 500, f'{path} มีแค่ {len(res.get_data())} ไบต์'
        if path.endswith('.css'):
            body = res.get_data(as_text=True)
            outside = external_asset_urls(body)
            assert not outside, f'{path} ยังอ้างไฟล์จากอินเทอร์เน็ต ' + ', '.join(outside)
            queue += [urljoin(path, ref)
                      for ref in re.findall(r"""url\(\s*["']?([^)"'#?]+)""", body)
                      if not ref.startswith('data:')]
    assert len(seen) > 4, f'ไล่ได้แค่ {len(seen)} ไฟล์ ชุดไลบรารีในเครื่องยังไม่ครบ'


def the_build_command_bundles_the_static_folder():
    """PyInstaller เก็บเฉพาะไฟล์ที่สั่งไว้ ถ้าไม่ระบุ static ไลบรารีจะไม่ติดไปกับ .exe"""
    readme = open(os.path.join(HERE, 'README.md'), encoding='utf-8').read()
    for name, text in (('app.py', APP_SOURCE), ('README.md', readme)):
        assert '--add-data "static;static"' in text, \
            f'คำสั่ง build ใน {name} ยังไม่ได้ใส่โฟลเดอร์ static'


def download_from(exporter, records):
    """เรียกฟังก์ชัน export ของจริงจากหน้าเว็บ แล้วคืนสิ่งที่ dl กับ toast ได้รับ

    `dl` คือขอบเขตที่ผู้ใช้มองเห็น ไฟล์ที่เบราว์เซอร์บันทึกคือสิ่งที่ส่งเข้ามาตรงนี้
    เทสจึงวัดที่ซองดาวน์โหลด `{content, name, type}` ไม่ใช่ที่ไส้ในของฟังก์ชัน
    """
    body = (
        'globalThis.allRecords = ' + json.dumps(records, ensure_ascii=False) + ';\n'
        'globalThis.notes = [];\n'
        'globalThis.toast = (msg) => { notes.push(msg); };\n'
        'globalThis.file = null;\n'
        'globalThis.dl = (content, name, type) => { file = {content, name, type}; };\n'
        + exporter + '();\n'
        'console.log(JSON.stringify({file, notes}));'
    )
    return run_js(['doExportCSV', 'doExportJSON', 'csvCell', 'dStr'], body)


BOM = '﻿'


def csv_table(content):
    """แยกไฟล์ CSV เป็นหัวตารางกับแถวข้อมูล ใช้ได้เพราะค่าที่เทสใส่ไม่มีลูกน้ำ"""
    lines = content.lstrip(BOM).split('\n')
    return lines[0].split(','), [line.split(',') for line in lines[1:]]


def the_json_export_hands_back_every_record_unchanged():
    if not NODE:
        raise Skipped('node is not on PATH')
    records = [
        {'id': 1, 'p1_title': 'กองการเจ้าหน้าที่', 'p5_salary': 0,
         'sec1_rows': '[{"s1_no": "001"}]'},
        {'id': 2, 'p1_title': 'สำนักงานปลัดสำนักนายกรัฐมนตรี "ฯ"', 'p5_salary': None,
         'sec1_rows': '[]'},
    ]
    got = download_from('doExportJSON', records)
    assert json.loads(got['file']['content']) == records, got['file']['content']
    assert got['file']['type'] == 'application/json', got['file']['type']


def the_json_export_names_the_file_with_the_date():
    if not NODE:
        raise Skipped('node is not on PATH')
    before = datetime.now(timezone.utc).strftime('%Y%m%d')
    got = download_from('doExportJSON', [{'id': 1}])
    after = datetime.now(timezone.utc).strftime('%Y%m%d')
    assert got['file']['name'] in (f'pos_{before}.json', f'pos_{after}.json'), got['file']['name']


def an_export_with_no_records_warns_instead_of_writing_an_empty_file():
    if not NODE:
        raise Skipped('node is not on PATH')
    for exporter in ('doExportCSV', 'doExportJSON'):
        got = download_from(exporter, [])
        assert got['file'] is None, f'{exporter} ดาวน์โหลดไฟล์เปล่าออกไป'
        notes = got['notes']
        assert notes == ['ไม่มีข้อมูล'], f'{exporter} เตือนว่า {notes}'


def the_csv_export_flattens_section_rows_into_columns():
    if not NODE:
        raise Skipped('node is not on PATH')
    rows = json.dumps([{'s1_type': 'ข้าราชการ', 's1_no': '001'}], ensure_ascii=False)
    got = download_from('doExportCSV', [{'id': 1, 'sec1_rows': rows}])
    header, body = csv_table(got['file']['content'])
    assert 'sec1_rows' not in header, 'คอลัมน์ JSON ดิบยังติดไปกับไฟล์'
    assert 'sec1_rows_1_s1_type' in header, header
    assert body[0][header.index('sec1_rows_1_s1_type')] == '"ข้าราชการ"', body[0]
    assert body[0][header.index('sec1_rows_1_s1_no')] == '"001"', body[0]


def the_csv_export_keeps_a_section_that_is_not_valid_json():
    if not NODE:
        raise Skipped('node is not on PATH')
    got = download_from('doExportCSV', [{'id': 1, 'sec1_rows': 'ไม่ใช่ json'}])
    header, body = csv_table(got['file']['content'])
    assert 'sec1_rows' in header, 'ข้อมูลที่ parse ไม่ได้หายไปจากไฟล์ทั้งคอลัมน์'
    assert body[0][header.index('sec1_rows')] == '"ไม่ใช่ json"', body[0]


def the_csv_export_keeps_every_row_the_same_width():
    if not NODE:
        raise Skipped('node is not on PATH')
    records = [
        {'id': 1, 'sec1_rows': '[{"s1_no": "001"}, {"s1_no": "002"}]'},
        {'id': 2, 'sec1_rows': '[]'},
    ]
    got = download_from('doExportCSV', records)
    header, body = csv_table(got['file']['content'])
    widths = {len(row) for row in body} | {len(header)}
    assert len(widths) == 1, f'แต่ละแถวมีจำนวนช่องไม่เท่ากัน {widths}'


def the_csv_export_starts_with_a_bom_so_excel_reads_thai():
    if not NODE:
        raise Skipped('node is not on PATH')
    got = download_from('doExportCSV', [{'id': 1, 'p1_title': 'กองการเจ้าหน้าที่'}])
    assert got['file']['content'].startswith(BOM), 'ไม่มี BOM นำหน้า Excel จะอ่านภาษาไทยเป็นขยะ'
    assert 'charset=utf-8' in got['file']['type'], got['file']['type']


def the_pdf_export_escapes_markup_from_the_record():
    if not NODE:
        raise Skipped('node is not on PATH')
    payload = '<script>alert(1)</script>'
    record = {
        'p4_note': payload,
        'p4_date': '2026-10-22',
        'sec1_rows': json.dumps([{'s1_type': payload, 's1_no': '001'}], ensure_ascii=False),
        'sec2_rows': '[]',
        'sec3_rows': '[]',
    }
    body = (
        'globalThis.getForm = () => (' + json.dumps(record, ensure_ascii=False) + ');\n'
        'globalThis.written = "";\n'
        'globalThis.window = {open: () => ({document: '
        '{write: (s) => { written += s; }, close: () => {}}})};\n'
        'exportPDFRecord();\n'
        'console.log(JSON.stringify(written));'
    )
    html = run_js(['exportPDFRecord', 'esc', 'fmtDate'], body)
    assert payload not in html, 'หน้า PDF เขียนแท็กจากข้อมูลผู้ใช้ลงไปตรงๆ'
    assert html.count('&lt;script&gt;alert(1)&lt;/script&gt;') == 2, html.count('&lt;script&gt;')
    assert '22/10/2026' in html, 'วันที่ในหน้า PDF ไม่ได้แปลงเป็นรูปแบบไทย'


CHECKS = [
    upload_accepts_a_thai_filename,
    upload_keeps_the_extension_when_the_name_has_several_dots,
    upload_rejects_an_extension_outside_the_allowlist,
    upload_never_writes_outside_the_upload_folder,
    put_reports_404_for_a_record_that_does_not_exist,
    put_writes_the_value_for_a_record_that_does_exist,
    post_drops_keys_outside_the_allowlist,
    deleting_a_record_removes_its_attached_file,
    deleting_every_record_removes_every_attached_file,
    replacing_an_attachment_removes_the_previous_file,
    the_record_list_returns_only_declared_columns,
    a_fresh_database_declares_no_legacy_columns,
    the_page_keeps_sqlite_as_its_only_store,
    the_bundled_entry_point_never_enables_the_werkzeug_debugger,
    the_bundled_entry_point_binds_loopback_only,
    the_api_stores_markup_verbatim_so_escaping_stays_at_the_render_boundary,
    an_oversize_upload_reports_413_in_thai,
    an_internal_failure_reports_a_thai_message_without_internals,
    a_failed_query_still_closes_its_connection,
    a_cross_site_write_is_rejected,
    a_cross_site_upload_never_reaches_the_disk,
    reading_is_never_blocked_by_the_origin_check,
    an_unknown_page_still_answers_with_html_not_json,
    the_entry_point_waits_for_the_port_instead_of_sleeping,
    new_records_store_timestamps_as_iso_8601,
    iso_timestamps_let_sqlite_sort_by_recency,
    legacy_slash_timestamps_are_migrated_and_the_migration_is_idempotent,
    the_page_renders_iso_timestamps_in_thai_format,
    the_csv_export_neutralises_spreadsheet_formulas,
    the_csv_export_keeps_a_zero_instead_of_blanking_it,
    requirements_txt_is_utf8_without_a_bom,
    the_api_sends_thai_characters_unescaped,
    uploads_are_served_by_exactly_one_route,
    the_table_and_dashboard_read_every_position,
    blank_position_rows_are_neither_counted_nor_displayed,
    the_page_never_loads_a_resource_from_the_internet,
    every_asset_the_page_asks_for_is_served_from_disk,
    the_build_command_bundles_the_static_folder,
    the_json_export_hands_back_every_record_unchanged,
    the_json_export_names_the_file_with_the_date,
    an_export_with_no_records_warns_instead_of_writing_an_empty_file,
    the_csv_export_flattens_section_rows_into_columns,
    the_csv_export_keeps_a_section_that_is_not_valid_json,
    the_csv_export_keeps_every_row_the_same_width,
    the_csv_export_starts_with_a_bom_so_excel_reads_thai,
    the_pdf_export_escapes_markup_from_the_record,
]


def main():
    """--no-skip ทำให้เคสที่ข้ามนับเป็นตก ใช้ใน CI ที่ต้องมีเครื่องมือครบทุกตัว"""
    strict = '--no-skip' in sys.argv
    failed = skipped = 0
    for fn in CHECKS:
        try:
            fn()
            print(f'PASS  {fn.__name__}')
        except Skipped as e:
            if strict:
                failed += 1
                print(f'FAIL  {fn.__name__}\n        {e}')
                continue
            skipped += 1
            print(f'SKIP  {fn.__name__}\n        {e}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL  {fn.__name__}\n        {e}')
        except Exception as e:
            failed += 1
            print(f'ERROR {fn.__name__}\n        {type(e).__name__}: {e}')
    shutil.rmtree(TMP, ignore_errors=True)
    tail = f', {skipped} skipped' if skipped else ''
    print(f'\n{len(CHECKS) - failed - skipped}/{len(CHECKS)} passed{tail}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
