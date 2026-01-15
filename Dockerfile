# ============================================================================
# Optimized Multi-stage Dockerfile for OASM Assistant
# Using UV package manager and distroless runtime for security and size optimization
# ============================================================================

# ----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies with UV
# ----------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# UV configuration
ENV UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=1200

# Install git (required by GitPython) and tzdata (for timezone support)
RUN apt-get update && apt-get install -y --no-install-recommends git tzdata && rm -rf /var/lib/apt/lists/*

# Determine architecture dynamically and copy required shared libraries
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        LIBARCH="x86_64"; \
    elif [ "$ARCH" = "aarch64" ]; then \
        LIBARCH="aarch64"; \
    else \
        LIBARCH="unknown"; \
    fi && \
    echo "Detected architecture: $ARCH, using library path: /lib/${LIBARCH}-linux-gnu" && \
    mkdir -p /lib/multi-arch && \
    cp /lib/${LIBARCH}-linux-gnu/libc.so.6 /lib/multi-arch/ && \
    cp /lib/${LIBARCH}-linux-gnu/libm.so.6 /lib/multi-arch/ && \
    if [ -f "/lib/${LIBARCH}-linux-gnu/libz.so.1" ]; then cp /lib/${LIBARCH}-linux-gnu/libz.so.1 /lib/multi-arch/; fi && \
    if [ -f "/lib/${LIBARCH}-linux-gnu/libgcc_s.so.1" ]; then cp /lib/${LIBARCH}-linux-gnu/libgcc_s.so.1 /lib/multi-arch/; fi && \
    if [ -f "/lib/${LIBARCH}-linux-gnu/libexpat.so.1" ]; then cp /lib/${LIBARCH}-linux-gnu/libexpat.so.1 /lib/multi-arch/; fi && \
    if [ -f "/lib/${LIBARCH}-linux-gnu/libpq.so.5" ]; then cp /lib/${LIBARCH}-linux-gnu/libpq.so.5 /lib/multi-arch/; fi && \
    if [ -f "/usr/lib/${LIBARCH}-linux-gnu/libstdc++.so.6" ]; then cp /usr/lib/${LIBARCH}-linux-gnu/libstdc++.so.6 /lib/multi-arch/; fi && \
    if [ -f "/usr/lib/${LIBARCH}-linux-gnu/libffi.so.8" ]; then cp /usr/lib/${LIBARCH}-linux-gnu/libffi.so.8 /lib/multi-arch/; fi && \
    if [ -f "/usr/lib/${LIBARCH}-linux-gnu/libpcre2-8.so.0" ]; then cp /usr/lib/${LIBARCH}-linux-gnu/libpcre2-8.so.0 /lib/multi-arch/; fi && \
    mkdir -p /tmp/logs

# Detect Python version dynamically
RUN PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2) && \
    echo "Detected Python version: $PYTHON_VERSION" && \
    echo "PYTHON_VERSION=$PYTHON_VERSION" > /tmp/python_version.env

WORKDIR /build

# Use UV to install dependencies
# --frozen: ensure only exact versions from uv.lock are installed
# --no-install-project: install dependencies only, not the project itself
# --no-dev: do not install dev dependencies (pytest, etc.)
# --no-editable: do not install in editable mode
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv venv /build/.venv && \
    uv sync --frozen --no-install-project --no-dev --no-editable && \
    ls -la /build/.venv/lib/

# ----------------------------------------------------------------------------
# Stage 2: Runtime - Python Slim for balance between size and compatibility
# ----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Metadata labels
LABEL maintainer="OASM Team"
LABEL maintainer.company="VIETNAM NATIONAL CYBER SECURITY TECHNOLOGY CORPORATION"
LABEL image.description="Secure OASM Assistant"
LABEL image.version="0.1.0"

WORKDIR /app

# Install runtime dependencies including Node.js 20.x
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends \
    git \
    nodejs \
    tzdata && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user with home directory
RUN groupadd -r nonroot && useradd -r -g nonroot -m -d /home/nonroot nonroot

# Copy UV virtual environment from builder
COPY --from=builder --chown=nonroot:nonroot /build/.venv/ /app/.venv/

# Copy application source code
COPY --chown=nonroot:nonroot ./agents/ ./agents/
COPY --chown=nonroot:nonroot ./app/ ./app/
COPY --chown=nonroot:nonroot ./common/ ./common/
COPY --chown=nonroot:nonroot ./llms/ ./llms/
COPY --chown=nonroot:nonroot ./tools/ ./tools/
COPY --chown=nonroot:nonroot ./data/ ./data/
COPY --chown=nonroot:nonroot ./knowledge/ ./knowledge/

# Create logs directory
RUN mkdir -p /app/logs && chown -R nonroot:nonroot /app/logs

# Set environment variables
ENV HOME=/home/nonroot \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    APP_MODE=production \
    TZ=Asia/Ho_Chi_Minh

# Switch to non-root user
USER nonroot

# Expose gRPC port
EXPOSE 8000

# Command to run the application
ENTRYPOINT ["python3", "-m", "app.main"]