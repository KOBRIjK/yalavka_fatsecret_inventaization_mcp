# Repository Guidelines

## Project Structure & Module Organization

This Python 3.11+ project connects a single owner's FatSecret diary to MCP clients.

- `src/fatsecret_connector/server.py`: `create_server()` factory and MCP registration.
- `src/fatsecret_connector/tools/foods.py`, `tools/diary.py`: tool validation and behavior.
- `src/fatsecret_connector/client.py`: OAuth sessions, HTTP requests, and date conversion.
- `src/fatsecret_connector/config.py`: explicit settings loading and token paths.
- `src/fatsecret_connector/authorize.py`: interactive OAuth 1.0 authorization.
- `src/fatsecret_connector/__main__.py`: HTTP/stdio command-line entry point.
- Root `server.py` and `authorize.py`: compatibility launchers using root-local config.
- `tests/`: unittest tests, with API calls mocked.
- `pyproject.toml`: dependencies and entry points; `requirements.txt`: editable-install shortcut.
- `README.md`: setup and usage instructions.

## Build, Test, and Development Commands

Use a virtual environment. From PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe server.py --http
```

These commands create the environment, install dependencies, run tests, and serve MCP at `http://127.0.0.1:8000/mcp`. Omit `--http` for stdio. On macOS/Linux, use `.venv/bin/python` instead. Install the package in editable mode before running it.

For account access, copy `.env.example` to `.env`, fill in credentials locally, and run `authorize.py` with the environment's Python interpreter.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions and variables, `PascalCase` classes, and uppercase constants. Match the existing single-quoted strings and type-annotated MCP tool signatures. Keep API transport in the package `client.py` and tool validation in `tools/`.
Inject clients into tools and load settings explicitly at startup; avoid import-time I/O. No formatter or linter is configured; keep changes focused and consistent with nearby code.

## Testing Guidelines

Use standard-library `unittest` and `unittest.mock.patch`. Name test files `test_*.py` and methods `test_*`. Mock API calls so tests require neither credentials nor network access. Cover invalid inputs, serving ownership, single-write behavior, and MCP annotations when changing those paths. No coverage threshold is configured. Run the full suite before submitting changes; account integration checks are separate and can modify the real diary.

## Commit & Pull Request Guidelines

This checkout contains no Git metadata, so existing commit conventions cannot be verified. Use concise imperative subjects, such as `Validate serving before diary write`. Describe the behavior change, relevant issue, test command and results, and any configuration changes in pull requests.

## Security & Configuration

Never commit `.env` or `.tokens.json`, or log credentials and signed URLs. Keep HTTP bound to loopback and use an authenticated tunnel. Preserve explicit local dates and serving-unit conversion. Never automatically retry diary writes; read the diary first after an uncertain failure.
