"""
DailyStatsService — aggregates a completed day's hourly test results into
per-test lists of p-values (or, for a small allow-list of tests, a single
representative statistic used in lieu of a p-value).

Relies entirely on StatsService.get_summary_for_hour() for the actual
per-hour compute-or-cache work -- each hour is already cached
independently (immutable once written), so aggregating a full day is
just: read/compute 24 small per-hour results, then walk each one and
pull out the fields listed in EXTRACTION_RULES below.

EXTRACTION_RULES is deliberately explicit rather than "auto-detect
anything with a p_value key" or similar heuristics -- as your test
suite grows, you add a line here to opt a new test in, rather than the
service silently guessing whether a new field is meaningful to surface.
Tests not listed here (e.g. longest_run, serial_correlation -- fields
with only an "expected" value to eyeball, no clean pass/fail number)
are simply skipped.

Each entry maps a dotted path into an hour's "tests" dict to how to
summarize it:
    "p_value"   -> pull the "p_value" field, label as p-values
    "statistic" -> pull an explicitly named field, label as that
                   field's name (so the output makes clear it's NOT
                   a p-value)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from service.stats_service import StatsService, NoArchivedDataError
from repository.stats_repository import StatsRepository

logger = logging.getLogger(__name__)


EXTRACTION_RULES: dict[str, dict[str, str]] = {
    "byte_level.chi_square":            {"type": "p_value", "field": "p_value"},
    "byte_level.byte_pair_chi_square":  {"type": "p_value", "field": "p_value"},
    "byte_level.entropy":               {"type": "statistic", "field": "delta"},
    "bit_level.monobit":                {"type": "p_value", "field": "p_value"},
    "bit_level.runs":                   {"type": "p_value", "field": "p_value"},
    "bit_level.block_frequency":        {"type": "p_value", "field": "p_value"},
    # Deliberately excluded (no p_value, no single clean pass/fail number):
    #   byte_level.mean_std          -- mean/std vs expected, not a p-value
    #   byte_level.serial_correlation -- "should be close to 0", no expected field
    #   byte_level.longest_run       -- observed vs expected only
    #   bit_level.longest_run        -- observed vs expected only
}


class DailyStatsService:
    def __init__(self, stats_service: StatsService, stats_repository: StatsRepository):
        self._stats_service = stats_service
        self._stats_repository = stats_repository

    def get_latest_completed_day_summary(self) -> dict[str, Any]:
        day_start = self._latest_completed_day_start()

        included_hours: list[str] = []
        missing_hours: list[str] = []
        bytes_per_hour: dict[str, int] = {}

        # test_path -> list of extracted values, in hour order
        collected: dict[str, list[float]] = {path: [] for path in EXTRACTION_RULES}

        for hour_offset in range(24):
            hour_start = day_start + timedelta(hours=hour_offset)
            hour_label = hour_start.strftime("%H")

            bin_path = self._stats_repository.bin_path_for_hour(hour_start)
            if not bin_path.exists():
                missing_hours.append(hour_label)
                continue

            try:
                hour_summary = self._stats_service.get_summary_for_hour(hour_start)
            except NoArchivedDataError:
                # .bin existed but was empty, or similar edge case --
                # treat the same as missing rather than failing the
                # whole day's aggregation.
                missing_hours.append(hour_label)
                continue

            included_hours.append(hour_label)
            bytes_per_hour[hour_label] = hour_summary.get("num_bytes_tested", 0)
            self._extract_into(hour_summary.get("tests", {}), collected)

        return {
            "day_utc": day_start.strftime("%Y-%m-%d"),
            "hours_included": included_hours,
            "hours_missing": missing_hours,
            "total_bytes": sum(bytes_per_hour.values()),
            "bytes_per_hour": bytes_per_hour,
            "tests": {
                path: {
                    "metric": rule["field"] if rule["type"] == "statistic" else "p_value",
                    "values": collected[path],
                }
                for path, rule in EXTRACTION_RULES.items()
            },
        }

    @staticmethod
    def _extract_into(tests: dict[str, Any], collected: dict[str, list[float]]) -> None:
        for path, rule in EXTRACTION_RULES.items():
            node = tests
            for part in path.split("."):
                if not isinstance(node, dict) or part not in node:
                    node = None
                    break
                node = node[part]

            if not isinstance(node, dict):
                continue  # this hour's results don't have this test at all

            value = node.get(rule["field"])
            if value is not None:
                collected[path].append(value)

    @staticmethod
    def _latest_completed_day_start() -> datetime:
        """The most recently fully-elapsed calendar day, UTC (i.e. yesterday)."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today_start - timedelta(days=1)