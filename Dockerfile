FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=production

# Install system deps for psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv with pinned version
COPY --from=ghcr.io/astral-sh/uv:0.6.0 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (cached unless pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv pip install --system -r pyproject.toml

# Copy source and install package
COPY . .
RUN uv pip install --system --no-deps .

# Build Tailwind CSS, then remove the CLI binary
ADD https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 /usr/local/bin/tailwindcss
RUN chmod +x /usr/local/bin/tailwindcss && \
    tailwindcss -i static/css/input.css -o static/css/tailwind.min.css --minify && \
    rm -f /usr/local/bin/tailwindcss

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
