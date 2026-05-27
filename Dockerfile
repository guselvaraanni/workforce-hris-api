# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Enterprise Workforce HRIS API
#
# Multi-stage build:
#   Stage 1 (builder): install Python deps with build tools (gcc for mysqlclient)
#   Stage 2 (runtime): minimal image, copy only what's needed
#
# Why mysqlclient needs gcc:
#   mysqlclient is a C extension that wraps libmysqlclient.
#   It must be compiled from source during pip install.
#   The builder stage has gcc; the runtime stage does not.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build dependencies ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System packages needed to compile mysqlclient
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a prefix directory
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Runtime MySQL shared library (no compiler needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Create required directories
RUN mkdir -p /app/logs /app/media /app/staticfiles

EXPOSE 8000

# Default command (overridden in docker-compose.yml)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
