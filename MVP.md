# Chumoli MVP — ishga tushirish

## Talablar
Python 3.11+, pip

## O'rnatish
```bash
cd chumoli   # yoki repo ildizi
pip install -e ".[dev]"
```

## Testlar
```bash
PYTHONPATH=src python -m pytest tests/ -q
```

## API + Dashboard
```bash
PYTHONPATH=src python -m chumoli.api.app
# yoki: uvicorn chumoli.api.app:app --host 0.0.0.0 --port 8000
```

Ochish: http://127.0.0.1:8000/

- Dashboard: `/` (`src/chumoli/static/index.html`)
- API docs: `/api/docs`
- Health: `/api/health`

## MVP da nima ishlaydi
1. Connector katalogi (REST, SQL, UZ connectorlar) — manifest orqali
2. Pipeline yaratish (secrets shifrlangan, ControlStore)
3. Run → dlt load (DuckDB / PostgreSQL / lokal fayl / S3 / ClickHouse)
4. Quality report (SQL destinationlar)
5. HTML dashboard API ga ulangan
6. Lokal eksport: `~/chumoli-data/exports/<pipeline>/` — Preview da yo'l + fayllar

## Destinationlar
| Key | Izoh |
|-----|------|
| `duckdb` | default local DB |
| `postgresql` | warehouse |
| `filesystem` | faqat lokal papka |
| `s3` | `s3://` / `gs://` / … |
| `clickhouse` | `pip install "dlt[clickhouse]"` |

## Docker
```bash
docker compose up --build
```
`CHUMOLI_HOME=/data`, `CHUMOLI_DATA=/data/chumoli-data`
