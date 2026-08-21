"""
live_bytes_display.py — a lightweight terminal visualization that
tails the latest archive .bin file and displays recent bytes as
scrolling ASCII, refreshing periodically. Purely cosmetic/fun -- not
part of the actual service, safe to run alongside it.

Usage:
    python tools/live_bytes_display.py
    python tools/live_bytes_display.py --refresh-rate 0.5 --num-bytes 512
    (press 'q' to quit)

Run from inside src/.

Design notes (kept deliberately lightweight, since this runs alongside
the real service):
  - Only ever seeks to and reads the last --num-bytes of the current
    hour's .bin file -- never reads the whole (potentially large) file.
  - "Latest file" is resolved directly from the current timestamp (with
    a fallback to the previous hour right after an hour rollover),
    reusing util.navigate's path helpers -- no directory scanning.
  - Non-printable bytes are simply replaced with a placeholder
    character rather than mapped via unbiased rejection sampling (the
    technique used for real password-generation output on the
    website). That rigor doesn't matter here -- this is a cosmetic
    display, not a security-relevant feature -- so the simpler
    approach is the right amount of effort.
  - The wait-for-next-refresh and check-for-quit-key steps are combined
    into a single curses timeout()+getch() call, so the tool sits
    blocked in one system call between refreshes rather than busy-
    polling or using an extra thread.
  - Reads the file with no cross-process locking against
    ArchiveRepository's writer. Fine for a cosmetic tool -- worst case
    is an occasional torn read of the last couple bytes, invisible in
    practice at this refresh rate.
"""

import argparse
import curses
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import config
from util.navigate import archive_bin_path

PRINTABLE_MIN = 32   # space
PRINTABLE_MAX = 126  # '~'
PLACEHOLDER_CHAR = ""


def find_latest_bin_path(root: Path, now: datetime | None = None) -> Path | None:
    now = now or datetime.now(timezone.utc)

    current = archive_bin_path(root, now)
    if current.exists():
        return current

    previous = archive_bin_path(root, now - timedelta(hours=1))
    if previous.exists():
        return previous

    return None


def read_tail_bytes(path: Path, num_bytes: int) -> bytes:
    with open(path, "rb") as f:
        f.seek(0, 2)  # SEEK_END
        size = f.tell()
        f.seek(max(0, size - num_bytes))
        return f.read(num_bytes)


def bytes_to_display(data: bytes) -> str:
    return "".join(
        chr(b) if PRINTABLE_MIN <= b <= PRINTABLE_MAX else PLACEHOLDER_CHAR
        for b in data
    )


def wrap_to_width(text: str, width: int) -> list[str]:
    if width <= 0:
        return [text]
    return [text[i:i + width] for i in range(0, len(text), width)]


def run_display(stdscr, refresh_rate: float, num_bytes: int, root: Path) -> None:
    curses.curs_set(0)  # hide cursor
    stdscr.timeout(int(refresh_rate * 1000))  # ms; also doubles as the refresh wait

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        bin_path = find_latest_bin_path(root)

        if bin_path is None:
            stdscr.addstr(0, 0, "No archive data found yet.")
        else:
            try:
                tail = read_tail_bytes(bin_path, num_bytes)
            except OSError as e:
                tail = b""
                stdscr.addstr(0, 0, f"Read error: {e}")
            else:
                header = f" {bin_path.name} -- last {len(tail)} bytes -- refresh {refresh_rate}s -- 'q' to quit "
                stdscr.addstr(0, 0, header[: max(0, width - 1)], curses.A_BOLD)

                display_text = bytes_to_display(tail)
                lines = wrap_to_width(display_text, max(1, width - 1))
                for i, line in enumerate(lines):
                    row = i + 2
                    if row >= height:
                        break
                    stdscr.addstr(row, 0, line)

        stdscr.refresh()

        key = stdscr.getch()  # blocks up to refresh_rate seconds, or returns a key immediately
        if key in (ord("q"), ord("Q")):
            break


def parse_args():
    parser = argparse.ArgumentParser(description="Live display of recent archive bytes")
    parser.add_argument(
        "--refresh-rate", type=float, default=1.0,
        help="Seconds between refreshes (default: 1.0)",
    )
    parser.add_argument(
        "--num-bytes", type=int, default=256,
        help="Number of trailing bytes to read and display each refresh (default: 256)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.refresh_rate <= 0:
        print("Error: --refresh-rate must be positive", file=sys.stderr)
        sys.exit(1)
    if args.num_bytes <= 0:
        print("Error: --num-bytes must be positive", file=sys.stderr)
        sys.exit(1)

    try:
        curses.wrapper(run_display, args.refresh_rate, args.num_bytes, config.ARCHIVE_ROOT_PATH)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
