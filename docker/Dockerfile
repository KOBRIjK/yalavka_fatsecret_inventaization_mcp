FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONPATH=/app
WORKDIR /app
COPY docker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY fatsecret-connector /sources/fatsecret
COPY yandex-lavka-mcp /sources/lavka
RUN pip install --no-cache-dir --no-deps /sources/fatsecret /sources/lavka \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app \
    && mkdir -p /backups && chown app:app /backups
COPY pantry-mcp/server.py pantry-mcp/migrate.py /app/pantry/
COPY shared/eda_state.py /app/
USER app
CMD ["python", "/app/pantry/server.py"]

FROM runtime AS tests
USER root
RUN pip install --no-cache-dir pytest==8.4.2 pytest-asyncio==1.2.0 respx==0.22.0
COPY pantry-mcp/test_server.py /tests/pantry/test_server.py
COPY fatsecret-connector/tests /tests/fatsecret/tests
COPY yandex-lavka-mcp/tests /tests/lavka/tests
COPY tests/test_stack.py /tests/test_stack.py
USER app
CMD ["python", "/tests/test_stack.py"]
