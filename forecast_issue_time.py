"""Helpers for ECMWF issue-time estimation used by training and runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import os
import re
from typing import Optional


FILE_PATTERN = re.compile(
    r"(?P<prefix>[A-Z]+)_forecast_(?P<forecast_date>\d{4}-\d{2}-\d{2})_"
    r"(?P<stamp_date>\d{8})_(?P<stamp_time>\d{6})\.csv$"
)

MORNING_WINDOW_START = time(3, 30)
MORNING_WINDOW_END = time(5, 30)
EVENING_WINDOW_START = time(15, 30)
EVENING_WINDOW_END = time(17, 30)
WINDOW_TOLERANCE_MINUTES = 90


@dataclass(frozen=True)
class IssueTimeEstimate:
    valid: bool
    issue_time_local: Optional[datetime]
    issue_cycle: Optional[str]
    reason: str
    used_tolerance: bool = False

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "issue_time_local": self.issue_time_local.isoformat(sep=" ") if self.issue_time_local else None,
            "issue_cycle": self.issue_cycle,
            "reason": self.reason,
            "used_tolerance": self.used_tolerance,
        }


def _minutes_since_midnight(value: time) -> int:
    return value.hour * 60 + value.minute


def _distance_to_window_minutes(value: time, start: time, end: time) -> int:
    minutes = _minutes_since_midnight(value)
    start_minutes = _minutes_since_midnight(start)
    end_minutes = _minutes_since_midnight(end)
    if start_minutes <= minutes <= end_minutes:
        return 0
    return min(abs(minutes - start_minutes), abs(minutes - end_minutes))


def parse_forecast_filename(filename: str) -> Optional[dict]:
    """Parse a forecast collection filename like HZ_forecast_2026-04-10_20260410_180456.csv."""
    match = FILE_PATTERN.match(os.path.basename(filename))
    if not match:
        return None

    forecast_date = datetime.strptime(match.group("forecast_date"), "%Y-%m-%d").date()
    collection_dt = datetime.strptime(
        f"{match.group('stamp_date')}_{match.group('stamp_time')}",
        "%Y%m%d_%H%M%S",
    )
    return {
        "prefix": match.group("prefix"),
        "forecast_date": forecast_date,
        "collection_time_local": collection_dt,
    }


def infer_issue_time_from_collection(
    forecast_date: date,
    collection_time_local: datetime,
    tolerance_minutes: int = WINDOW_TOLERANCE_MINUTES,
) -> IssueTimeEstimate:
    """Infer ECMWF issue time from forecast-file collection timestamp."""
    collection_clock = collection_time_local.time()
    morning_distance = _distance_to_window_minutes(
        collection_clock,
        MORNING_WINDOW_START,
        MORNING_WINDOW_END,
    )
    evening_distance = _distance_to_window_minutes(
        collection_clock,
        EVENING_WINDOW_START,
        EVENING_WINDOW_END,
    )

    if morning_distance == 0 or (morning_distance <= tolerance_minutes and morning_distance <= evening_distance):
        used_tolerance = morning_distance > 0
        issue_time_local = datetime.combine(
            forecast_date - timedelta(days=1),
            time(20, 0),
        )
        reason = "mapped_to_12z"
        if used_tolerance:
            reason = "mapped_to_12z_with_tolerance"
        return IssueTimeEstimate(True, issue_time_local, "12Z", reason, used_tolerance)

    if evening_distance == 0 or evening_distance <= tolerance_minutes:
        used_tolerance = evening_distance > 0
        issue_time_local = datetime.combine(forecast_date, time(8, 0))
        reason = "mapped_to_00z"
        if used_tolerance:
            reason = "mapped_to_00z_with_tolerance"
        return IssueTimeEstimate(True, issue_time_local, "00Z", reason, used_tolerance)

    return IssueTimeEstimate(False, None, None, "outside_supported_windows", False)


def infer_issue_time_from_filename(filename: str) -> IssueTimeEstimate:
    parsed = parse_forecast_filename(filename)
    if not parsed:
        return IssueTimeEstimate(False, None, None, "filename_unrecognized", False)
    return infer_issue_time_from_collection(
        forecast_date=parsed["forecast_date"],
        collection_time_local=parsed["collection_time_local"],
    )


def estimate_runtime_issue_time(reference_local: Optional[datetime] = None) -> IssueTimeEstimate:
    """
    Estimate the latest ECMWF cycle available to the live forecast page.

    Rules:
    - >= 15:30 local: same-day 00Z cycle, local issue_time 08:00
    - 03:30-15:29 local: previous-day 12Z cycle, local issue_time 20:00
    - < 03:30 local: previous-day 00Z cycle, local issue_time 08:00
    """
    reference_local = reference_local or datetime.now()
    today = reference_local.date()
    clock = reference_local.time()

    if clock >= EVENING_WINDOW_START:
        return IssueTimeEstimate(
            True,
            datetime.combine(today, time(8, 0)),
            "00Z",
            "latest_runtime_cycle_00z",
            False,
        )

    if clock >= MORNING_WINDOW_START:
        return IssueTimeEstimate(
            True,
            datetime.combine(today - timedelta(days=1), time(20, 0)),
            "12Z",
            "latest_runtime_cycle_12z",
            False,
        )

    return IssueTimeEstimate(
        True,
        datetime.combine(today - timedelta(days=1), time(8, 0)),
        "00Z",
        "latest_runtime_cycle_prev_00z",
        False,
    )
