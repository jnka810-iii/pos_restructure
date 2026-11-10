r"""จัดการบัญชีผู้ใช้งานสำหรับโหมดวง LAN  รันบนเครื่องแม่ข่ายเท่านั้น

    .venv\Scripts\python.exe manage_users.py list
    .venv\Scripts\python.exe manage_users.py add somchai "สมชาย ใจดี"
    .venv\Scripts\python.exe manage_users.py passwd somchai
    .venv\Scripts\python.exe manage_users.py remove somchai

ตั้งใจให้ไม่มีหน้าจัดการบัญชีในเว็บ เพราะเครื่องแม่ข่ายคือเครื่องของผู้ดูแลอยู่แล้ว
จึงไม่ต้องสร้างบทบาท "ผู้ดูแล" ขึ้นมาในระบบ

การลบบัญชีไม่กระทบชื่อผู้บันทึกบนคำขอเดิม เพราะชื่อนั้นถูกคัดลอกเก็บไว้ตั้งแต่ตอนบันทึก
ดู docs/adr/0002-recorder-is-a-copied-name.md
"""

import getpass
import re
import sqlite3
import sys

from werkzeug.security import generate_password_hash

import app

USERNAME_RULE = re.compile(r'^[a-z0-9][a-z0-9._-]{2,31}$')
MIN_PASSWORD  = 8


def ask_password(username):
    """ถามรหัสผ่านสองครั้งโดยไม่แสดงบนหน้าจอ คืน None ถ้าผู้ใช้ยกเลิกหรือกรอกไม่ผ่าน"""
    first = getpass.getpass(f'รหัสผ่านใหม่ของ {username}: ')
    if len(first) < MIN_PASSWORD:
        print(f'รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD} ตัวอักษร')
        return None
    if first != getpass.getpass('พิมพ์รหัสผ่านอีกครั้ง: '):
        print('รหัสผ่านสองครั้งไม่ตรงกัน')
        return None
    return first


def cmd_list(con, args):
    rows = con.execute('SELECT username, display_name, created FROM users ORDER BY username').fetchall()
    if not rows:
        print('ยังไม่มีบัญชีผู้ใช้งาน คนในวง LAN จึงยังเข้าระบบไม่ได้เลย')
        return 0
    width = max(len(r['username']) for r in rows)
    for r in rows:
        print(f"  {r['username']:<{width}}  {r['display_name']}   (สร้างเมื่อ {r['created'] or '-'})")
    return 0


def cmd_add(con, args):
    if len(args) != 2:
        print('ใช้: manage_users.py add <ชื่อผู้ใช้งาน> "<ชื่อแสดงผล>"')
        return 2
    username, display_name = args
    if not USERNAME_RULE.match(username):
        print('ชื่อผู้ใช้งานใช้ได้เฉพาะ a-z 0-9 . _ - ยาว 3 ถึง 32 ตัว และขึ้นต้นด้วยตัวอักษรหรือตัวเลข')
        return 2
    if not display_name.strip():
        print('ชื่อแสดงผลว่างไม่ได้ เพราะเป็นชื่อที่จะไปปรากฏเป็นผู้บันทึกบนคำขอ')
        return 2
    password = ask_password(username)
    if password is None:
        return 1
    try:
        con.execute('INSERT INTO users (username, display_name, password_hash, created) VALUES (?,?,?,?)',
                    [username, display_name.strip(), generate_password_hash(password), app.now_iso()])
    except sqlite3.IntegrityError:
        print(f'มีบัญชี {username} อยู่แล้ว ถ้าต้องการตั้งรหัสผ่านใหม่ให้ใช้คำสั่ง passwd')
        return 1
    con.commit()
    print(f'เพิ่มบัญชี {username} ({display_name.strip()}) แล้ว')
    return 0


def cmd_passwd(con, args):
    if len(args) != 1:
        print('ใช้: manage_users.py passwd <ชื่อผู้ใช้งาน>')
        return 2
    username = args[0]
    if not con.execute('SELECT 1 FROM users WHERE username=?', [username]).fetchone():
        print(f'ไม่พบบัญชี {username}')
        return 1
    password = ask_password(username)
    if password is None:
        return 1
    con.execute('UPDATE users SET password_hash=? WHERE username=?',
                [generate_password_hash(password), username])
    con.commit()
    print(f'ตั้งรหัสผ่านใหม่ของ {username} แล้ว เซสชันที่เปิดค้างอยู่ยังใช้ได้จนหมดอายุ')
    return 0


def cmd_remove(con, args):
    if len(args) != 1:
        print('ใช้: manage_users.py remove <ชื่อผู้ใช้งาน>')
        return 2
    username = args[0]
    if not con.execute('DELETE FROM users WHERE username=?', [username]).rowcount:
        print(f'ไม่พบบัญชี {username}')
        return 1
    con.commit()
    print(f'ลบบัญชี {username} แล้ว ชื่อผู้บันทึกบนคำขอเดิมไม่เปลี่ยน')
    return 0


COMMANDS = {'list': cmd_list, 'add': cmd_add, 'passwd': cmd_passwd, 'remove': cmd_remove}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip())
        return 2
    app.init_db()
    con = app.get_db()
    try:
        return COMMANDS[argv[1]](con, argv[2:])
    finally:
        con.close()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
