import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DAY_DIR_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HOUR_BIN_PATTERN = re.compile(r"^(\d{2})\.bin$")
BEACON_DAY_FILE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")


def day_dir(root: Path, dt: datetime) -> Path:
    """<root>/<YYYY-MM-DD>"""
    return Path(root) / dt.strftime("%Y-%m-%d")


def archive_bin_path(root: Path, dt: datetime) -> Path:
    """<root>/<YYYY-MM-DD>/<HH>.bin"""
    return day_dir(root, dt) / f"{dt.strftime('%H')}.bin"


def archive_meta_path(root: Path, dt: datetime) -> Path:
    """<root>/<YYYY-MM-DD>/<HH>.meta.jsonl"""
    return day_dir(root, dt) / f"{dt.strftime('%H')}.meta.jsonl"


def stats_path(root: Path, dt: datetime) -> Path:
    """<root>/<YYYY-MM-DD>/<HH>.stats.json"""
    return day_dir(root, dt) / f"{dt.strftime('%H')}.stats.json"


def beacon_day_path(root: Path, dt: datetime) -> Path:
    """<root>/<YYYY-MM-DD>.jsonl"""
    return Path(root) / f"{dt.strftime('%Y-%m-%d')}.jsonl"


def iter_archive_hours(
    root: Path,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Iterator[tuple[datetime, Path]]:
    """
    Yield (hour_start_utc, bin_path) for every existing archived .bin
    file under `root`, in chronological order, optionally restricted to
    [start, end] inclusive (both tz-aware UTC datetimes; either may be
    None for an unbounded side).

    Walks the actual on-disk directory structure rather than assuming a
    contiguous date range, so gaps (missing hours/days -- e.g. from
    downtime) are handled naturally: they're just absent, not an error.
    """
    root = Path(root)
    if not root.exists():
        return

    for day_path in sorted(root.iterdir()):
        if not day_path.is_dir() or not DAY_DIR_PATTERN.match(day_path.name):
            continue

        day_date = datetime.strptime(day_path.name, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        # Cheap day-level skip before even listing hour files.
        if start is not None and day_date.replace(hour=23, minute=59, second=59) < start:
            continue
        if end is not None and day_date > end:
            continue

        for hour_path in sorted(day_path.iterdir()):
            match = HOUR_BIN_PATTERN.match(hour_path.name)
            if not match:
                continue
            hour = int(match.group(1))
            hour_start = day_date.replace(hour=hour)

            if start is not None and hour_start < start:
                continue
            if end is not None and hour_start > end:
                continue

            yield hour_start, hour_path


def iter_beacon_pulses(
    root: Path,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Iterator[dict]:
    """
    Yield beacon pulses (as dicts) in chronological (pulse_index)
    order, optionally restricted to [start, end] inclusive (tz-aware
    UTC datetimes; either may be None for an unbounded side).
    """
    root = Path(root)
    if not root.exists():
        return

    for day_path in sorted(root.glob("*.jsonl")):
        match = BEACON_DAY_FILE_PATTERN.match(day_path.name)
        if not match:
            continue

        day_date = datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)

        # Cheap day-level skip before reading the file at all.
        if start is not None and day_date.replace(hour=23, minute=59, second=59) < start:
            continue
        if end is not None and day_date > end:
            continue

        with open(day_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pulse = json.loads(line)

                pulse_ts = datetime.fromisoformat(pulse["timestamp_utc"])
                if start is not None and pulse_ts < start:
                    continue
                if end is not None and pulse_ts > end:
                    continue

                yield pulse