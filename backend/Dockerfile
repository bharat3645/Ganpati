# Ganpati backend -- FastAPI + Pillow + rembg image-compositing service.
FROM python:3.11-slim AS base

# rembg's onnxruntime dependency needs libgomp at runtime; libjpeg/zlib cover
# Pillow's JPEG/PNG codecs on the slim base image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libjpeg62-turbo \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so this layer is cached across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + the bundled Ganesh backdrop assets it composites onto.
COPY app.py run.py ./
COPY assets/ ./assets/

# rembg downloads its ONNX background-removal model to this cache directory
# on first use (unless already present); point it somewhere writable and
# persistable via a volume rather than the default $HOME, which may not be
# writable depending on the runtime user.
ENV U2NET_HOME=/app/.u2net
RUN mkdir -p /app/.u2net

# Not baked into the image: HF_TOKEN, CORS_ORIGINS -- pass them via
# `docker run -e` / docker-compose / your platform's secret manager.
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
