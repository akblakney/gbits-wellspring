"""
BeaconRepository — owns on-disk storage for beacon pulses, with a
memory-bounded lookup strategy.

Layout: <BEACON_ROOT_PATH>/<YYYY-MM-DD>.jsonl, append-only, one JSON
pulse record per line. Public, permanent data (unlike the archive) --
every pulse must remain retrievable forever.

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

        self._latest: dict[str, Any] | None = None
        # day_str ("YYYY-MM-DD") -> (first_pulse_index, last_pulse_index)
        self._day_index: dict[str, tuple[int, int]] = {}

        self._load_day_index_and_latest()

    def append(self, pulse: dict[str, Any]) -> None:
        with self._lock:
            day_str = self._day_str_for(pulse["timestamp_utc"])
            path = self._root_path / f"{day_str}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(pulse) + "\n")
                f.flush()
                os.fsync(f.fileno())

            first, _ = self._day_index.get(day_str, (pulse["pulse_index"], None))
            self._day_index[day_str] = (first, pulse["pulse_index"])
            self._latest = pulse
        logger.debug("Appended beacon pulse index=%s to %s", pulse["pulse_index"], day_str)

    def get_latest(self) -> dict[str, Any] | None:
        with self._lock:
            return self._latest

    def get_by_index(self, pulse_index: int) -> dict[str, Any] | None:
        with self._lock:
            day_index_snapshot = dict(self._day_index)  # copy; don't hold lock during file I/O

        day_str = self._find_day_for_index(day_index_snapshot, pulse_index)
        if day_str is None:
            return None
        return self._scan_day_file_for_index(day_str, pulse_index)

    def get_by_timestamp(self, timestamp_utc: datetime) -> dict[str, Any] | None:
        # Timestamp directly tells us the day file -- no index needed here.
        day_str = timestamp_utc.strftime("%Y-%m-%d")
        target_iso = timestamp_utc.isoformat()
        return self._scan_day_file_for_timestamp(day_str, target_iso)

    @staticmethod
    def _find_day_for_index(day_index: dict[str, tuple[int, int]], target_index: int) -> str | None:
        # Number of DAYS is small (thousands even after years), so a
        # linear scan here is trivial -- this is scanning day entries,
        # not pulses.
        for day_str, (first, last) in day_index.items():
            if first <= target_index <= last:
                return day_str
        return None

    def _scan_day_file_for_index(self, day_str: str, target_index: int) -> dict[str, Any] | None:
        path = self._root_path / f"{day_str}.jsonl"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pulse = json.loads(line)
                if pulse["pulse_index"] == target_index:
                    return pulse
        return None

    def _scan_day_file_for_timestamp(self, day_str: str, target_iso: str) -> dict[str, Any] | None:
        path = self._root_path / f"{day_str}.jsonl"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pulse = json.loads(line)
                if pulse["timestamp_utc"] == target_iso:
                    return pulse
        return None

    def _load_day_index_and_latest(self) -> None:
        if not self._root_path.exists():
            return
        files = sorted(self._root_path.glob("*.jsonl"))  # chronological, filenames are YYYY-MM-DD
        for path in files:
            first = self._read_first_line_json(path)
            last = self._read_last_line_json(path)
            if first is None or last is None:
                continue
            day_str = path.stem
            self._day_index[day_str] = (first["pulse_index"], last["pulse_index"])
            self._latest = last  # files processed in chronological order, so this ends on the true latest

        if self._day_index:
            logger.info(
                "Loaded beacon day index: %d day(s), latest pulse_index=%s",
                len(self._day_index),
                self._latest["pulse_index"] if self._latest else None,
            )

    @staticmethod
    def _read_first_line_json(path: Path) -> dict[str, Any] | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                line = f.readline().strip()
                return json.loads(line) if line else None
        except (OSError, json.JSONDecodeError):
            logger.error("Failed to read first line of %s", path, exc_info=True)
            return None

    @staticmethod
    def _read_last_line_json(path: Path, chunk_size: int = 4096) -> dict[str, Any] | None:
        """
        Read just the last line of a file by seeking backward from the
        end, rather than loading the whole file -- keeps startup cheap
        even if a day file were unexpectedly large.
        """
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                pointer = file_size
                buffer = b""
                while pointer > 0:
                    read_size = min(chunk_size, pointer)
                    pointer -= read_size
                    f.seek(pointer)
                    buffer = f.read(read_size) + buffer
                    if buffer.count(b"\n") >= 2 or pointer == 0:
                        break
                for raw_line in reversed(buffer.splitlines()):
                    line = raw_line.strip()
                    if line:
                        return json.loads(line)
                return None
        except (OSError, json.JSONDecodeError):
            logger.error("Failed to read last line of %s", path, exc_info=True)
            return None

    @staticmethod
    def _day_str_for(timestamp_iso: str) -> str:
        dt = datetime.fromisoformat(timestamp_iso)
        return dt.strftime("%Y-%m-%d")