"""Food search and serving tools."""
from mcp.server.fastmcp import FastMCP

from ..client import FatSecretClient
from . import READ


class FoodTools:
    def __init__(self, client: FatSecretClient):
        self.client = client

    def search_foods(self, query: str, page: int = 0) -> dict:
        """Find food IDs. Results may depend on API edition/region; don't infer nutrition from the name."""
        if not query.strip() or page < 0:
            raise ValueError('Nonempty query and nonnegative page required')
        return self.client.api('foods/search/v1', {'search_expression': query, 'page_number': page, 'max_results': 20})

    def get_food(self, food_id: str) -> dict:
        """Get food nutrition and exact serving_id, number_of_units and metric_serving_amount."""
        if not food_id.isdigit():
            raise ValueError('Numeric food_id required')
        return self.client.api('food/v6', {'food_id': food_id})


def register_tools(server: FastMCP, client: FatSecretClient):
    tools = FoodTools(client)
    server.add_tool(tools.search_foods, annotations=READ)
    server.add_tool(tools.get_food, annotations=READ)
