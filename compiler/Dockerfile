# ============================================================
# Tectonic LaTeX Compiler — Microservice
# Lightweight: ~150MB image (vs 4GB TexLive)
# ============================================================

# ---------- Dockerfile ----------
FROM python:3.12-slim

# Install tectonic + runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    libfontconfig1 libharfbuzz0b libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Install tectonic binary (~15MB)
RUN curl -fL --retry 3 --retry-delay 2 \
    https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz \
    | tar -xz -C /usr/local/bin

# Install FastAPI
RUN python -m pip install --no-cache-dir fastapi uvicorn python-multipart

WORKDIR /app
COPY compiler_service.py .

# Tectonic cache dir (packages auto-downloaded on first use)
ENV XDG_CACHE_HOME=/app/tectonic_cache
RUN mkdir -p /app/tectonic_cache \
    && useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8001
CMD ["python3", "-m", "uvicorn", "compiler_service:app", "--host", "0.0.0.0", "--port", "8001"]