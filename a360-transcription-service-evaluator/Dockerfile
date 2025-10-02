# Build stage
FROM python:3.12-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY backend/ backend/

# Install dependencies to wheels directory
RUN pip install --no-cache-dir --user .

# Runtime stage
FROM python:3.12-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY backend/ backend/

# Create necessary directories and set permissions
ENV MPLCONFIGDIR=/tmp/matplotlib
RUN mkdir -p $MPLCONFIGDIR && chown -R appuser:appuser /app /home/appuser $MPLCONFIGDIR

# Switch to non-root user
USER appuser

# Add local packages to PATH
ENV PATH="/home/appuser/.local/bin:$PATH"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["gunicorn", "transcription_evaluator.api.cognito_main:app", \
     "--bind", "0.0.0.0:8000", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--timeout", "300", \
     "--graceful-timeout", "300", \
     "--keep-alive", "2"]