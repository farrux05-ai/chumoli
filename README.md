# UzPipe

Lightweight EL tool for Uzbekistan data sources, built on [dlt](https://dlthub.com) (Apache 2.0).

Dashboard + FastAPI + connectors (SQL, REST, Click, Payme, Uzum) + volume demo.

---

## Option A — Docker (recommended)

**Requirements:** Docker + Docker Compose v2

```bash
git clone https://github.com/farrux05-ai/uzpipe.git
cd uzpipe
docker compose up --build
```

Open **http://localhost:8000/**

- Data (pipelines, secrets, run history) → Docker volume `uzpipe_data`
- Stop: `Ctrl+C` or `docker compose down`
- Logs: `docker compose logs -f`

### Volume demo (speed)

In the UI click **⚡ Volume demo**, or:

```bash
curl -X POST "http://localhost:8000/api/demo/volume?row_count=100000"
```

Response includes `total_rows`, `duration_seconds`, `rows_per_second`.

---

## Option B — Local Python

**Requirements:** Python 3.11+

```bash
git clone https://github.com/farrux05-ai/uzpipe.git
cd uzpipe

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -U pip
pip install -r requirements.txt
pip install -e .

uzpipe-api
# or: python -m uvicorn uzpipe.api.app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/**

Data dir: `~/.uzpipe` (override with `UZPIPE_HOME=/path`).

### Tests

```bash
pip install -e ".[dev]"
pytest -q
```

---

## Features (v1)

| Area | Status |
|------|--------|
| PostgreSQL / MySQL / SQL / REST | ✅ |
| Click / Payme / Uzum Market | ✅ |
| Volume demo (synthetic) | ✅ |
| DuckDB / Postgres / FS / ClickHouse destinations | ✅ |
| Run monitor + duration / rows/s | ✅ |
| Interval scheduler | ✅ |
| Encrypted secrets | ✅ |
| Docker | ✅ |

License: Apache-2.0
