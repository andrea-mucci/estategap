FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY libs/common /libs/common
COPY services/pipeline /app

RUN uv sync --no-dev

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

# Override this at deploy time to select the long-running worker you want:
#   python -m pipeline.normalizer
#   python -m pipeline.deduplicator
# Kubernetes sets the container command per Deployment instead of baking it into the image.
CMD ["python", "main.py"]
