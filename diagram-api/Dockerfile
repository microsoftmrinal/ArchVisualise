# Build stage
FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    graphviz \
    graphviz-dev \
    gcc \
    g++ && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Runtime stage
FROM python:3.13-slim

# Install only runtime dependencies (graphviz lib, no build tools)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    graphviz && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appuser app/ /app
WORKDIR /app

# Create output directory with proper permissions
RUN mkdir -p /app/diagrams && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
