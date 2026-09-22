<p align="center">
  <img src="assets/chumoli-logo.svg" alt="Chumoli" width="120" height="120" />
</p>

<h1 align="center">Chumoli</h1>

<p align="center">
  <strong>O‘zbekiston ma’lumot manbalari uchun engil EL vosita</strong><br/>
  <a href="https://dlthub.com">dlt</a> ustida · Apache 2.0
</p>

<p align="center">
  <a href="#tez-boshlash">Tez boshlash</a> ·
  <a href="#dashboard">Dashboard</a> ·
  <a href="#cli">CLI</a> ·
  <a href="#ulagichlar">Ulagichlar</a> ·
  <a href="#sozlamalar">Sozlamalar</a>
</p>

---

SQL, REST, Click, Payme, Uzum va boshqa manbalardan ma’lumotni olib **DuckDB / PostgreSQL** ga yuklang. Brauzerda boshqaring yoki terminaldan ishga tushiring.

---

## Tez boshlash

**Kerak:** Python **3.11+** va `pip`.

### 1) O‘rnatish

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -U pip
pip install chumoli                # PyPI (chiqarilgach)
# yoki loyihadan:
# git clone https://github.com/farrux05-ai/chumoli.git
# cd chumoli && pip install -e .
```

### 2) UI ni ochish

```bash
chumoli ui
```

- Server: **http://127.0.0.1:8000/**
- Brauzer **o‘zi ochiladi**
- To‘xtatish: `Ctrl+C`

Brauzersiz faqat server:

```bash
chumoli ui --no-open
# yoki
chumoli-api
```

### 3) Birinchi pipeline

1. Dashboardda **+ Yangi** yoki **Ulagichlar**
2. Manba tanlang (SQL / REST / …)
3. Ulanishni tekshiring → jadvallarni tanlang → saqlang
4. **Run** → **Preview** da natijani ko‘ring

Namuna (UI dagi demo tugmalar):

- SQL namunasi — tayyor SQLite → DuckDB  
- REST namunasi — JSONPlaceholder → DuckDB  
- Volume demo — tezlik sinovi (sintetik qatorlar)

---

## Dashboard

| Bo‘lim | Vazifa |
|--------|--------|
| **Pipeline’lar** | Ro‘yxat, Run, Preview, tahrirlash |
| **Ulagichlar** | Manba katalogi (SQL, REST, to‘lov tizimlari…) |
| **Ishga tushirishlar** | Run tarixi, status, qatorlar, vaqt |
| **Sozlamalar** | Telegram xabar, scheduler |

Ma’lumot ikki joyda saqlanadi (loyiha papkasida emas):

```text
~/.chumoli/                 # yashirin (tizim)
  chumoli_control.db
  master.key
  api.key
  pipelines/                # dlt state / schema

~/chumoli-data/             # foydalanuvchi ko‘radigan
  <pipeline>.duckdb
  examples/
  exports/<pipeline>/       # lokal CSV/Parquet
```

Boshqa joyga yozish:

```bash
export CHUMOLI_HOME=/path/to/system
export CHUMOLI_DATA=/path/to/visible-data
chumoli ui
```

---

## Production notes

- Run **one** uvicorn worker only (`chumoli ui` already uses `workers=1`). Multiple workers break the in-process scheduler and run locks.
- Back up `CHUMOLI_HOME/master.key` together with the control DB — without the key, secrets cannot be decrypted.

## CLI

```bash
chumoli --help
chumoli ui                 # dashboard + brauzer
chumoli ui --port 8080
chumoli list               # saqlangan pipeline’lar
chumoli run <nom>          # bir marta ishga tushirish
```

---

## Ulagichlar

| Tur | Misollar |
|-----|----------|
| Universal | PostgreSQL, MySQL, umumiy SQL, REST API |
| To‘lov | Click, Payme, Uzum Market |
| Sinov | Volume demo (sintetik) |

**Destination:** DuckDB (default), PostgreSQL, Lokal fayl, S3/Object storage, ClickHouse.

- Bo‘sh DuckDB → `~/chumoli-data/<pipeline>.duckdb`
- Lokal fayl → `~/chumoli-data/exports/<pipeline>/` (S3 dan alohida katalog)

---

## Sozlamalar

| O‘zgaruvchi | Ma’nosi |
|-------------|---------|
| `CHUMOLI_HOME` | Tizim papka (default `~/.chumoli`) |
| `CHUMOLI_DATA` | Ko‘rinadigan ma’lumot (default `~/chumoli-data`) |
| `CHUMOLI_API_KEY` | API kalit (bo‘sh bo‘lsa `api.key` yaratiladi) |

Telegram: dashboard **Sozlamalar** da bot token + chat id. Muvaffaqiyat/xato xabarlarini pipeline sozlamasida yoqing.

---

## Ishlab chiqish (ixtiyoriy)

```bash
git clone https://github.com/farrux05-ai/chumoli.git
cd chumoli
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
chumoli ui
```

### Docker (ixtiyoriy)

Docker biladiganlar uchun:

```bash
docker compose up --build
# http://127.0.0.1:8000/
```

---

## Features (v1)

- SQL / REST va O‘zbekiston to‘lov ulagichlari  
- Dashboard: yaratish, Run, Preview, runs tarixi  
- Shifrlangan secrets  
- Interval scheduler  
- Telegram bildirishnomalar  
- `chumoli ui` — bir buyruqda ochiladigan interfeys  

---

## License

Apache-2.0 · [GitHub](https://github.com/farrux05-ai/chumoli)
