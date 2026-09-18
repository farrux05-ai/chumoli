# UzPipe — production image
# Build:  docker compose up --build
# Open:   http://localhost:8000

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY static ./static

# Install package so `import uzpipe` works
RUN pip install --no-cache-dir --no-deps .

ENV UZPIPE_HOME=/data
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "uzpipe.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
