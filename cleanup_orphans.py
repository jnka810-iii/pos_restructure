"""Remove uploaded files no record points at. Dry-run by default.

    .venv\\Scripts\\python.exe cleanup_orphans.py           list them
    .venv\\Scripts\\python.exe cleanup_orphans.py --apply   delete them
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app


def main():
    apply = '--apply' in sys.argv

    if not os.path.isdir(app.UPLOAD_FOLDER):
        print(f'no upload folder at {app.UPLOAD_FOLDER}')
        return 0

    con = sqlite3.connect(app.DB_PATH)
    referenced = {r[0] for r in con.execute(
        'SELECT file_name FROM positions WHERE file_name IS NOT NULL AND file_name != ""')}
    con.close()

    on_disk = {f for f in os.listdir(app.UPLOAD_FOLDER)
               if os.path.isfile(os.path.join(app.UPLOAD_FOLDER, f))}
    orphans = sorted(on_disk - referenced)
    missing = sorted(referenced - on_disk)

    print(f'uploads folder : {app.UPLOAD_FOLDER}')
    print(f'on disk        : {len(on_disk)}')
    print(f'referenced     : {len(referenced)}')
    print(f'orphaned       : {len(orphans)}')

    if missing:
        print(f'\nWARNING: {len(missing)} record(s) point at a file that is gone:')
        for name in missing:
            print(f'  {name}')

    if not orphans:
        print('\nnothing to remove')
        return 0

    print('\norphaned files:')
    total = 0
    for name in orphans:
        size = os.path.getsize(os.path.join(app.UPLOAD_FOLDER, name))
        total += size
        print(f'  {name}  {size/1024:.1f} KB')
    print(f'reclaimable: {total/1024:.1f} KB')

    if not apply:
        print('\ndry run, nothing deleted. Re-run with --apply to remove them.')
        return 0

    for name in orphans:
        os.remove(os.path.join(app.UPLOAD_FOLDER, name))
    print(f'\ndeleted {len(orphans)} file(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
