FROM python:3.12-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY libs/common /libs/common
COPY services/ml /app

RUN uv sync --frozen --no-dev || uv sync --no-dev

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ARG SERVICE_MODE=scorer
ENV SERVICE_MODE=${SERVICE_MODE}

CMD ["python", "-m", "estategap_ml"]
