# ============================================================
# Stage 1: Build — compile assets, install deps
# ============================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.6.0 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache -r pyproject.toml

COPY . .
RUN uv pip install --system --no-deps --no-cache .

# Build Tailwind CSS — auto-detect architecture via TARGETPLATFORM
ARG TARGETPLATFORM
RUN if [ "$TARGETPLATFORM" = "linux/arm64" ]; then TW_ARCH="linux-arm64"; else TW_ARCH="linux-x64"; fi && \
    python3 -c "import urllib.request; urllib.request.urlretrieve('https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-${TW_ARCH}', '/usr/local/bin/tailwindcss')" && \
    chmod +x /usr/local/bin/tailwindcss && \
    tailwindcss -i static/css/input.css -o static/css/tailwind.min.css --minify && \
    rm -f /usr/local/bin/tailwindcss

# ============================================================
# Stage 2: Runtime — minimal image, no build tools
# ============================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=production

COPY --from=ghcr.io/astral-sh/uv:0.6.0 /uv /usr/local/bin/uv

WORKDIR /app

# Install only Python runtime dependencies (no gcc, no libpq-dev)
COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application code, migrations, and compiled assets from builder
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/static /app/static

# Create non-root user
RUN mkdir -p static/uploads && \
    groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
