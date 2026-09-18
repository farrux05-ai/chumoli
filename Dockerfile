FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY static ./static

RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src
ENV UZPIPE_HOME=/data
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "uzpipe.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
