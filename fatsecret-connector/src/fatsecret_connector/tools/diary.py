"""Diary reads and validated single-entry writes."""
import math
from typing import Literal

from mcp.server.fastmcp import FastMCP

from ..client import FatSecretClient, days
from . import DELETE, READ, WRITE
from .foods import FoodTools


class DiaryTools:
    def __init__(self, client: FatSecretClient):
        self.client = client
        self.foods = FoodTools(client)

    def get_diary(self, date: str) -> dict:
        """Read existing account food diary for explicit local date YYYY-MM-DD, including calories/macros."""
        return self.client.api('food-entries/v2', {'date': days(date)})

    def add_food(self, date: str, meal: Literal['breakfast', 'lunch', 'dinner', 'other'],
                 food_id: str, serving_id: str, number_of_units: float, name: str) -> dict:
        """Write ONE food entry, only when user requested it. Resolve food and serving first.

        Units follow selected FatSecret serving definition. Never pass grams as units
        without converting against that serving. Never automatically retry a write.
        """
        day = days(date)
        if meal not in ('breakfast', 'lunch', 'dinner', 'other'):
            raise ValueError('Invalid meal')
        if not math.isfinite(number_of_units) or number_of_units <= 0:
            raise ValueError('Positive finite number_of_units required')
        if not name.strip():
            raise ValueError('Food name required')
        food = self.foods.get_food(food_id)['food']
        servings = food.get('servings', {}).get('serving', [])
        if isinstance(servings, dict):
            servings = [servings]
        if not any(str(s['serving_id']) == serving_id for s in servings):
            raise ValueError('Serving does not belong to selected food')
        return self.client.api('food-entries/v1', {
            'date': day, 'meal': meal, 'food_id': food_id,
            'serving_id': serving_id, 'number_of_units': str(number_of_units),
            'food_entry_name': name,
        }, write=True)

    def delete_food(self, date: str, food_entry_id: str) -> dict:
        """Delete ONE diary entry only when the user requested its removal.

        Use food_entry_id from get_diary for explicit local date YYYY-MM-DD,
        never food_id or a guessed ID. Verify the entry belongs to that date.
        Never automatically retry; after any failure read the diary first.
        """
        day = days(date)
        if (not food_entry_id.isascii() or not food_entry_id.isdecimal()
                or not 0 < int(food_entry_id) <= 9223372036854775807):
            raise ValueError('Positive integer food_entry_id required')
        entry_id = str(int(food_entry_id))
        diary = self.get_diary(date)
        entries = (diary.get('food_entries') or {}).get('food_entry') or []
        if isinstance(entries, dict):
            entries = [entries]
        if not any(str(entry.get('food_entry_id')) == entry_id
                   and str(entry.get('date_int')) == str(day) for entry in entries):
            raise ValueError('Food entry not found for selected date; read diary first')
        return self.client.api('food-entries/v1', {'food_entry_id': entry_id},
                               method='DELETE')


def register_tools(server: FastMCP, client: FatSecretClient):
    tools = DiaryTools(client)
    server.add_tool(tools.get_diary, annotations=READ)
    server.add_tool(tools.add_food, annotations=WRITE)
    server.add_tool(tools.delete_food, annotations=DELETE)
