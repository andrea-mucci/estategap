FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY libs/common /libs/common
COPY services/spider-workers /app

RUN uv sync --no-dev
RUN uv run playwright install chromium --with-deps

FROM builder AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
