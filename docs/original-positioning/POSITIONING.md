# UzPipe — Senior DE Positioning: Who We Are and What We Do

---

## 1. Stack Architecture & Integrated Tools

```
┌─────────────────────────────────────────────────────────┐
│                        UzPipe                           │
│                                                         │
│  YAML config  →  CLI (Typer+Rich)  →  Logs (structlog) │
│       ↓                                                 │
│  Config (Pydantic) + Env vars (.env)                    │
│       ↓                                                 │
│  Source Factory (BaseUZConnector Protocol)              │
│       ↓                                                 │
│  ┌──────────────────────────────────────────┐          │
│  │            DLT 1.30 (Engine)             │          │
│  │  - Schema inference (PyArrow)            │          │
│  │  - Incremental state management          │          │
│  │  - Load packages + checksums             │          │
│  │  - Built-in: rest_api, sql_database      │          │
│  └──────────────────────────────────────────┘          │
│       ↓                                                 │
│  Quality (4 SQL checks, DuckDB native)                  │
│       ↓                                                 │
│  Metadata Store (DuckDB: uzpipe_runs history table)     │
│       ↓                                                 │
│  Notify (httpx → Telegram/Email)                        │
│       ↓                                                 │
│  Scheduler (APScheduler, Asia/Tashkent TZ)             │
│       ↓                ↓                               │
│  Airflow DAG gen   Built-in cron                       │
└─────────────────────────────────────────────────────────┘
```

### Integrated Tools Rationale

| Tool | Version | Rationale |
|---|---|---|
| **dlt** | 1.30 | Core Engine. Schema inference, state management, load packages, PyArrow. Zero wheel reinvention. |
| **Pydantic v2** | 2.x | YAML → typed config validation. Clear error diagnostics. |
| **Typer** | 0.12 | CLI builder (built on Click). Free auto-completion support. |
| **Rich** | 13 | Terminal UI. Rich panels, tables, colored output. |
| **structlog** | 24 | Structured JSON logs. Compatible with Grafana/ELK. |
| **APScheduler** | 3.10 | Built-in cron scheduler when Airflow is not required. |
| **httpx** | 0.27 | Sync HTTP client replacing requests (proper timeouts, retries). |
| **python-dotenv** | 1.0 | Environment variable loader (.env). 12-factor app pattern. |
| **PyYAML** | 6.0 | YAML parser with safe load. |

**Total: 9 lightweight dependencies.** Zero bloat.

---

## 2. Market Landscape & Tool Comparison

### Spectrum

```
Weight:
HEAVY ─────────────────────────────────── LIGHT
  │                                          │
Airbyte    Meltano    dlt (raw)   Sling   UzPipe
  │           │           │         │        │
Docker/K8s  meltano.yml  Python   YAML+CLI YAML+CLI
  UI included Singer taps Python code binary   UZ-tailored
600+ conn   hub.melt.com required DB→DB   connectors
```

### Competitor Limitations

**Airbyte:**
- Heavy Docker + Kubernetes footprint requires admin overhead
- Zero native connectors for Uzbekistan payment/tax APIs
- Enterprise pricing: $1000+/month
- Self-hosted: 6+ containers, 2-day setup process

**Meltano + Singer:**
- Steep learning curve for `meltano.yml`
- Singer taps are community-maintained with variable quality
- Missing native Uzbek connectors (`tap-payme-uz`, etc.)
- Requires separate Python packages for each tap

**dlt (raw Python):**
- Requires writing Python code directly
- No built-in scheduler, quality checks, or alerting out-of-the-box
- High barrier for non-Python finance analysts

**Sling CLI:**
- Limited to DB→DB and DB→File syncs (no generic REST API engine)
- Lacks native Uzbek connectors and built-in quality checks
- Go binary outside the Python ecosystem

---

## 3. UzPipe Positioning & Key Advantages

### Bridging Sling CLI Simplicity and dlt Power

