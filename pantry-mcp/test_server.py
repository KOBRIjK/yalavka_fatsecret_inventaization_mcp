import asyncio
import concurrent.futures
import json
import os
import psycopg
from psycopg import sql
import tempfile
import sys
import unittest
from uuid import uuid4
from pathlib import Path

import server as s
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class PantryTests(unittest.TestCase):
    def setUp(self):
        self.old = s.SCHEMA
        s.SCHEMA = 'test_' + uuid4().hex
        with psycopg.connect(s.DATABASE_URL, autocommit=True) as c:
            c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(s.SCHEMA)))
        self.tmp = tempfile.TemporaryDirectory()
        self.old_backup = os.environ.get('PANTRY_BACKUP_DIR')
        os.environ['PANTRY_BACKUP_DIR'] = self.tmp.name
        s.initialize()

    def tearDown(self):
        with psycopg.connect(s.DATABASE_URL, autocommit=True) as c:
            c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(s.SCHEMA)))
        s.SCHEMA = self.old
        if self.old_backup is None:
            os.environ.pop('PANTRY_BACKUP_DIR', None)
        else:
            os.environ['PANTRY_BACKUP_DIR'] = self.old_backup
        self.tmp.cleanup()

    def receive(self, quantity='10', key='initial'):
        return s.receive_stock([s.StockInput(name='Яйца', quantity=quantity, unit='pcs')], key, 'сверка')

    def test_retry_conflict_and_unknown(self):
        first = self.receive()
        self.assertEqual(first['items'], self.receive()['items'])
        self.assertTrue(self.receive()['already_applied'])
        with self.assertRaises(ValueError):
            self.receive('20')
        self.assertEqual(len(s.stock_history()['events']), 1)
        item = self.receive(None, 'unknown')['items'][0]
        with self.assertRaises(ValueError):
            s.change_stock([s.StockChange(stock_id=item['id'], action='consume', quantity='1')], 'consume', 'еда')
        s.change_stock([s.StockChange(stock_id=item['id'], action='set', quantity='3', expected_revision=1)], 'count', 'сверка')
        with self.assertRaises(ValueError):
            s.change_stock([s.StockChange(stock_id=item['id'], action='set', quantity='5', expected_revision=1)], 'stale', 'сверка')

    def test_atomicity_precision_and_validation(self):
        a = self.receive('1.2')['items'][0]['id']
        b = self.receive('2', 'second')['items'][0]['id']
        with self.assertRaises(ValueError):
            s.change_stock([s.StockChange(stock_id=a, action='consume', quantity='0.2'),
                            s.StockChange(stock_id=b, action='consume', quantity='3')], 'bad', 'еда')
        self.assertEqual({r['id']: r['quantity'] for r in s.list_stock()['items']}[a], '1.2')
        s.change_stock([s.StockChange(stock_id=a, action='consume', quantity='0.2')], 'good', 'еда')
        self.assertEqual({r['id']: r['quantity'] for r in s.list_stock()['items']}[a], '1.0')
        self.assertEqual(len(s.stock_history()['events']), 3)
        for bad in ['NaN', 'Infinity', '-1', '0.0000001']:
            with self.assertRaises(ValueError):
                self.receive(bad, bad)
        self.assertEqual(s.list_stock('ЯЙЦА')['count'], 2)

    def test_concurrent_spend_and_backup(self):
        item = self.receive('1')['items'][0]
        def consume(key):
            try:
                s.change_stock([s.StockChange(stock_id=item['id'], action='consume', quantity='1')], key, 'еда')
                return True
            except ValueError:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(consume, ['one', 'two'])), 1)
        self.assertEqual(s.list_stock()['count'], 0)
        path = s.backup_pantry()['backup']
        backup = json.loads(Path(path).read_text(encoding='utf-8'))
        self.assertEqual(backup['stock'][0]['quantity'], '0')
        self.assertEqual(len(backup['events']), 2)

    def test_stdio_two_sessions_persistence(self):
        async def run():
            env = dict(os.environ, PANTRY_SCHEMA=s.SCHEMA, MCP_TRANSPORT='stdio', PYTHONIOENCODING='utf-8')
            params = StdioServerParameters(command=sys.executable, args=[str(s.ROOT / 'server.py')], env=env)
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as client:
                    init = await client.initialize()
                    self.assertIn('постоянное', init.instructions)
                    names = {t.name for t in (await client.list_tools()).tools}
                    self.assertEqual(len(names), 6)
                    result = await client.call_tool('receive_stock', {'items': [{'name': 'Молоко', 'quantity': '1000', 'unit': 'ml'}], 'operation_key': 'lavka:order:test', 'reason': 'получено'})
                    self.assertFalse(result.isError)
                    error = await client.call_tool('change_stock', {'changes': [{'stock_id': 'missing', 'action': 'consume', 'quantity': '1'}], 'operation_key': 'invalid', 'reason': 'еда'})
                    self.assertTrue(error.isError)
            # A fresh process, just like a different chat, reads the same database.
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as client:
                    await client.initialize()
                    result = await client.call_tool('list_stock', {'query': 'МОЛОКО'})
                    data = json.loads(next(x.text for x in result.content if x.type == 'text'))
                    self.assertEqual(data['items'][0]['quantity'], '1000')
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
