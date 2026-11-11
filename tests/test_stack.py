"""Run isolated database tests, connector suites, and read-only MCP smoke checks."""
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def run(*args, env=None, cwd=None):
    subprocess.run([sys.executable, *args], env=env, cwd=cwd, check=True, timeout=180)


def test_migration():
    schema = 'migration_test_' + uuid4().hex
    dsn = os.environ['EDA_DATABASE_URL']
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with sqlite3.connect(path / 'pantry.sqlite3') as c:
                c.executescript('''
                CREATE TABLE stock(id TEXT PRIMARY KEY,name TEXT,quantity TEXT,unit TEXT,location TEXT,expires_on TEXT,note TEXT,external_ids TEXT,revision INTEGER,updated_at TEXT);
                CREATE TABLE operations(key TEXT PRIMARY KEY,fingerprint TEXT,result TEXT,created_at TEXT);
                CREATE TABLE events(id INTEGER PRIMARY KEY,operation_key TEXT,stock_id TEXT,action TEXT,before_quantity TEXT,after_quantity TEXT,reason TEXT,created_at TEXT);
                ''')
                c.execute('INSERT INTO stock VALUES(?,?,?,?,?,?,?,?,?,?)', ('fixture', 'Яйца', '8', 'pcs', 'холодильник', None, '', '{}', 2, '2026-11-10'))
                c.execute('INSERT INTO operations VALUES(?,?,?,?)', ('fixture:op', 'digest', '{}', '2026-11-10'))
                c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)', (17, 'fixture:op', 'fixture', 'receive', None, '8', 'сверка', '2026-11-10'))
            (path / 'lavka.json').write_text(json.dumps({'cookies': {'Session_id': 'fixture-only'}}))
            (path / 'fatsecret-token.json').write_text(json.dumps({'oauth_token': 'fixture-only', 'oauth_token_secret': 'fixture-only'}))
            (path / 'fatsecret.env').write_text('FATSECRET_CONSUMER_KEY=fixture\nFATSECRET_CONSUMER_SECRET=fixture\n')
            test_dsn = make_conninfo(dsn, options=f'-csearch_path={schema}')
            env = dict(os.environ, EDA_DATABASE_URL=test_dsn, PANTRY_SCHEMA=schema, LEGACY_DIR=str(path))
            run('/app/pantry/migrate.py', env=env)
            run('/app/pantry/migrate.py', env=env)
            with psycopg.connect(test_dsn) as c:
                assert c.execute('SELECT quantity FROM stock').fetchone()[0] == '8'
                assert c.execute('SELECT COUNT(*) FROM events').fetchone()[0] == 1
                assert c.execute("SELECT nextval(pg_get_serial_sequence('events','id'))").fetchone()[0] == 18
                assert c.execute('SELECT COUNT(*) FROM connector_state').fetchone()[0] == 4
            # Verify JSON configuration really uses PostgreSQL, not file fallback.
            run('-c', "from yandex_lavka_mcp.config import load_config,save_config; c=load_config(); assert c.is_authenticated(); c.context['test']='persisted'; save_config(c); assert load_config().context['test']=='persisted'; from fatsecret_connector.config import load_settings; assert load_settings().consumer_key=='fixture'", env=env)
    finally:
        with psycopg.connect(dsn, autocommit=True) as c:
            c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
    print('Migration and connector state persistence: OK', flush=True)


async def smoke():
    for host, port, required, read_tool in [('pantry', 8002, 'receive_stock', 'pantry_status'), ('fatsecret', 8001, 'get_diary', None), ('lavka', 8000, 'checkout_preview', 'lavka_status')]:
        async with streamable_http_client(f'http://{host}:{port}/mcp') as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert required in names, (host, names)
                if read_tool:
                    result = await session.call_tool(read_tool, {})
                    assert not result.isError, host
                print(f'MCP HTTP {host}: OK, {len(names)} tools', flush=True)


if __name__ == '__main__':
    os.environ['PYTHONPATH'] = '/app:/app/pantry'
    run('/tests/pantry/test_server.py')
    test_migration()
    schema = 'startup_test_' + uuid4().hex
    dsn = os.environ['EDA_DATABASE_URL']
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        env = dict(os.environ, EDA_DATABASE_URL=make_conninfo(dsn, options=f'-csearch_path={schema}'), PANTRY_SCHEMA=schema, MCP_TRANSPORT='stdio')
        # EOF shuts down stdio after the actual server startup path has initialized tables.
        for _ in range(2):
            subprocess.run([sys.executable, '/app/pantry/server.py'], input='', text=True, env=env, check=True, timeout=20)
        with psycopg.connect(env['EDA_DATABASE_URL']) as c:
            tables = {r[0] for r in c.execute('SELECT tablename FROM pg_tables WHERE schemaname=%s', (schema,))}
            assert {'stock', 'operations', 'events', 'connector_state'} <= tables
        print('Pantry automatic PostgreSQL initialization and restart: OK', flush=True)
    finally:
        with psycopg.connect(dsn, autocommit=True) as c:
            c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
    local_env = dict(os.environ)
    local_env.pop('EDA_DATABASE_URL', None)
    local_env.pop('FATSECRET_MCP_HOST', None)
    run('-m', 'unittest', 'discover', '-s', 'tests', env=local_env, cwd='/tests/fatsecret')
    run('-m', 'pytest', '-q', 'tests', '--asyncio-mode=auto', '-p', 'no:cacheprovider', env=local_env, cwd='/tests/lavka')
    asyncio.run(smoke())
    print('All checks passed.', flush=True)
