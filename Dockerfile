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
# docling 2.118.0-2.120.2 shipped a layout engine that calls torch.compile,
# which needs a C++ compiler this slim image does not have — every PDF failed.
# Upstream turned it off again in 2.121.0, so today it works by luck rather than
# by design. Pin the behaviour: BRAG never wants runtime compilation here.
ENV DOCLING_INFERENCE_COMPILE_TORCH_MODELS=false
ENV HF_HOME=/models
# The BM25 model must live on the models_cache volume too. brag/config.py
# otherwise defaults it to ~/.cache/fastembed, which inside the container is the
# throwaway image layer: every update/recreate re-downloads it, and offline that
# silently degrades BM25 (see the comment at FASTEMBED_CACHE_PATH in config.py).
ENV FASTEMBED_CACHE_PATH=/models/fastembed
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
