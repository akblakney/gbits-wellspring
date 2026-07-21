"""
responsible for on-disk archive format

Layout: <ARCHIVE_ROOT_PATH>/<YYYY-MM-DD>/<HH>.bin + <HH>.meta.jsonl

- <HH>.bin is a flat, append-only stream of raw chunk bytes, nothing else.
- <HH>.meta.jsonl is a JSON-lines file with a strict one-to-one,
  same-order correspondence to the chunks written into <HH>.bin:
    - line 1 is a header record (hour start, format version, etc.)
    - each subsequent line is one record per archived chunk, in the
      same order they were appended to the .bin file.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from model.chunk import Chunk
from config import config

logger = logging.getLogger(__name__)


class ArchiveRepository:
    def __init__(self, root_path: Path | None = None, format_version: int | None = None):
        self._root_path = Path(root_path) if root_path is not None else config.ARCHIVE_ROOT_PATH
        self._format_version = format_version if format_version is not None else config.ARCHIVE_FORMAT_VERSION

        # Guards all file writes. Archive writes can come from the
        # generator thread (sweep_expired) and from request-handling
        # threads (archive_excess) concurrently, so this must be a real
        # lock, not just "single-threaded assumption."
        self._lock = threading.Lock()

    def write_chunk(self, chunk: Chunk, reason: str) -> None:
        with self._lock:
            bin_path, meta_path = self._resolve_paths(chunk.created_at)
            bin_path.parent.mkdir(parents=True, exist_ok=True)

            self._write_header_if_new(meta_path)

            # Bytes first, flushed, THEN metadata — see fail-safety note above.
            self._append_bytes(bin_path, chunk.data)
            self._append_metadata(meta_path, chunk, reason)

    def _resolve_paths(self, unix_timestamp: float) -> tuple[Path, Path]:
        dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
        day_dir = self._root_path / dt.strftime("%Y-%m-%d")
        hour_str = dt.strftime("%H")
        return day_dir / f"{hour_str}.bin", day_dir / f"{hour_str}.meta.jsonl"

    def _write_header_if_new(self, meta_path: Path) -> None:
        if meta_path.exists():
            return

        hour_start = self._hour_start_iso(meta_path)
        header = {
            "type": "header",
            "hour_start_utc": hour_start,
            "format_version": self._format_version,
            "written_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        with open(meta_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(header) + "\n")
            f.flush()
        logger.debug("Started new archive hour file: %s", meta_path)

    @staticmethod
    def _hour_start_iso(meta_path: Path) -> str:
        # Derive hour-start timestamp from the path itself (YYYY-MM-DD/HH.meta.jsonl)
        # rather than "now", since header creation could theoretically lag
        # the actual hour boundary slightly.
        day_str = meta_path.parent.name
        hour_str = meta_path.stem.split(".")[0]  # "HH" from "HH.meta"
        dt = datetime.strptime(f"{day_str} {hour_str}", "%Y-%m-%d %H").replace(tzinfo=timezone.utc)
        return dt.isoformat()

    @staticmethod
    def _append_bytes(bin_path: Path, data: bytes) -> None:
        with open(bin_path, "ab") as f:
            f.write(data)
            f.flush()

    @staticmethod
    def _append_metadata(meta_path: Path, chunk: Chunk, reason: str) -> None:
        record = {
            "type": "chunk",
            "generated_at_unix": chunk.created_at,
            "archived_at_unix": time.time(),
            "length_bytes": len(chunk),
            "reason": reason,
        }
        with open(meta_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()