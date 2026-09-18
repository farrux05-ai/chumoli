# UzPipe — Documentation index

**Read this file first, every time.** Below is what each document
covers and when to open it — find the relevant section, open only
that. No monolith file, because reading (or updating) one giant
document every time wastes time and attention.

## Getting oriented

**What the project is:** [`../README.md`](../README.md) — one-paragraph
product description.

**Where things stand right now:** [`status.md`](status.md) — what code
exists, what doesn't, test status. Open this every time, then move to
whichever section you actually need.

## Architecture documents (`architecture/`)

| File | When to read it |
|---|---|
| [`architecture/dlt-boundary.md`](architecture/dlt-boundary.md) | **Before adding any new functionality.** What dlt (free) provides vs. what dltHub (commercial) provides — getting this boundary wrong once already led to a licensing trap; the lesson is documented here |
| [`architecture/overview.md`](architecture/overview.md) | When you need the full layer map — answers "which layer does this belong to" |
| [`architecture/config-and-manifest.md`](architecture/config-and-manifest.md) | When working on connector manifests or `PipelineConfig` |
| [`architecture/security.md`](architecture/security.md) | When working on credentials, encryption, or the control store |
| [`architecture/dashboard.md`](architecture/dashboard.md) | When building or changing the dashboard (marimo) |
| [`architecture/quality-and-reliability.md`](architecture/quality-and-reliability.md) | When working on quality checks, recovery, or error handling |
| [`architecture/scalability.md`](architecture/scalability.md) | When asking "does this decision still hold at connector #50" |

## Practical guides

| File | When to read it |
|---|---|
| [`connector-skill.md`](connector-skill.md) | Before writing a new connector (Payme, Click, etc.) — step-by-step |

## Update rule

Each file covers ONE topic. When a decision or correction is added:
1. Find the matching file from the tables above
2. Update that file only — don't touch unrelated files
3. If a decision genuinely affects multiple files (rare), leave a short
   note in each with "details: `other-file.md`" — don't duplicate content
