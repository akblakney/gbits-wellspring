"""
Layout: <BEACON_ROOT_PATH>/<YYYY-MM-DD>.jsonl, append-only, one JSON pulse
record per line. This data is PUBLIC and PERMANENT (unlike the archive,
which stays private to Wellspring) -- once a pulse is published, it must
remain retrievable forever for the chain to be independently verifiable.

Total beacon data volume is tiny (one ~200-byte record per minute --
under 300KB/day), so all pulses are kept fully indexed in memory for
O(1) lookup by index or by timestamp, rebuilt from disk at startup and
kept in sync on every append. Disk remains the durable source of truth;
memory is just a read cache.
"""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BeaconRepository:
    def __init__(self, root_path: Path):
        self._root_path = Path(root_path)
        self._lock = threading.Lock()

        self._by_index: dict[int, dict[str, Any]] = {}
        self._by_timestamp: dict[str, dict[str, Any]] = {}  # keyed by ISO timestamp string
        self._latest: dict[str, Any] | None = None

        self._load_existing()

    def append(self, pulse: dict[str, Any]) -> None:
        with self._lock:
            day_str = self._day_str_for(pulse["timestamp_utc"])
            path = self._root_path / f"{day_str}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(pulse) + "\n")
                f.flush()
                os.fsync(f.fileno())

            self._index(pulse)
        logger.debug("Appended beacon pulse index=%s to %s", pulse["pulse_index"], path)

    def get_latest(self) -> dict[str, Any] | None:
        with self._lock:
            return self._latest

    def get_by_index(self, pulse_index: int) -> dict[str, Any] | None:
        with self._lock:
            return self._by_index.get(pulse_index)

    def get_by_timestamp(self, timestamp_utc: datetime) -> dict[str, Any] | None:
        with self._lock:
            return self._by_timestamp.get(timestamp_utc.isoformat())

    def _index(self, pulse: dict[str, Any]) -> None:
        self._by_index[pulse["pulse_index"]] = pulse
        self._by_timestamp[pulse["timestamp_utc"]] = pulse
        if self._latest is None or pulse["pulse_index"] > self._latest["pulse_index"]:
            self._latest = pulse

    def _load_existing(self) -> None:
        if not self._root_path.exists():
            return
        files = sorted(self._root_path.glob("*.jsonl"))
        count = 0
        for path in files:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        pulse = json.loads(line)
                    except json.JSONDecodeError:
                        logger.error("Skipping corrupt beacon line in %s", path, exc_info=True)
                        continue
                    self._index(pulse)
                    count += 1
        if count:
            logger.info("Loaded %d existing beacon pulses from disk", count)

    @staticmethod
    def _day_str_for(timestamp_iso: str) -> str:
        dt = datetime.fromisoformat(timestamp_iso)
        return dt.strftime("%Y-%m-%d")