FROM python:3.12-slim

# System libraries needed by Docling's layout models (OpenCV backend)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY studiolo/ /app/studiolo/
COPY vault_template/ /app/vault_template/

# Model caches (Docling layout models, reranker) persist via a named volume
ENV HF_HOME=/models
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "studiolo.main"]
