# ============================================================
# Orchestrator Dockerfile
# Python 3.9-slim base — FastAPI + Uvicorn
# ============================================================
FROM python:3.9-slim

# Non-interactive apt installs
ENV DEBIAN_FRONTEND=noninteractive

# Install curl for health checks and netcat for connectivity tests
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies before copying source code
# (leverages Docker layer cache when requirements.txt is unchanged)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Expose the orchestrator port
EXPOSE 9000

# Run the FastAPI application with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000", "--log-level", "info"]
