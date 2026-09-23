# Changelog

## 0.1.0 — 2026-09-23

### Added
- PyPI packaging polish: classifiers, `pip install chumoli`, wheel static include
- Connector `maturity` (`stable` | `beta`) — UI badge
- Local filesystem: hidden dlt staging; user folder gets clean tables only
- Native folder picker for local filesystem destination
- CI: pytest 3.11/3.12 + Docker smoke

### Notes
- UZ connectors (Click, Payme, Uzum Market, Didox) are **beta** — test with your own API keys
- Stable: SQL, REST, synthetic volume, DuckDB / filesystem / S3 destinations
