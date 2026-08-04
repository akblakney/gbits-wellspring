"""
plot_raw_waveform.py — reads a .raw archive file (signed 16-bit
little-endian PCM audio samples, as written by ArchiveRepository when
write_chunk() is called with archive_values=True) and plots the
waveform to a PNG.

Usage:
    python tools/plot_raw_waveform.py path/to/13.raw
    python tools/plot_raw_waveform.py path/to/13.raw --output waveform.png
    python tools/plot_raw_waveform.py path/to/13.raw --rate 44100 --show

Later: this will share quantitative analysis logic (entropy,
autocorrelation, spectral peaks, etc.) with the standalone
tools/analyze_audio_source.py -- kept out of scope for this first pass,
which just plots the waveform. read_raw_samples() below is kept
separate from the plotting/CLI logic specifically so it's easy to reuse
once that analysis gets added.
"""

import argparse
import struct
import sys
from pathlib import Path

_SHOW_REQUESTED = "--show" in sys.argv

import matplotlib
if not _SHOW_REQUESTED:
    matplotlib.use("Agg")  # headless-safe default
import matplotlib.pyplot as plt

DEFAULT_SAMPLE_RATE = 44100
DEFAULT_MAX_SAMPLES = 2_000_000


def read_raw_samples(path: Path) -> list[int]:
    """Reads a .raw file as signed 16-bit little-endian PCM samples."""
    raw_bytes = path.read_bytes()
    if len(raw_bytes) % 2 != 0:
        print(
            f"Warning: {path} size ({len(raw_bytes)} bytes) is not a multiple of 2 -- "
            f"trailing byte will be ignored (possibly a truncated/corrupt file)",
            file=sys.stderr,
        )
        raw_bytes = raw_bytes[: len(raw_bytes) - (len(raw_bytes) % 2)]

    num_samples = len(raw_bytes) // 2
    if num_samples == 0:
        return []
    return list(struct.unpack(f"<{num_samples}h", raw_bytes))


def plot_waveform(samples: list[int], rate: int, title: str, output_path: Path) -> None:
    n = len(samples)
    time_axis = [i / rate for i in range(n)]

    fig = plt.figure(figsize=(14, 5))
    ax = fig.add_subplot(111)
    ax.plot(time_axis, samples, linewidth=0.4)
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude (signed 16-bit)")
    if time_axis:
        ax.set_xlim(0, time_axis[-1])
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    print(f"Saved plot: {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Plot the waveform of a Wellspring .raw archive file")
    parser.add_argument("raw_file", type=str, help="Path to the .raw file to plot")
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output PNG path (default: <input>.png)",
    )
    parser.add_argument(
        "--rate", type=int, default=DEFAULT_SAMPLE_RATE,
        help=f"Sample rate for the time axis (default: {DEFAULT_SAMPLE_RATE})",
    )
    parser.add_argument(
        "--max-samples", type=int, default=DEFAULT_MAX_SAMPLES,
        help=f"Cap on samples plotted, to avoid choking on huge files "
             f"(default: {DEFAULT_MAX_SAMPLES:,}). Use 0 for no cap.",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Also open an interactive matplotlib window (requires a display)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_path = Path(args.raw_file)

    if not raw_path.exists():
        print(f"Error: file not found: {raw_path}", file=sys.stderr)
        sys.exit(1)

    samples = read_raw_samples(raw_path)
    print(f"Read {len(samples):,} samples from {raw_path} ({raw_path.stat().st_size:,} bytes)")

    if not samples:
        print("Error: no samples to plot (empty or fully truncated file)", file=sys.stderr)
        sys.exit(1)

    if args.max_samples and len(samples) > args.max_samples:
        print(
            f"Truncating to first {args.max_samples:,} samples for plotting "
            f"(use --max-samples 0 to disable)",
            file=sys.stderr,
        )
        samples = samples[: args.max_samples]

    output_path = Path(args.output) if args.output else raw_path.parent / (raw_path.stem + ".png")
    title = f"Waveform: {raw_path.name} ({len(samples):,} samples)"
    plot_waveform(samples, args.rate, title, output_path)

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()