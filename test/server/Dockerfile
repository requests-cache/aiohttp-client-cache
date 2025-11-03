FROM python:3.13-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY test ./test
COPY pyproject.toml uv.lock README.md ./

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install dependencies
RUN uv sync --group test-server --no-dev

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/test"

ENTRYPOINT ["uv", "run", "gunicorn", "server:app", "-c", "test/server/gunicorn-cfg.py"]
