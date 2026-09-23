<p align="center">
  <img src="https://raw.githubusercontent.com/farrux05-ai/chumoli/main/assets/chumoli-logo.svg" alt="Chumoli" width="120" height="120" />
</p>

<h1 align="center">Chumoli</h1>

<p align="center">
  <strong>O‘zbekiston ma’lumot manbalari uchun engil EL vosita</strong><br/>
  <a href="https://dlthub.com/docs">dlt</a> (Apache 2.0) ustida · UI + CLI
</p>

<p align="center">
  <a href="https://github.com/farrux05-ai/chumoli/actions/workflows/ci.yml"><img src="https://github.com/farrux05-ai/chumoli/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://pypi.org/project/chumoli/"><img src="https://img.shields.io/pypi/v/chumoli.svg" alt="PyPI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" /></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python" />
  <img src="https://img.shields.io/badge/status-beta-yellow.svg" alt="Beta" />
</p>

---

SQL, REST va O‘zbekiston manbalaridan (Click, Payme, Uzum, Didox — **beta**) ma’lumotni olib **DuckDB**, **PostgreSQL**, **lokal fayl** yoki **S3** ga yuklang. Brauzerda boshqaring yoki CLI orqali ishga tushiring.

## Tez boshlash

**Talab:** Python 3.11+

```bash
pip install chumoli
chumoli ui
```

- Dashboard: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/api/docs
- To‘xtatish: `Ctrl+C`

Brauzersiz: `chumoli ui --no-open` yoki `chumoli-api`.

### Ishlab chiqish (repo)

```bash
git clone https://github.com/farrux05-ai/chumoli.git
cd chumoli
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
chumoli ui
```

### Birinchi pipeline

1. **+ Yangi** yoki **Ulagichlar**
2. Manba tanlang → ulanishni tekshiring → saqlang
3. **Run** → **Preview**

UI dagi demo: SQL → DuckDB, REST (CBU valyuta kurslari) → DuckDB, Volume (sintetik).

## Nima bor (v0.1)

| Imkoniyat | Izoh |
|-----------|------|
| Ulagichlar | SQL, REST, sintetik volume (**stable**); Click, Payme, Uzum, Didox (**beta**) |
| Destinationlar | DuckDB, PostgreSQL, lokal CSV/Parquet, S3/GCS/…, ClickHouse |
| Dashboard | Yaratish, Run, Preview, runs tarixi, scheduler |
| Xavfsizlik | Secrets Fernet bilan shifrlangan; API kalit |
| Bildirishnoma | Telegram (ixtiyoriy) |
| CLI | `chumoli ui`, `list`, `run` |

### UZ connectorlar — beta

Click, Payme, Uzum Market va Didox kod bazasida bor va UI da **beta** deb belgilangan. Ular hali barcha merchant/sandbox muhitlarida to‘liq tasdiqlanmagan. Ishlatishdan oldin o‘z API kalitingiz bilan sinang; xato topsangiz [Issues](https://github.com/farrux05-ai/chumoli/issues) oching.

## Destinationlar

| Key | Default / connection |
|-----|----------------------|
| `duckdb` | `~/chumoli-data/<pipeline>.duckdb` |
| `postgresql` | SQLAlchemy URL (parol maxfiy) |
| `filesystem` | Faqat lokal → tanlangan papka yoki `~/chumoli-data/exports/<pipeline>/` |
| `s3` | `s3://` / `gs://` / `az://` … |
| `clickhouse` | URL; `pip install "chumoli[clickhouse]"` |

Lokal fayl va S3 katalogda **alohida**. dlt `_dlt_*` metadata yashirin staging da qoladi; foydalanuvchi papkasiga faqat toza jadvallar chiqadi. Preview: papka yo‘li, fayllar, CSV namunasi.

## Ma’lumot qayerda

```text
~/.chumoli/                 # tizim (yashirin)
  chumoli_control.db
  master.key
  api.key
  pipelines/                # dlt state
  fs_staging/               # dlt filesystem + _dlt_* (yashirin)

~/chumoli-data/             # foydalanuvchi ko‘radigan
  <pipeline>.duckdb
  examples/
  exports/<pipeline>/       # toza CSV/Parquet
```

```bash
export CHUMOLI_HOME=/var/lib/chumoli
export CHUMOLI_DATA=/var/lib/chumoli-data
chumoli ui
```

`master.key` ni control DB bilan birga zaxiralang — kalitsiz secrets ochilmaydi.

## CLI

```bash
chumoli --help
chumoli ui                 # dashboard + brauzer
chumoli ui --port 8080
chumoli list
chumoli run <pipeline>
```

## Docker

```bash
docker compose up --build
# http://127.0.0.1:8000/
```

- Bind: `127.0.0.1:8000` (tashqi tarmoq uchun reverse proxy + `CHUMOLI_API_KEY` + TLS)
- Volume: `chumoli_data` → `/data` (`CHUMOLI_HOME` + `CHUMOLI_DATA`)
- **Bitta** uvicorn worker — scheduler va run lock shu processda

## Muhit o‘zgaruvchilari

| O‘zgaruvchi | Default | Ma’nosi |
|-------------|---------|---------|
| `CHUMOLI_HOME` | `~/.chumoli` | Control DB, kalitlar, dlt state |
| `CHUMOLI_DATA` | `~/chumoli-data` | DuckDB va lokal eksportlar |
| `CHUMOLI_API_KEY` | (avto `api.key`) | API autentifikatsiya |

Telegram: dashboard **Sozlamalar** → bot token + chat id.

## Ishlab chiqish

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m pytest tests/ -q
```

CI (GitHub Actions): har push/PR da Python 3.11 va 3.12 da testlar + Docker image build.

## Litsenziya

Apache-2.0 · [GitHub](https://github.com/farrux05-ai/chumoli)
