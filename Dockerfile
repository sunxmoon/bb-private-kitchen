# Use the official Python base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create a non-root user and ensure proper ownership
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID appgroup && \
    useradd -u $UID -g appgroup -m appuser && \
    mkdir -p static/uploads && \
    chown -R appuser:appgroup /app && \
    chmod -R 775 /app/static/uploads

USER appuser

# Expose the application port
EXPOSE 8000

# Run the application
CMD ["bash", "-c", "python3 seed_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