```
Sling ──────── UzPipe ──────── dlt (raw)
  │               │                │
DB→DB only    YAML-first       Python-first
No REST       REST✓ SQL✓       REST✓ SQL✓
No UZ         UZ connectors    No UZ
No Quality    Built-in Quality No Quality
No Alerts     Built-in Alerts  No Alerts
```

### 5 Strategic Pillars

**1. Tailored Uzbekistan Connectors (Unfair Advantage / Moat)**
```
Payme     → Absent in Airbyte, Sling, raw dlt.
Click     → Absent in Airbyte, Sling, raw dlt.
1C OData  → Absent in Airbyte, Meltano.
Didox     → Absent in all global EL tools.
```

**2. Zero Infrastructure Requirement**
```bash
pip install uzpipe
uzpipe run pipeline.yml
```
Airbyte requires 8 containers and 4GB+ RAM; UzPipe runs on standard Python with minimal resource usage.

**3. Accessible to Finance & Analytics Teams**
```yaml
source:
  connector: payme_uz
  auth:
    username: "${PAYME_ID}"
    password: "${PAYME_KEY}"
sink:
  connector: postgresql
  connection: "${PG_URL}"
```
Clear declarative YAML without needing full Python code.

**4. Batteries Included**
```
Quality Checks → Native SQL queries (no external dbt/Great Expectations dependency)
Notifications  → Telegram alerts (standard channel in Uzbekistan)
Scheduler      → APScheduler (built-in cron support)
Airflow DAGs   → One-click DAG generation for enterprise scaling
JSON Logs      → Grafana-compatible structured logging
```

**5. Robust Incremental Loading**
```yaml
incremental:
  cursor_field: updated_at
  initial_value: "2024-01-01"
```
DLT state engine automatically handles cursor tracking, state persistence, and deduplication.

---

## 4. Engineering Standards for Production Reliability

### A) Connector Robustness
- ✅ Retries with exponential backoff on HTTP 429 & 5xx
- ✅ Enforced timeout handling
- ✅ Idempotency (preventing duplicate rows across re-runs)
- ✅ Enforced API rate limits (e.g., Payme max 50 req/min)

### B) Developer Experience (DX)
- Quick time-to-first-pipeline (< 15 minutes setup to execution)

### C) Ecosystem Scalability
- Start with CLI (`uzpipe run`) → Scale to built-in cron (`uzpipe schedule`) → Export to Airflow (`uzpipe generate airflow`).

---

## 5. Scope Boundaries (Anti-Features)

To prevent scope creep, UzPipe explicitly does **NOT**:
- ❌ Provide data transformation (use dbt)
- ❌ Act as a data catalog (use DataHub/OpenMetadata)
- ❌ Implement column-level lineage
- ❌ Maintain 500+ global connectors (Airbyte target)
- ❌ Handle real-time streaming (use Kafka/Flink)

---

## 6. Current Implementation Status

### Completed Features (Phase 0, 1 & 2 ✅)
```
Core engine          → DLT 1.30 + YAML + Pydantic v2
CLI                  → Typer + Rich (6 commands)
BaseUZConnector      → Protocol-based framework ✅
Metadata Store       → uzpipe_runs history table (DuckDB) ✅
Sources (Universal)  → rest_api (pagination ✅), sql_database ✅
Sources (UZ Payment) → payme_uz ✅, uzum_market ✅, click_uz ✅
Sources (UZ Gov/ERP) → soliq_uz ✅, mygov ✅, didox ✅, onec_odata ✅
Quality              → 4 SQL checks, DuckDB + PostgreSQL ✅
Notify               → Telegram (sync httpx) ✅
Scheduler            → APScheduler (Asia/Tashkent TZ) ✅
Airflow Integration  → Airflow DAG generator ✅
Test Suite           → 70 automated tests (100% passing) ✅
CI/CD                → GitHub Actions (Python 3.11 + 3.12) ✅
Linting              → Ruff compliant ✅
```

---

## 7. Executive Summary

```
UzPipe Definition:
dlt (Engine) + YAML (Config) + UZ Connectors (Moat)
+ Built-in Quality + Telegram Alerts + APScheduler
= Lightweight, Uzbekistan-focused EL Data Pipeline Engine
```
