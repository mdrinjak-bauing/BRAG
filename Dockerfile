FROM python:3.12-slim

# System libraries needed by Docling's layout models (OpenCV backend)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY brag/ /app/brag/
COPY vault_template/ /app/vault_template/

# Model caches (Docling layout models, reranker) persist via a named volume
ENV HF_HOME=/models
ENV PYTHONUNBUFFERED=1

# Run as a non-root user (defense in depth). /models is a named volume — Docker
# seeds its ownership from this image directory on first mount, so the app can
# write the model cache. The bind mounts (/vault, /workspace) are handled by
# Docker Desktop's permission mapping; on a native-Linux host the mounted dirs
# should be owned by UID 1000 (the default for the first desktop user).
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /models \
    && chown -R app:app /app /models
USER app

CMD ["python", "-m", "brag.main"]
