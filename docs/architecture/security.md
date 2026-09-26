# Security: credentials and control store

Covers: `security/crypto.py`, `store/control_store.py`.

## Threat model (explicit, so scope stays honest)

Chumoli is a **single-user, local-first** tool (`pip install`,
localhost). The threat this design protects against:

- Credentials accidentally committed to git
- Credentials readable by an unrelated process/tool on the same machine
- Credentials stored in plaintext by mistake in application code

The threat this design does **NOT** protect against:

- Someone with full filesystem access to the user's machine (both the
  key file and the SQLite file) — this is an OS-level concern
  (file permissions), not something a local app can solve without a
  hardware security module or OS keychain integration, which is out
  of scope for a zero-friction MVP.

## Why Fernet (symmetric), not asymmetric encryption

Encryptor and decryptor are the same machine, same user. Asymmetric
crypto (e.g. RSA) would add complexity without adding real security
here, since the private key would have to live on the same disk
anyway. Fernet (`cryptography` library — AES-128-CBC + HMAC) is the
standard tool for exactly this "encrypt now, decrypt later, same
owner" pattern.

## Why the master key lives in a file (`~/.chumoli/master.key`), not an env var

The zero-friction requirement means the user does zero setup. A key
file generated on first run, saved with `chmod 600`, follows the same
pattern as SSH keys (`~/.ssh/`) — a well-understood convention, not a
novel one.

## Why credentials and config live in the SAME SQLite row (not a joined table)

A pipeline has exactly one credential set — always 1:1, never 1:many.
A separate `credentials` table joined by `pipeline_id` would only add
JOIN overhead and a second place where "pipeline created but
credentials write failed" inconsistency could occur. One row, atomic
write, no join.

## Why secrets are one JSON blob column, not one column per secret field

Different connectors have different numbers and names of secret
fields (Payme: 2, Didox: 1, etc.). A column-per-secret schema would
require `ALTER TABLE` every time a new connector is added — exactly
the kind of dashboard-touching change the manifest system exists to
avoid (see `config-and-manifest.md`). The manifest, not the database
schema, is the source of truth for which keys exist inside the blob.

## Why SQLite, not DuckDB, for the control store

DuckDB is optimized for analytical, read-heavy workloads. The control
store is write-heavy relative to that (every pipeline create/edit from
the dashboard writes here) and needs reliable concurrent-write
behavior (dashboard, CLI, and a background run could all touch it).
SQLite in WAL mode handles this well; DuckDB is not designed for it.
Run history lives in a **separate SQLite file** (`chumoli_runs.db`) — it
is append-mostly and low-volume, so it stays on SQLite too. DuckDB is
reserved for the analytical destination data, not for control-plane
metadata.

## The one enforced invariant: secrets can never leak into `source_params`

`ControlStore.save()` explicitly checks that none of `manifest.secret_keys()`
appear inside `config.source_params`, and raises if they do. This is a
deliberate defense-in-depth layer: even if a caller makes a mistake
upstream (e.g. accidentally puts a form's raw dict straight into
`source_params` instead of splitting secrets out first), the store
refuses to persist a plaintext secret rather than silently accepting
it. This is tested directly (`test_save_rejects_secret_leaked_in_source_params`).

## What `list_all()` deliberately omits

`ControlStore.list_all()` (used by any pipeline listing UI) never
returns secrets — not even encrypted. The reasoning: a list view has
no legitimate need for credentials, encrypted or not, so the safest
default is to not include them in the return type at all. Anyone who
actually needs a pipeline's secrets must call `load(name)` explicitly
— a call whose presence in code review signals "this code needs
credentials," which is a useful signal to preserve.
