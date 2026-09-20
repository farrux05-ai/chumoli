<p align="center">
  <img src="assets/chumoli-logo.svg" alt="Chumoli Logo" width="120" height="120" />
</p>

<h1 align="center">Chumoli</h1>

<p align="center">
  <strong>Lightweight EL Tool for Uzbekistan Data Sources</strong><br>
  Built on top of <a href="https://dlthub.com">dlt engine</a> (Apache 2.0)
</p>

<p align="center">
  <a href="#option-a--docker-recommended">Docker Quickstart</a> •
  <a href="#option-b--local-python">Local Setup</a> •
  <a href="#features-v1">Features</a>
</p>

---

Dashboard + FastAPI + Connectors (SQL, REST, Click, Payme, Uzum Market, Didox) + Volume Demo.

---

## Option A — Docker (recommended)

**Requirements:** Docker + Docker Compose v2

```bash
git clone https://github.com/farrux05-ai/chumoli.git
cd chumoli
docker compose up --build
```

Open **http://localhost:8000/**

- Data (pipelines, secrets, run history) → Docker volume `chumoli_data`
- Stop: `Ctrl+C` or `docker compose down`
- Logs: `docker compose logs -f`

### Volume demo (speed)

In the UI click **⚡ Volume demo**, or:

```bash
curl -X POST "http://localhost:8000/api/demo/volume?row_count=100000"
```

Response includes `total_rows`, `duration_seconds`, `rows_per_second`.

---


## Option B — pip (PyPI)

```bash
pip install chumoli
export CHUMOLI_HOME=~/.chumoli
chumoli-api
# yoki: uvicorn chumoli.api.app:app --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000/**

CLI: `chumoli --help`

---

## Option C — Local Python

**Requirements:** Python 3.11+

```bash
git clone https://github.com/farrux05-ai/chumoli.git
cd chumoli

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -U pip
pip install -r requirements.txt
pip install -e .

chumoli-api
# or: python -m uvicorn chumoli.api.app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/**

Data dir: `~/.chumoli` (override with `CHUMOLI_HOME=/path`).

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
| Click / Payme / Uzum Market / Didox | ✅ |
| Volume demo (synthetic benchmark) | ✅ |
| DuckDB / Postgres / FS / ClickHouse destinations | ✅ |
| Run monitor + duration / rows/s | ✅ |
| Interval scheduler | ✅ |
| Encrypted secrets | ✅ |
| Docker support | ✅ |

---

## License

Apache-2.0
