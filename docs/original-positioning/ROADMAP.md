# Chumoli — Product Roadmap & Architecture Plan

> **Tarixiy hujjat (2026-09-26):** bu dastlabki reja. YAML-first config,
> `soliq_uz`/`mygov`/`onec_odata` connectorlar va DuckDB metadata store
> tasvirlangan — bular amalga oshirilmadi yoki o'zgardi. Haqiqiy holat uchun
> `docs/status.md` va `docs/architecture/` ga qarang.

> **Goal:** Lightweight, YAML-based EL data pipeline tool tailored for Uzbekistan data sources. EL only. Thin architectural layer.

---

## Core Principles

| Principle | Description |
|---|---|
| **EL Only** | Extract + Load only. No transformations. Raw data preservation. |
| **DLT Engine** | Built on top of `dlt`. Zero engine reinvention. |
| **YAML-First** | Accessible to non-engineers and finance analysts. |
| **Lightweight** | Single command installation via `pip install chumoli`. |
| **Uzbekistan-Tailored** | Solves regional data integration challenges. |

---

## DLT 1.30 Built-in Sources

```
dlt.sources
├── rest_api      ✅ Available — Generic REST API
├── sql_database  ✅ Available — PostgreSQL, MySQL, MSSQL, SQLite, Oracle
└── filesystem    ✅ Available — CSV, Parquet, JSONL (Local, S3, GCS)
```

---

## Implementation Phases

```
Phase 0 ── Core Engine + DLT Wrappers (Completed ✅)
Phase 1 ── Uzbekistan Payment Gateways (Completed ✅)
Phase 2 ── Uzbekistan Government & ERP Sources (Completed ✅)
Phase 3 ── Web UI / Dashboard (Optional / Future)
```

---

## Supported Sources

### 1. `rest_api` — Universal REST API
- **Based on:** `dlt.sources.rest_api.rest_api_source`
- **Status:** ✅ Completed (Supports `page_number`, `offset`, `cursor` pagination)
- **Auth:** `api_key`, `bearer`, `basic`, `none`

### 2. `sql_database` — Relational Databases
- **Based on:** `dlt.sources.sql_database.sql_database`
- **Status:** ✅ Completed
- **Supported DBs:** PostgreSQL, MySQL, MSSQL, SQLite, Oracle
- **Incremental:** ✅ Cursor column-based incremental extraction

### 3. `payme_uz` — Payme Payment Gateway
- **Type:** Custom connector (JSON-RPC 2.0 over HTTPS)
- **Status:** ✅ Completed
- **Endpoint:** `https://checkout.paycom.uz/api`
- **Auth:** `X-Auth: base64(merchant_id:api_key)`
- **Resources:** `receipts`

### 4. `click_uz` — Click Merchant Gateway
- **Type:** Custom connector (HMAC-SHA1 authentication)
- **Status:** ✅ Completed
- **Resources:** `payments`

### 5. `uzum_market` — Uzum Market Seller API
- **Type:** Custom connector (REST API, Bearer token)
- **Status:** ✅ Completed
- **Resources:** `orders`, `finance_report`

### 6. `soliq_uz` — Soliq Tax Portal API
- **Type:** Custom connector
- **Status:** ✅ Completed

### 7. `mygov` — MyGov Public Services API
- **Type:** Custom connector
- **Status:** ✅ Completed

### 8. `didox` — Didox E-Factura API
- **Type:** Custom connector (Bearer token)
- **Status:** ✅ Completed
- **Resources:** `invoices`, `documents`

### 9. `onec_odata` — 1C:Enterprise OData API
- **Type:** Custom connector (OData v4, Basic auth)
- **Status:** ✅ Completed

---

## All Sources — Master Status Table

| # | Connector | Type | Base | Phase | Status |
|---|---|---|---|---|---|
| 1 | `rest_api` | Universal | DLT built-in | 0 | ✅ Completed |
| 2 | `sql_database` | Universal | DLT built-in | 0 | ✅ Completed |
| 3 | `filesystem` | Universal | DLT built-in | 0 | ⬜ Planned |
| 4 | `payme_uz` | UZ Payment | Custom | 1 | ✅ Completed |
| 5 | `click_uz` | UZ Payment | Custom | 1 | ✅ Completed |
| 6 | `uzum_market` | UZ Marketplace | Custom | 1 | ✅ Completed |
| 7 | `soliq_uz` | UZ Gov | Custom | 2 | ✅ Completed |
| 8 | `mygov` | UZ Gov | Custom | 2 | ✅ Completed |
| 9 | `didox` | UZ Gov | Custom | 2 | ✅ Completed |
| 10 | `onec_odata` | ERP | Custom | 2 | ✅ Completed |

---

## Technical Architecture

```
YAML Config (pipeline.yml)
    │
    ▼
Config Layer (Pydantic v2)
    │  ${ENV_VAR} → .env resolution
    ▼
Source Factory (BaseUZConnector Protocol)
    ├── DLT Built-in (rest_api, sql_database, filesystem)
    └── Custom UZ Sources (payme_uz, uzum_market, click_uz, etc.)
    │
    ▼
DLT Engine (Schema inference, state, load packages)
    │
    ▼
Sink (DuckDB | PostgreSQL | Filesystem | ClickHouse)
    │
    ▼
Quality Checker (4 SQL checks)
    │
    ▼
Metadata Store (DuckDB: chumoli_runs history table)
    │
    ▼
Notify (Telegram | Email)
    │
    ▼
Logs (structlog JSON)
```

---

## Dependency Stack

```
Core:
  dlt[postgres,duckdb,filesystem]  ← Engine
  pydantic                         ← Config validation
  typer + rich                     ← CLI
  structlog                        ← Logging
  apscheduler                      ← Built-in scheduler
  httpx                            ← HTTP client
  python-dotenv                    ← .env loader
  PyYAML                           ← YAML parser
```
