# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install uv
RUN pip install uv && \
    uv pip install --system

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_WARN_SCRIPT_LOCATION=0 \
    PATH="/root/.cargo/bin:${PATH}"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies using uv
RUN uv pip install --no-cache -r requirements.txt --target /deps

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv && \
    uv pip install --system

# Create a non-root user
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app

# Copy Python dependencies from builder
COPY --from=builder /deps /usr/local/lib/python3.11/site-packages

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    UV_NO_WARN_SCRIPT_LOCATION=0

# Expose the port the app runs on
EXPOSE $APP_PORT

# Command to run the application
CMD ["uvicorn", "interfaces.api.main:app", "--reload", "--host", "${APP_HOST}", "--port", "${APP_PORT}"]