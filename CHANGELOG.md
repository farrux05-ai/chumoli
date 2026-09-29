# Changelog

## Unreleased

### Fixed
- **Bitrix24:** drop experimental `columns` hints. They collided with dlt's
  snake_case normalization against an already-evolved pipeline schema
  (`backlogId`→`backlog_id`, etc.) and flooded logs without materializing
  null fields. Null-field type-inference WARNINGs are expected and harmless
  when the portal leaves those fields empty.

## 0.1.1 — 2026-09-27

### Added
- Source connectors: **Filesystem / S3** (`filesystem_s3`, dlt `readers`),
  **MoySklad** (JSON API 1.2), **Bitrix24** (inbound webhook / OAuth REST),
  **Meta Ads / Facebook Ads** (`facebook_ads`, Marketing API — beta, live token)
- Failed runs are now persisted to run history for manual (sync), async and demo
  runs. Previously only scheduler runs recorded failures, so a dashboard-triggered
  failure left no trace beyond a transient toast.
- `RunResult.error` / `RunResponse.error`: the dlt failed-jobs reason is captured
  and shown in the dashboard run history.
- `core/errors.py`: credential redaction (`sanitize_error`) and friendly mapping
  (`friendly_error`) so stored/displayed errors never leak passwords or tokens.

### Changed
- ClickHouse loads now use `parquet` instead of dlt's `jsonl` default (columnar +
  compressed; much faster for anything but a handful of rows).
- Quality checks reuse a single `sql_client` instead of opening one per check —
  avoids a connect/auth round-trip per check on remote destinations.

### Fixed
- **`drop-resource` was a silent no-op for DuckDB:** the dlt CLI ran as a
  separate process without the destination credentials, so it opened a stray
  empty `<cwd>/<pipeline>.duckdb`, "dropped" there and reported success while the
  real table stayed. It now runs in-process on the pipeline built from the
  stored config (`dlt.pipeline.helpers.pipeline_drop`), like recovery's other
  actions — the drop hits the real destination and no longer litters the working
  directory. A drop that matches no table/state is reported as an error, not `ok`.
- `tests/test_recovery.py` now asserts the dropped table is actually gone from
  the destination — the old assertion only checked the success message, which is
  how the no-op above stayed hidden.
- Meta Ads (`facebook_ads`) now retries 429/5xx: the Meta JSON error was raised
  as `ValueError`, which the shared retry policy treats as non-transient, so
  rate limits were never retried (transient statuses are now re-raised as
  `HTTPStatusError`; JSON-less error pages are handled too)
- MoySklad `updated>=` filter uses Moscow time (the server's timezone), not
  Tashkent — the 2-hour offset could skip records at the filter boundary
- MoySklad `stock` merge key is derived from `meta.href` with the query string
  stripped (stable across `?expand=...`), falling back to the nested product id
- Pagination no longer risks an infinite loop when the API cursor does not
  advance (Bitrix24 `next: 0`, Meta Ads repeated `after`)
- Filesystem / S3: a dotted directory (`s3://bucket/data.v2`) is no longer
  mistaken for a single file and silently read as empty
- `.gitignore`: `.uzpipe/` is ignored again — the inline comment on that line
  prevented the rule from matching
- `drop-resource` recovery was completely broken: the dlt CLI was invoked with
  `--pipelines-dir` *after* the subcommand (rejected as "unrecognized arguments")
  and without `-y` (could hang on the interactive confirmation). Now uses
  `dlt -y pipeline --pipelines-dir <dir> <name> drop <resource>`.
- Dashboard run stats: load-OK but quality-fail runs no longer counted as
  "Muvaffaqiyatli"; new `quality_warn` field so "Quality ogohlantirish" card is accurate
- Run history now shows the failure reason (redacted) instead of only a red badge
- Recovery (`sync` / `drop-pending` / `drop-resource`) now refuses to run while the
  pipeline is loading — wiping pending dirs or dropping a table mid-load corrupts
  dlt state
- Recovery error messages are redacted (no connection-string passwords in toasts)
- Dashboard recovery buttons disable during the action and surface failures as
  errors (an error payload was previously toasted as success)

## 0.1.0 — 2026-09-23

### Added
- PyPI packaging polish: classifiers, `pip install chumoli`, wheel static include
- Connector `maturity` (`stable` | `beta`) — UI badge
- Local filesystem: hidden dlt staging; user folder gets clean tables only
- Native folder picker for local filesystem destination
- CI: pytest 3.11/3.12 + Docker smoke

### Fixed
- Click connector auth raised `NameError` (`time` not imported) — connector was unusable
- Filesystem export silently failed: `Path` was undefined in `_execute` and the
  error was swallowed by `except Exception`
- Wheel build failed with duplicate `chumoli/static/index.html` (redundant
  `force-include`); static is now packaged via `packages = ["src/chumoli"]`
- Single source of truth for the version (`src/chumoli/__init__.py`);
  `pyproject.toml` and the FastAPI app read it dynamically

### Removed
- Unused imports across `src` and `tests`
- Stale `tests/static/` dashboard copies (canonical UI is `src/chumoli/static/index.html`)

### Notes
- UZ connectors (Click, Payme, Uzum Market, Didox) are **beta** — test with your own API keys
- Stable: SQL, REST, synthetic volume, DuckDB / filesystem / S3 destinations
