import unittest
from unittest.mock import Mock

from fatsecret_connector.client import FatSecretClient
from fatsecret_connector.tools.foods import FoodTools


class FoodTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock(spec=FatSecretClient)
        self.foods = FoodTools(self.client)

    def test_search_parameters(self):
        self.foods.search_foods('milk', page=2)
        self.client.api.assert_called_once_with(
            'foods/search/v1', {'search_expression': 'milk', 'page_number': 2, 'max_results': 20})

    def test_invalid_search_does_not_call_api(self):
        for query, page in (('', 0), ('  ', 0), ('milk', -1)):
            with self.subTest(query=query, page=page), self.assertRaises(ValueError):
                self.foods.search_foods(query, page)
        self.client.api.assert_not_called()

    def test_food_details(self):
        self.foods.get_food('123')
        self.client.api.assert_called_once_with('food/v6', {'food_id': '123'})

    def test_invalid_food_id_does_not_call_api(self):
        for value in ('', '-1', 'abc'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.foods.get_food(value)
        self.client.api.assert_not_called()
