# Changelog

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
