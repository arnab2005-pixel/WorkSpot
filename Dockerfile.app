# Multi-stage build: build frontend, then copy to Python runtime
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Install frontend dependencies
COPY apps/web/package*.json ./apps/web/
RUN cd apps/web && npm ci

# Build frontend
COPY apps/web ./apps/web
RUN cd apps/web && npm run build

# ---- Python runtime ----
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    libsamplerate0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/apps/web/dist ./apps/web/dist

# Expose port (Render sets PORT env var)
EXPOSE 10000

# Start server
CMD ["python", "-m", "api.server"]