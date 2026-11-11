"""Shared PostgreSQL storage for connector configuration. Never log payloads/DSNs."""
import os

import psycopg
from psycopg.types.json import Jsonb


def initialize_state():
    with psycopg.connect(os.environ['EDA_DATABASE_URL']) as c:
        c.execute('CREATE TABLE IF NOT EXISTS connector_state (key TEXT PRIMARY KEY, value JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())')


def load_state(key):
    with psycopg.connect(os.environ['EDA_DATABASE_URL']) as c:
        row = c.execute('SELECT value FROM connector_state WHERE key=%s', (key,)).fetchone()
        return row[0] if row else None


def save_state(key, value, only_if_absent=False):
    suffix = 'DO NOTHING' if only_if_absent else 'DO UPDATE SET value=EXCLUDED.value, updated_at=now()'
    with psycopg.connect(os.environ['EDA_DATABASE_URL']) as c:
        result = c.execute('INSERT INTO connector_state(key,value) VALUES(%s,%s) ON CONFLICT(key) ' + suffix, (key, Jsonb(value)))
        if only_if_absent and result.rowcount == 0:
            raise ValueError('State already exists; refusing to overwrite')
