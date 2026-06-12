FROM python:3.11-slim AS base

WORKDIR /app

# Install build tools needed for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ── Development stage ─────────────────────────────────────────────────────────
FROM base AS development
CMD ["sh", "./entrypoint.sh"]

# ── Production stage ──────────────────────────────────────────────────────────
FROM base AS production
EXPOSE 8000
# 4 Uvicorn workers behind Gunicorn for production throughput
CMD ["gunicorn", "app:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
