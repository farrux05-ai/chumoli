"""uzpipe.core.scheduler — APScheduler interval jobs for pipelines."""
from __future__ import annotations

import logging
import threading
from typing import Any

from uzpipe.core.pipeline_runner import run_pipeline_by_name
from uzpipe.store.control_store import ControlStore
from uzpipe.store.run_store import RunStore

log = logging.getLogger("uzpipe.scheduler")

_lock = threading.RLock()
_scheduler: Any = None
_started = False
