"""
chumoli.core.logging_setup
===========================

Butun ilova uchun yagona structlog konfiguratsiyasi.
CHUMOLI_LOG_FORMAT=json → prod (Grafana/Loki uchun)
CHUMOLI_LOG_FORMAT=console → dev (rang-barang, o'qish oson)

Chaqirish joyi: api/app.py startup da, cli.py da.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog

_CONFIGURED = False


def configure_logging() -> None:
    """Bir marta chaqiriladi — ikki marta chaqirilsa idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_format = os.environ.get("CHUMOLI_LOG_FORMAT", "console").lower()
    log_level_str = os.environ.get("CHUMOLI_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # stdlib logging → structlog orqali yo'naltirish
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    # dlt + pyarrow: nullable/precision hints vs Arrow schema farqi —
    # load ishlayveradi, lekin har batch da WARNING shovqin chiqaradi.
    # See dlt-hub/dlt#2788, #3581. INFO da to'liq log qoladi.
    class _DltArrowSchemaHintNoiseFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            if "when merging arrow schema with dlt schema" in msg:
                return False
            if "arrow schema and data were unmodified" in msg:
                return False
            return True

    for name in ("dlt", "dlt.extract", "dlt.extract.extractors"):
        logging.getLogger(name).addFilter(_DltArrowSchemaHintNoiseFilter())

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str | None = None) -> Any:
    """structlog bound logger (configure_logging birinchi marta avtomatik)."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)
