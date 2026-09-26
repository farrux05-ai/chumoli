# Quality and reliability

Covers: data quality checks, failure recovery, notifications.

## The core requirement (verbatim from the person building this)

> "Not just a connector — a reliable pipeline. Even if it breaks, it
> should be easy to recover. Even a less technical person should be
> able to operate it."

## Two separate concerns, deliberately not merged

1. **Structural / operational reliability** — did the pipeline run
   succeed, and if not, how do we recover? This is what dlt already
   solves (see `dlt-boundary.md`) — we wrap it, we don't rebuild it.
2. **Content-level data quality** — does the *data itself* meet
   business expectations (row count above zero, no nulls in key
   columns, no duplicate primary keys, freshness within SLA)? dlt's
   free tier does NOT provide this (`is_unique()`, `is_in()`, etc. are
   dltHub-only, confirmed in `dlt-boundary.md`) — this was genuinely
   ours to build, matching the original plan in
   `docs/original-positioning/POSITIONING.md` ("4 SQL checks, DuckDB
   native"), and is now implemented (`core/quality.py`, section 2
   below).

## 1. Structural reliability — using dlt's own tools

| dlt tool | What it does | How Chumoli exposes it |
|---|---|---|
| `dlt pipeline <name> failed-jobs` | Lists failed jobs with error messages | "Tiklash" drawer lists failed jobs in plain Uzbek |
| `dlt pipeline <name> drop-pending-packages` | Clears half-loaded packages | "Kutayotgan paketlarni tozalash" button |
| `dlt pipeline <name> sync` | Restores local state from the destination | "Destination bilan sinxronlashtirish" button |
| `dlt pipeline <name> drop <resource>` | Resets one resource's table + state | "Jadvalni qayta o'rnatish" button |
| Automatic retry on transient errors | dlt retries network blips on its own | Nothing to build — happens silently |
| `schema_contract` (`evolve`/`freeze`/`discard_row`/`discard_value`) | Gate structural changes (new table/column/type) at ingestion | Not exposed yet — dlt's default `evolve` behavior applies |

**What Chumoli adds on top (the only new code needed here):** small
wrapper functions in `pipeline_runner.py` that call these dlt CLI
commands programmatically (not via shell — dlt exposes equivalent
Python-level pipeline methods), translate error output into plain
Uzbek, and expose them as single dashboard buttons. This was called
"Recovery functions" in earlier planning — the design hasn't changed,
only the file location (this doc replaces the old inline section).

## 2. Content-level quality checks — built (`core/quality.py`)

Implemented, tested against a real DuckDB destination (11 tests in
`tests/test_quality.py`, plus one full end-to-end test through
`run_pipeline_by_name` in `tests/test_e2e_rest_api_to_duckdb.py`):

| Check | What it verifies | Config field |
|---|---|---|
| `row_count` | Minimum expected rows (catches empty loads) | `QualityConfig.row_count_min` |
| `not_null` | Required columns have no nulls | `QualityConfig.not_null_columns` |
| `no_duplicates` | Primary key uniqueness | `QualityConfig.no_duplicates_key` |
| `freshness` | Data isn't stale beyond an SLA | `QualityConfig.freshness_max_minutes` + `QualityConfig.freshness_column` |

Each check returns a `CheckOutcome` (pass/fail + a plain-Uzbek detail
string); all outcomes for a run are collected into a `QualityReport`,
attached to `RunResult.quality_report`. Checks run via
`pipeline.sql_client()` — dlt's own, free, destination-agnostic SQL
execution API (confirmed in `dlt-boundary.md` to be part of open dlt,
not dltHub) — so the same check code works unchanged against DuckDB,
Postgres, or any other SQL destination dlt supports.

**Why `RunResult.success` stays load-only, not load-AND-quality:** a
load can succeed while quality still fails (data arrived, but less of
it than expected). Collapsing these into one boolean would hide which
kind of failure occurred. The CLI (`chumoli run`) makes the practical
call explicit: it exits 0 only when BOTH load and quality pass, but
the underlying `RunResult.success` property intentionally still means
"did the load itself work" — callers building on top of
`pipeline_runner` directly get to decide how to combine the two
signals for their own context.

**A bug found while building this, worth keeping as a lesson:**
`pipeline_runner._get_row_counts` originally tried to read row counts
out of `LoadInfo.metrics`. When quality checks were wired in and
needed real row counts to know which tables to check, an end-to-end
test caught that `row_counts` was silently empty. Investigation
(actually running dlt and printing the real object shapes, not
guessing from documentation) showed `LoadInfo.metrics` and
`LoadInfo.load_packages` in dlt 1.30 carry file/job metadata
(`table_name`, `file_path`, timestamps) but genuinely no row count
field at all — the original code's assumption was wrong from the
start, not just a naming mismatch. The fix: read the true table list
from `pipeline.default_schema.tables` (filtering dlt's internal
`_dlt_*` tables) and query row counts directly via
`pipeline.sql_client()` — the same mechanism quality checks already
use. This is arguably a better design than the original anyway: one
mechanism (`sql_client()`) for both row counts and quality checks,
verified accurate by a real assertion (`assert result.row_counts ==
{"items": 2}`) rather than "the function ran without raising."

## 3. Notifications

`PipelineConfig.notify` already models `on_failure`, `on_success`, and
`telegram_chat_id`. The bot token itself is a global setting (one bot
serves all pipelines), not per-pipeline — it belongs in a `settings`
table in the control store, not in `PipelineConfig`. Telegram was the
channel already chosen in the original positioning docs ("standard
channel in Uzbekistan") — no new decision needed here, just
implementation.

## Why quality checks run AFTER load, not before

Pre-load validation would require buffering/inspecting data before it
reaches the destination, which either duplicates dlt's own extraction
work or requires intercepting its internal pipeline — both violate
"don't rewrite what dlt does." Running checks as plain SQL against the
already-loaded destination table is simpler, destination-agnostic (the
same SQL check works whether the destination is DuckDB, Postgres, or
ClickHouse), and matches how the original POSITIONING.md described it
("4 SQL checks, DuckDB native").

## Why "ahmoqroq odam ham boshqara olsin" (a less technical person can operate it) is satisfied

| Requirement | How it's met |
|---|---|
| No code/YAML to write | Manifest-driven form (`config-and-manifest.md`) |
| Understand why it broke | Plain-Uzbek translation of `failed-jobs` output |
| Recover with one click | Dashboard buttons mapped to dlt CLI commands |
| Get notified immediately | Telegram notify on failure |
| Can't destructively break things by accident | `ControlStore.save()` already enforces the secret-leak invariant (`security.md`); destructive dashboard actions (drop, reset) require explicit confirmation, matching dlt's own CLI behavior which also confirms before `drop` |
