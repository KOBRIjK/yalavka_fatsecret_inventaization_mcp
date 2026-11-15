<!-- mcp-name: io.github.Dudude-bit/yandex-lavka-mcp -->

# yandex-lavka-mcp

[![PyPI](https://img.shields.io/pypi/v/yandex-lavka-mcp.svg)](https://pypi.org/project/yandex-lavka-mcp/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-server-black.svg)](https://modelcontextprotocol.io)

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant order
groceries from **Yandex Lavka** — search products, build a cart, and place a real
order — with an explicit human confirmation before any money is charged.

> [!WARNING]
> **Unofficial.** Yandex Lavka has no public API. This project talks to the same
> private web API that `lavka.yandex.ru` uses, authenticated with **your own**
> Yandex session cookies. It automates your own account, for your own shopping.
>
> - Not affiliated with or endorsed by Yandex. Using it may violate Yandex's
>   Terms of Service, and the private API can change or be blocked at any time.
> - `confirm_order` spends **real money** on your card. Use at your own risk.
> - Provided **as is**, without warranty (see [LICENSE](LICENSE)).

## What it does

| Tool | Charges? | What it does |
|------|:---:|------|
| `lavka_status` | — | Is the session + location set up? |
| `list_addresses` | — | Your saved Lavka addresses, by name. |
| `use_address` | — | Switch delivery to a saved address by name. |
| `set_delivery_address` | — | Set delivery to any address by text (any city). |
| `set_location` | — | Set delivery point by raw lat/lon. |
| `search_products` | — | Search the catalog at the current location. |
| `get_product` | — | Product detail by id, slug or Lavka link, incl. nutrition (КБЖУ per 100 g / per portion, as the card shows it). |
| `list_categories` | — | Catalog menu: category groups with their categories (per storefront). |
| `get_category_group` | — | Categories inside one catalog group, by group id. |
| `get_category_products` | — | Products in a category + its subcategory shelf counts; optional subcategory filter. |
| `view_cart` | — | Show cart + total. |
| `add_to_cart` | — | Add an item. |
| `update_cart_item` | — | Set exact quantity (0 removes). |
| `clear_cart` | — | Empty the cart. |
| `checkout_preview` | **no** | Full summary: items, subtotal, discount, delivery, ETA, payment, total. |
| `list_payment_methods` | — | Your saved cards and which is the default. |
| `set_payment_method` | — | Choose which card orders charge. |
| `confirm_order` | **YES** | Places the order and charges the default card (or the one set above). |
| `cancel_order` | — | Cancel an order by id. |
| `active_orders` | — | Currently tracked orders with status/ETA. |
| `order_history` | — | Past orders (total, items count, date), paged. |
| `get_order` | — | One order in full: items, totals, address, status. |

**Money safety.** Placing an order is a deliberate two-step flow: `checkout_preview`
returns the full summary and charges nothing; `confirm_order(confirmed_total)`
refuses unless a preview was just run and you pass back the exact total it showed.
Change the cart and the preview is invalidated — you must preview again.

**3-D Secure.** `confirm_order` submits the order and charges the on-file card,
then polls payment status. If your bank requires 3-D Secure, `payment_status`
comes back `wait_user_action` and a `redirect_url` is returned — open it to
finish paying (a headless charge cannot complete 3DS). `cancel_order(order_id)`
cancels.

**Multiple locations / cities.** Catalog, prices and cart are location-scoped.
`use_address("Дача")` switches to a saved address; `set_delivery_address("Казань,
улица Баумана, 1", flat="12")` works for any address in any city (it geocodes via
Lavka's own address search).

## How it's built

- Python 3.12+ · [FastMCP](https://github.com/modelcontextprotocol/python-sdk) · `httpx`.
- `client.py` — the async API client (session auth, CSRF, request building, trims huge payloads).
- `endpoints.py` — every API path in one place (overridable from config, no code change).
- `server.py` — the MCP tools the assistant sees.

The API sits under `https://lavka.yandex.ru/api/v1/providers/*` (plus
`/api/v1/orders/submit` for placing orders). Requests need the CSRF token from
the homepage HTML plus `X-Lavka-Web-*` headers — the client handles this.

## Setup in Eda

Run the `lavka` service through the [root Compose stack](../compose.yaml). The local MCP endpoint is `http://127.0.0.1:8000/mcp`. For initial session import into PostgreSQL, follow the [Eda account setup instructions](../README.md#настройки-аккаунтов-и-перенос-старых-данных). Use `lavka_status` to check the session and delivery location.

## One account = one cart

Lavka keeps a single server-side cart per account, guarded by an optimistic
`cartVersion`. This server serializes its own cart writes and retries on version
conflicts, so parallel tool calls in one session are safe. But **don't drive the
same Yandex account from two places at once** (e.g. this server *and* a second
MCP session, *and* the Lavka app): they all write the one shared cart, and you'll
see items from the other writer appear in yours. Use a single client at a time.

For development checks, follow the [stack test instructions](../README.md#разработка-и-проверки).

## License

[MIT](LICENSE). Unofficial project, not affiliated with Yandex.
