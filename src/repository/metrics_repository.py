import json
import logging
import os
from pathlib import Path
from typing import Any
from config import config

logger = logging.getLogger(__name__)


class MetricsRepository:
    def __init__(self):
        self._path = config.ARCHIVE_ROOT_PATH.parent / "metrics.json"

    def read(self) -> dict[str, Any] | None:
        """Return the persisted counters dict, or None if it doesn't exist yet."""
        if not self._path.exists():
            return None
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.error("Failed to read metrics file at %s, starting from zero", self._path, exc_info=True)
            return None

    def write(self, counters: dict[str, Any]) -> None:
        """Persist the full counters dict, atomically."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(counters, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self._path)