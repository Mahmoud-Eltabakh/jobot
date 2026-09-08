# Multi-Stage Production Dockerfile for Jobot
# Builder Stage: Install dependencies and Playwright browser binaries
FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libmagic1 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt

# Final Runtime Stage: Secure Non-Root Container
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH \
    PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright \
    JOBOT_ENV=production \
    JOBOT_DATA_DIR=/app/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libmagic1 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && groupadd -r appgroup && useradd -r -g appgroup -u 10001 -m -d /home/appuser appuser \
    && mkdir -p /app/data /home/appuser/.cache/ms-playwright \
    && chown -R appuser:appgroup /app /home/appuser \
    && rm -rf /var/lib/apt/lists/*

USER appuser

# Copy installed Python packages from builder
COPY --chown=appuser:appgroup --from=builder /root/.local /home/appuser/.local

# Install minimal Chromium for Playwright scraping in runner
RUN playwright install chromium

# Copy application source and templates
COPY --chown=appuser:appgroup app/ /app/app/
COPY --chown=appuser:appgroup templates/ /app/templates/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
