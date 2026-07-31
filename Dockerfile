# syntax=docker/dockerfile:1

# ---- Builder stage: compile wheels with build tooling, discarded afterwards ----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ---- Final stage: slim runtime image, no compiler toolchain ----
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libpq5 is the psycopg2 runtime client library; libpq-dev/gcc (build-only) stay in the builder stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY . .

RUN addgroup --system app \
    && adduser --system --ingroup app --no-create-home app \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app \
    && chmod +x .scripts/entrypoint.sh

USER app

EXPOSE 8000

# CMD (not ENTRYPOINT) so Render's `dockerCommand` can fully replace it per-service
# -- the Celery worker/beat services reuse this same image but override this command.
CMD ["sh", ".scripts/entrypoint.sh"]
