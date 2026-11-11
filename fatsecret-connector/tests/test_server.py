import unittest
from unittest.mock import Mock

from fatsecret_connector.client import FatSecretClient
from fatsecret_connector.server import create_server


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_annotations_and_schemas(self):
        server = create_server(Mock(spec=FatSecretClient))
        tools = {tool.name: tool for tool in await server.list_tools()}
        self.assertEqual(set(tools), {'search_foods', 'get_food', 'get_diary', 'add_food', 'delete_food'})
        for name in ('search_foods', 'get_food', 'get_diary'):
            self.assertTrue(tools[name].annotations.readOnlyHint)
        self.assertFalse(tools['add_food'].annotations.readOnlyHint)
        self.assertFalse(tools['add_food'].annotations.idempotentHint)
        self.assertEqual(set(tools['add_food'].inputSchema['required']),
                         {'date', 'meal', 'food_id', 'serving_id', 'number_of_units', 'name'})
        self.assertFalse(tools['delete_food'].annotations.readOnlyHint)
        self.assertTrue(tools['delete_food'].annotations.destructiveHint)
        self.assertFalse(tools['delete_food'].annotations.idempotentHint)
        self.assertEqual(set(tools['delete_food'].inputSchema['required']),
                         {'date', 'food_entry_id'})
        for tool in tools.values():
            self.assertNotIn('self', tool.inputSchema['properties'])
            self.assertNotIn('client', tool.inputSchema['properties'])
        self.assertEqual(server.settings.host, '127.0.0.1')

    async def test_servers_use_their_own_clients(self):
        first = Mock(spec=FatSecretClient)
        second = Mock(spec=FatSecretClient)
        first.api.return_value = {'foods': []}
        second.api.return_value = {'foods': []}
        one = create_server(first)
        two = create_server(second)
        await one.call_tool('search_foods', {'query': 'milk'})
        first.api.assert_called_once()
        second.api.assert_not_called()
        await two.call_tool('search_foods', {'query': 'bread'})
        second.api.assert_called_once_with(
            'foods/search/v1', {'search_expression': 'bread', 'page_number': 0, 'max_results': 20})
