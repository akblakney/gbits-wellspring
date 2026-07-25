"""
Usage:
    python run_sts_report.py data.bin
    python run_sts_report.py data.bin --results-dir /my/dir
    python run_sts_report.py data.bin --sts-bin /path/to/sts

Runs:
    sts -s -i <bitstreams> -w <results_dir> -F r data.bin
with the maximum possible number of bitstreams

Note: this script is a wrapper around the existing improved sts
test suite: https://github.com/arcetri/sts
"""

import argparse
import math
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from scipy.stats import binom

DEFAULT_BITSTREAM_BITS = 1_048_576  # sts default value
SIGNIFICANCE_LEVEL = 0.01           # sts default
UNUSUAL_Z_THRESHOLD = 3.0           # z-score for unusual flag


@dataclass
class TestResult:
    name: str
    success_count: int
    fail_count: int

    @property
    def total(self) -> int:
        return self.success_count + self.fail_count

    @property
    def fail_rate(self) -> float:
        return self.fail_count / self.total if self.total else 0.0

    @property
    def p_value(self) -> float:
        return binom.sf(self.fail_count - 1, self.total, SIGNIFICANCE_LEVEL)

    def is_unusual(self, p: float = SIGNIFICANCE_LEVEL, z_threshold: float = UNUSUAL_Z_THRESHOLD) -> bool:
        if self.total == 0:
            return False
        expected = self.total * p
        std_dev = math.sqrt(self.total * p * (1 - p))
        if std_dev == 0:
            return self.fail_count > expected
        z = (self.fail_count - expected) / std_dev
        return z > z_threshold


def compute_max_bitstreams(input_path: Path, bitstream_bits: int) -> int:
    file_size_bits = input_path.stat().st_size * 8
    num_bitstreams = file_size_bits // bitstream_bits
    return num_bitstreams


def run_sts(sts_bin: str, results_dir: Path, num_bitstreams: int, input_path: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sts_bin, "-s", "-i", str(num_bitstreams), "-w", str(results_dir), "-F", "r", str(input_path)]
    print(f"Running: {' '.join(cmd)}", file=sys.stderr)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("sts exited with a non-zero status. stdout/stderr follow:", file=sys.stderr)
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        sys.exit(1)


def parse_overall_summary(results_dir: Path) -> list[str]:
    results_txt = results_dir / "result.txt"
    if not results_txt.exists():
        print(f"Warning: expected {results_txt} not found -- sts output layout may differ from what this "
              f"script assumes. Check {results_dir} manually.", file=sys.stderr)
        return []

    lines = []
    with open(results_txt, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.rstrip("\n")
            if "passed" in stripped.lower() or "fail" in stripped.lower():
                lines.append(stripped)
    return lines


def discover_test_results(results_dir: Path) -> list[TestResult]:
    results = []
    for stats_path in sorted(results_dir.glob("*/stats.txt")):
        test_name = stats_path.parent.name
        success_count = 0
        fail_count = 0
        with open(stats_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                lower = line.lower()
                if "success" in lower:
                    success_count += 1
                elif "fail" in lower:
                    fail_count += 1
        results.append(TestResult(name=test_name, success_count=success_count, fail_count=fail_count))
    return results


def build_report(
    input_path: Path,
    results_dir: Path,
    num_bitstreams: int,
    overall_lines: list[str],
    test_results: list[TestResult],
) -> str:
    out = []
    out.append("=" * 70)
    out.append("improved STS randomness test summary")
    out.append("=" * 70)
    out.append(f"Input file:       {input_path}")
    out.append(f"Input size:       {input_path.stat().st_size:,} bytes")
    out.append(f"Bitstream length: {DEFAULT_BITSTREAM_BITS:,} bits (sts default)")
    out.append(f"Bitstreams run:   {num_bitstreams:,}")
    out.append(f"Results dir:      {results_dir}")
    out.append("")

    out.append("-" * 70)
    out.append("Overall summary (from result.txt)")
    out.append("-" * 70)
    if overall_lines:
        out.extend(overall_lines)
    else:
        out.append("(no summary lines found -- see warning above)")
    out.append("")

    out.append("-" * 70)
    out.append(f"Per-test breakdown ({len(test_results)} test(s) found)")
    out.append("-" * 70)
    if not test_results:
        out.append("(no test directories with stats.txt found)")
    else:
        header = f"{'Test':<32} {'Success':>8} {'Fail':>6} {'Total':>6} {'Fail %':>8} {'p-value':>8} Flag"
        out.append(header)
        out.append("-" * len(header))
        for t in test_results:
            flag = "<-- UNUSUAL" if t.is_unusual() else ""
            out.append(
                f"{t.name:<32} {t.success_count:>8} {t.fail_count:>6} {t.total:>6} "
                f"{t.fail_rate * 100:>7.2f}% {t.p_value:>7.6f} {flag}"
            )

    out.append("")
    out.append(f"Note: expected fail rate is ~{SIGNIFICANCE_LEVEL * 100:.0f}% per test."
               f"'UNUSUAL' flags tests whose fail count "
               f"is more than {UNUSUAL_Z_THRESHOLD} standard deviations above that expectation.")
    out.append(f"p-value gives the probability of seeing at LEAST as many failures for each test"
               f"under the assumption of random data.")
    out.append("=" * 70)
    return "\n".join(out)


def parse_args():
    parser = argparse.ArgumentParser(description="Run sts against a data file and summarize results")
    parser.add_argument("input", type=str, help="Path to the data file to test (e.g. output of export_archive.py)")
    parser.add_argument("--results-dir", type=str, default=None,
                         help="Directory for sts's full output. Defaults to a new temp dir under /tmp "
                              "(not auto-deleted -- inspect it later if a report looks suspicious).")
    parser.add_argument("--sts-bin", type=str, default="sts", help="Path to the sts binary (default: 'sts' on PATH)")
    parser.add_argument("--bitstream-bits", type=int, default=DEFAULT_BITSTREAM_BITS,
                         help=f"Bitstream length in bits (default: {DEFAULT_BITSTREAM_BITS}, sts's own default)")
    parser.add_argument("--report-out", type=str, default=None,
                         help="Also write the report to this file (in addition to stdout and results_dir)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    num_bitstreams = compute_max_bitstreams(input_path, args.bitstream_bits)
    if num_bitstreams < 1:
        print(f"Error: input file is too small to produce even one {args.bitstream_bits}-bit bitstream",
              file=sys.stderr)
        sys.exit(1)

    if args.results_dir:
        results_dir = Path(args.results_dir)
    else:
        results_dir = Path(tempfile.mkdtemp(prefix="sts_results_"))

    run_sts(args.sts_bin, results_dir, num_bitstreams, input_path)

    overall_lines = parse_overall_summary(results_dir)
    test_results = discover_test_results(results_dir)

    report = build_report(input_path, results_dir, num_bitstreams, overall_lines, test_results)

    print(report)

    # Always drop a copy of the report inside the results dir itself, so
    # the report and the raw data it summarizes stay together.
    (results_dir / "summary_report.txt").write_text(report, encoding="utf-8")

    if args.report_out:
        Path(args.report_out).write_text(report, encoding="utf-8")
        print(f"\nReport also written to {args.report_out}", file=sys.stderr)


if __name__ == "__main__":
    main()