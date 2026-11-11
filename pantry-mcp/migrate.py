"""One-time, transactional import. Source files are read-only and never logged."""
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import dotenv_values
from psycopg import sql
from psycopg.types.json import Jsonb

sys.path.insert(0, '/app/pantry')
import server
from eda_state import initialize_state


def migrate():
    legacy = Path(os.environ.get('LEGACY_DIR', '/legacy'))
    initialize_state()
    server.initialize()
    with server.connect(True) as c:
        def seed(key, value):
            c.execute('INSERT INTO connector_state(key,value) VALUES(%s,%s) ON CONFLICT(key) DO NOTHING', (key, Jsonb(value)))

        for key, filename in [('lavka_config', 'lavka.json'), ('fatsecret_token', 'fatsecret-token.json')]:
            path = legacy / filename
            if path.is_file():
                seed(key, json.loads(path.read_text(encoding='utf-8-sig')))
        env = dotenv_values(legacy / 'fatsecret.env')
        if env.get('FATSECRET_CONSUMER_KEY') and env.get('FATSECRET_CONSUMER_SECRET'):
            seed('fatsecret_credentials', {'consumer_key': env['FATSECRET_CONSUMER_KEY'], 'consumer_secret': env['FATSECRET_CONSUMER_SECRET']})

        path = legacy / 'pantry.sqlite3'
        if path.exists():
            # SQLite backup produces a stable view even if an old client is still connected.
            with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as src:
                src.row_factory = sqlite3.Row
                src.execute('BEGIN')
                tables = {t: [dict(row) for row in src.execute(f'SELECT * FROM {t}')] for t in ('stock', 'operations', 'events')}
            digest = hashlib.sha256(json.dumps(tables, sort_keys=True).encode()).hexdigest()
            previous = c.execute("SELECT value FROM connector_state WHERE key='pantry_sqlite_import'").fetchone()
            if previous:
                if previous['value']['digest'] != digest:
                    raise RuntimeError('Legacy SQLite changed after import; manual reconciliation required')
            else:
                if any(c.execute(sql.SQL('SELECT COUNT(*) AS n FROM {}').format(sql.Identifier(t))).fetchone()['n'] for t in tables):
                    raise RuntimeError('PostgreSQL pantry is not empty; refusing to merge automatically')
                for table in ('stock', 'operations', 'events'):
                    for row in tables[table]:
                        columns = list(row)
                        c.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, columns)), sql.SQL(',').join(sql.Placeholder() for _ in columns)), list(row.values()))
                c.execute("SELECT setval(pg_get_serial_sequence('events','id'), GREATEST(COALESCE((SELECT MAX(id) FROM events),0),1), EXISTS(SELECT 1 FROM events))")
                seed('pantry_sqlite_import', {'digest': digest, 'rows': {t: len(v) for t, v in tables.items()}})
    print('PostgreSQL initialized; legacy import complete. Source files unchanged.')


if __name__ == '__main__':
    migrate()
