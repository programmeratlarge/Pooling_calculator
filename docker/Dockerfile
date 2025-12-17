# Pooling Calculator - Docker Image
# Multi-stage build for optimized image size

FROM python:3.11-slim AS builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy project files (needed for editable install)
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install dependencies in a virtual environment
RUN uv sync --frozen --no-dev

# Final stage - runtime image
FROM python:3.11-slim

# Install runtime dependencies (curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy uv from builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Expose Gradio default port
EXPOSE 7860

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV GRADIO_SERVER_NAME=0.0.0.0
ENV GRADIO_SERVER_PORT=7860

# Health check (using curl instead of requests library)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860 || exit 1

# Run the application
CMD ["python", "-m", "pooling_calculator.ui"]
