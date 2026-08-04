"""
responsible for on-disk archive format

Layout: <ARCHIVE_ROOT_PATH>/<YYYY-MM-DD>/<HH>.bin + <HH>.meta.jsonl + <HH>.raw (optional)

- <HH>.bin is a flat, append-only stream of raw chunk bytes.
- <HH>.meta.jsonl is a JSON-lines file with a strict one-to-one,
  same-order correspondence to the chunks written into <HH>.bin
- <HH>.raw is an flat, append-only stream of raw audio samples
"""

import json
import logging
import struct
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from model.chunk import Chunk
from config import config

logger = logging.getLogger(__name__)

RAW_SAMPLE_FORMAT = "int16_le"
_RAW_SAMPLE_STRUCT_CODE = "h"  # signed short


class ArchiveRepository:
    def __init__(self, root_path: Path | None = None, format_version: int | None = None):
        self._root_path = Path(root_path) if root_path is not None else config.ARCHIVE_ROOT_PATH
        self._format_version = format_version if format_version is not None else config.ARCHIVE_FORMAT_VERSION

        # Guards all file writes
        self._lock = threading.Lock()

    def write_chunk(self, chunk: Chunk, reason: str, archive_values: bool = False) -> None:
        with self._lock:
            bin_path, meta_path, raw_path = self._resolve_paths(chunk.created_at)
            bin_path.parent.mkdir(parents=True, exist_ok=True)

            self._write_header_if_new(meta_path)

            self._append_bytes(bin_path, chunk.data)

            write_raw = archive_values and bool(chunk.audio_samples)
            if archive_values and not chunk.audio_samples:
                logger.warning(
                    "archive_values=True but chunk has no audio_samples -- skipping .raw write for this chunk"
                )

            if write_raw:
                self._append_raw_samples(raw_path, chunk.audio_samples)

            self._append_metadata(meta_path, chunk, reason, audio_samples_included=write_raw)

    def _resolve_paths(self, unix_timestamp: float) -> tuple[Path, Path, Path]:
        dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
        day_dir = self._root_path / dt.strftime("%Y-%m-%d")
        hour_str = dt.strftime("%H")
        return (
            day_dir / f"{hour_str}.bin",
            day_dir / f"{hour_str}.meta.jsonl",
            day_dir / f"{hour_str}.raw",
        )

    def _write_header_if_new(self, meta_path: Path) -> None:
        if meta_path.exists():
            return

        hour_start = self._hour_start_iso(meta_path)
        header = {
            "type": "header",
            "hour_start_utc": hour_start,
            "format_version": self._format_version,
            "raw_sample_format": RAW_SAMPLE_FORMAT,
            "written_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        with open(meta_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(header) + "\n")
            f.flush()
        logger.debug("Started new archive hour file: %s", meta_path)

    @staticmethod
    def _hour_start_iso(meta_path: Path) -> str:
        # Derive hour-start timestamp from the path itself (YYYY-MM-DD/HH.meta.jsonl)
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
    def _append_raw_samples(raw_path: Path, audio_samples: list[int]) -> None:
        packed = struct.pack(f"<{len(audio_samples)}{_RAW_SAMPLE_STRUCT_CODE}", *audio_samples)
        with open(raw_path, "ab") as f:
            f.write(packed)
            f.flush()

    @staticmethod
    def _append_metadata(meta_path: Path, chunk: Chunk, reason: str, audio_samples_included: bool) -> None:
        record = {
            "type": "chunk",
            "generated_at_unix": chunk.created_at,
            "archived_at_unix": time.time(),
            "length_bytes": len(chunk),
            "reason": reason,
            "audio_samples_included": audio_samples_included,
        }
        if audio_samples_included:
            record["audio_samples_count"] = len(chunk.audio_samples)
        with open(meta_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()