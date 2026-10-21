"""Drop columns the code no longer references. Dry-run by default.

    .venv\\Scripts\\python.exe migrate_schema.py           show the plan
    .venv\\Scripts\\python.exe migrate_schema.py --apply   back up, then drop
"""

import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app


def table_columns(con):
    return [r[1] for r in con.execute('PRAGMA table_info(positions)')]


def backup(path):
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    dest = f'{path}.{stamp}.bak'
    src = sqlite3.connect(path)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest


def main():
    apply = '--apply' in sys.argv
    con = sqlite3.connect(app.DB_PATH)
    con.row_factory = sqlite3.Row

    keep = {'id', *app.COLUMNS}
    present = table_columns(con)
    doomed = [c for c in present if c not in keep]
    rows = con.execute('SELECT COUNT(*) FROM positions').fetchone()[0]

    print(f'database : {app.DB_PATH}')
    print(f'rows     : {rows}')
    print(f'columns  : {len(present)} present, {len(keep)} declared, {len(doomed)} to drop')

    if not doomed:
        print('\nnothing to do, the schema already matches app.COLUMNS')
        con.close()
        return 0

    carrying = []
    for col in doomed:
        used = con.execute(
            f'SELECT COUNT(*) FROM positions WHERE "{col}" IS NOT NULL AND "{col}" != ""').fetchone()[0]
        if used:
            carrying.append((col, used))

    print('\nto drop:')
    for col in doomed:
        note = next((f'  <-- holds data in {n} row(s)' for c, n in carrying if c == col), '')
        print(f'  {col}{note}')

    if carrying:
        print(f'\nWARNING: {len(carrying)} column(s) still hold values. Review before applying.')

    if not apply:
        print('\ndry run, nothing changed. Re-run with --apply to perform the migration.')
        con.close()
        return 0

    con.close()
    saved = backup(app.DB_PATH)
    print(f'\nbackup written to {saved}')

    con = sqlite3.connect(app.DB_PATH)
    for col in doomed:
        con.execute(f'ALTER TABLE positions DROP COLUMN "{col}"')
    con.commit()
    remaining = table_columns(con)
    after = con.execute('SELECT COUNT(*) FROM positions').fetchone()[0]
    con.close()

    print(f'dropped {len(doomed)} column(s)')
    print(f'columns now : {len(remaining)}')
    print(f'rows now    : {after}')
    assert after == rows, 'row count changed, restore the backup'
    assert set(remaining) == keep, f'schema still off: {set(remaining) ^ keep}'
    print('schema matches app.COLUMNS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
