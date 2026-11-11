FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FATSECRET_CONFIG_DIR=/config

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/fatsecret_connector/ ./src/fatsecret_connector/

RUN python -m pip install --no-cache-dir . \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir /config \
    && chown app:app /config

USER app

# HTTP stays on loopback. Run with --network host; see README.md.
ENTRYPOINT ["python", "-m", "fatsecret_connector"]
CMD ["--http"]
