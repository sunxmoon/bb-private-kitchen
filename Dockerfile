FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv pip install --system -r pyproject.toml

COPY . .
RUN uv pip install --system --no-deps .

# Download Tailwind Standalone CLI + build CSS (not needed at runtime)
ADD https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 /usr/local/bin/tailwindcss
RUN chmod +x /usr/local/bin/tailwindcss && \
    tailwindcss -i static/css/input.css -o static/css/tailwind.min.css --minify && \
    rm -f /usr/local/bin/tailwindcss

RUN mkdir -p static/uploads && \
    groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python seed_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
