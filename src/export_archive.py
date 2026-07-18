"""
Usage:
    python export_archive.py                                # all archived data
    python export_archive.py --start 2026-07-01              # from this date onward (inclusive)
    python export_archive.py --end 2026-07-15                # through this date (inclusive)
    python export_archive.py --start 2026-07-01 --end 2026-07-15
"""

import argparse
import sys
from datetime import datetime, timezone

from config import config
from util.navigate import iter_archive_hours

CHUNK_SIZE = 65536


def parse_date_utc(date_str: str, end_of_day: bool = False) -> datetime:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


def parse_args():
    parser = argparse.ArgumentParser(description="Stream archived .bin entropy data to stdout")
    parser.add_argument(
        "--start", type=str, default=None,
        help="Start date (YYYY-MM-DD), inclusive. Omit for no lower bound.",
    )
    parser.add_argument(
        "--end", type=str, default=None,
        help="End date (YYYY-MM-DD), inclusive. Omit for no upper bound.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        start = parse_date_utc(args.start) if args.start else None
        end = parse_date_utc(args.end, end_of_day=True) if args.end else None
    except ValueError:
        print(f"Error: invalid date, expected YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    if start is not None and end is not None and start > end:
        print(f"Error: --start ({args.start}) is after --end ({args.end})", file=sys.stderr)
        sys.exit(1)

    total_bytes = 0
    total_files = 0
    out = sys.stdout.buffer

    for hour_start, bin_path in iter_archive_hours(config.ARCHIVE_ROOT_PATH, start=start, end=end):
        with open(bin_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
                total_bytes += len(chunk)
        total_files += 1

    out.flush()
    print(f"Streamed {total_bytes} bytes from {total_files} hour file(s)", file=sys.stderr)


if __name__ == "__main__":
    main()