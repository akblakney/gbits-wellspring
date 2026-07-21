"""
Layout: <ARCHIVE_ROOT_PATH>/<YYYY-MM-DD>/<HH>.stats.json, sitting alongside
the existing <HH>.bin / <HH>.meta.jsonl files for that hour.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class StatsRepository:
    def __init__(self, root_path: Path):
        self._root_path = Path(root_path)

    def bin_path_for_hour(self, hour_start: datetime) -> Path:
        return self._hour_dir(hour_start) / f"{hour_start.strftime('%H')}.bin"

    def stats_path_for_hour(self, hour_start: datetime) -> Path:
        return self._hour_dir(hour_start) / f"{hour_start.strftime('%H')}.stats.json"

    def _hour_dir(self, hour_start: datetime) -> Path:
        return self._root_path / hour_start.strftime("%Y-%m-%d")

    def read(self, hour_start: datetime) -> dict[str, Any] | None:
        """Return cached results for this hour, or None if not yet computed."""
        path = self.stats_path_for_hour(hour_start)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.error("Failed to read stats cache at %s, will recompute", path, exc_info=True)
            return None

    def write(self, hour_start: datetime, results: dict[str, Any]) -> None:
        path = self.stats_path_for_hour(hour_start)
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=_json_default)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic on POSIX
        logger.debug("Wrote stats cache to %s", path)


def _json_default(obj: Any) -> Any:
    """
    Fallback for json.dump to handle numpy scalar types"""
    if hasattr(obj, "item"):  # covers np.generic (numpy scalars)
        return obj.item()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")