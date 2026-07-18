"""
Usage:
    python verify_beacon_chain.py  # full history, from genesis
    python verify_beacon_chain.py --start 2026-07-01
    python verify_beacon_chain.py --start 2026-07-01 --end 2026-07-15

"""

import argparse
import sys
from datetime import datetime, timezone

from config import config
from util.navigate import iter_beacon_pulses
from service.beacon_service import BeaconService


def parse_date_utc(date_str: str, end_of_day: bool = False) -> datetime:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


def parse_args():
    parser = argparse.ArgumentParser(description="Verify the beacon's hash chain")
    parser.add_argument(
        "--start", type=str, default=None,
        help="Start date (YYYY-MM-DD), inclusive. Omit to verify from genesis (recommended).",
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
        print("Error: invalid date, expected YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    if start is not None and end is not None and start > end:
        print(f"Error: --start ({args.start}) is after --end ({args.end})", file=sys.stderr)
        sys.exit(1)

    # Tracks first/last pulse seen and a running count, as a side effect
    # of iterating -- avoids materializing the whole history as a list
    # just to report a summary.
    summary = {"count": 0, "first_index": None, "last_index": None, "first_ts": None, "last_ts": None}

    def tracked_pulses():
        for pulse in iter_beacon_pulses(config.BEACON_ROOT_PATH, start=start, end=end):
            if summary["count"] == 0:
                summary["first_index"] = pulse["pulse_index"]
                summary["first_ts"] = pulse["timestamp_utc"]
            summary["last_index"] = pulse["pulse_index"]
            summary["last_ts"] = pulse["timestamp_utc"]
            summary["count"] += 1
            yield pulse

    is_valid = BeaconService.verify_chain(tracked_pulses())

    if summary["count"] == 0:
        print("No pulses found in the given range.", file=sys.stderr)
        sys.exit(0)

    print(
        f"Checked {summary['count']} pulse(s): "
        f"index {summary['first_index']}..{summary['last_index']}, "
        f"{summary['first_ts']} to {summary['last_ts']}",
        file=sys.stderr,
    )

    if is_valid:
        print("Chain VALID", file=sys.stderr)
        sys.exit(0)
    else:
        print("Chain INVALID -- see warning above for which pulse failed", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()