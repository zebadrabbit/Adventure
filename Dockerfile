# Adventure MUD - Production Dockerfile
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 adventure && \
    mkdir -p /app /app/logs /app/instance && \
    chown -R adventure:adventure /app

WORKDIR /app

# Install Python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=adventure:adventure . .

# Switch to non-root user
USER adventure

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/').raise_for_status()"

# Run application
# NOTE: >1 worker requires sticky sessions + a Socket.IO message queue; state is in-process (pre-existing)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "--timeout", "120", "run:app"]
