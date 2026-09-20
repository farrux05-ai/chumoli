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

Ma’lumot va maxfiy kalitlar shu yerda saqlanadi (loyiha papkasida emas):

```text
~/.chumoli/
  chumoli_control.db    # pipeline sozlamalari
  master.key            # shifrlash
  api.key               # API kalit
  data/                 # default DuckDB fayllar
  pipelines/            # dlt holati
  examples/             # demo ma’lumotlar
```

Boshqa joyga yozish:

```bash
export CHUMOLI_HOME=/path/to/my-data
chumoli ui
```

---

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

**Destination:** DuckDB (default), PostgreSQL, Filesystem/S3, ClickHouse.

Bo‘sh DuckDB yo‘li → avtomatik `~/.chumoli/data/<pipeline>.duckdb` (CWD ga yozilmaydi).

---

## Sozlamalar

| O‘zgaruvchi | Ma’nosi |
|-------------|---------|
| `CHUMOLI_HOME` | Runtime papka (default `~/.chumoli`) |
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
