FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY libs/common /libs/common
COPY services/ai-chat /app

RUN uv sync --no-dev

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "estategap_ai_chat"]
