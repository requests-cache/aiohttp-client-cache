FROM python:3.10.10-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.4.0

COPY test ./test
COPY pyproject.toml poetry.lock gunicorn-cfg.py docker-entrypoint.sh ./

RUN pip install "poetry==$POETRY_VERSION"

RUN python -m venv /venv
RUN poetry export --only=test-server -f requirements.txt | /venv/bin/pip install -r /dev/stdin

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH="$PYTHONPATH:/app/test"

CMD ["./docker-entrypoint.sh"]
