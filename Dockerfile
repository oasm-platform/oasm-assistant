# Build stage
FROM python:3.12-slim AS builder

WORKDIR /build

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements for better layer caching
COPY requirements.txt .

# Install Python dependencies to a separate directory with pip cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install --no-warn-script-location -r requirements.txt

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime system dependencies with cache mounts
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Copy installed Python dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=appuser:appuser ./agents ./agents
COPY --chown=appuser:appuser ./app ./app
COPY --chown=appuser:appuser ./common ./common
COPY --chown=appuser:appuser ./llms ./llms
COPY --chown=appuser:appuser ./tools ./tools
COPY --chown=appuser:appuser ./data ./data
COPY --chown=appuser:appuser ./scripts ./scripts
COPY --chown=appuser:appuser ./dev.py ./dev.py

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT:-8000}/health || exit 1

# Expose gRPC port
EXPOSE 8000

# Command to run the application in production mode
# CMD ["python", "-m", "app.main"]

# Command to run the application in development mode
CMD ["python", "dev.py"]