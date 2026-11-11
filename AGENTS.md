# Eda workspace

- Use the root compose.yaml for all production services. Do not start native Python or a second SQLite-backed pantry.
- Runtime storage is PostgreSQL. shared/eda_state.py holds shared connector state; pantry-mcp/server.py owns inventory tables and prepares the schema at startup.
- Docker build files belong in docker/, shared code in shared/, and stack integration tests in tests/.
- Never display or commit .env, tokens, cookies, database connection strings, or database dumps.
- Do not bake secret/config/data files into images; keep .dockerignore protections.
- Run docker compose build tests and docker compose run --rm tests for changes to storage or connectors.
- Tests must use isolated PostgreSQL schemas and mocked external writes. Never order groceries or modify the real diary as a test.
- Do not delete volumes or overwrite existing PostgreSQL state during migration.
- Preserve the FatSecret single-write/no-retry behavior and Lavka checkout preview/explicit payment confirmation.
