# Chumoli MVP — ishga tushirish

## Talablar
Python 3.11+, pip

## O'rnatish
```bash
cd chumoli-mvp
pip install -e ".[dev]"
```

## Testlar (fundament)
```bash
python -m pytest tests/ -v
# 42 passed (tasdiqlangan)
```

## API + Dashboard
```bash
PYTHONPATH=src python -m chumoli.api.app
# yoki: uvicorn chumoli.api.app:app --host 0.0.0.0 --port 8000
```

Ochish: http://127.0.0.1:8000/

- Dashboard: `/`
- API docs: `/api/docs`
- Health: `/api/health`

## MVP da nima ishlaydi
1. Connector katalogi (REST API, SQL Database) — manifest orqali
2. Pipeline yaratish (secrets shifrlangan, ControlStore)
3. Run → haqiqiy dlt load (DuckDB)
4. Quality report qaytariladi
5. HTML dashboard API ga ulangan

## Sinov (tasdiqlangan)
`POST /api/pipelines` + `POST .../run` bilan jsonplaceholder `/posts` → **100 qator** DuckDB ga yuklandi.

## Keyingi qadamlar
- UI nomlari: PostgreSQL / MySQL (sql_database o'rniga)
- UZ connectorlar (Click, Payme)
- Monitor → GitHub issue
