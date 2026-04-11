from datetime import date, datetime

from forecast_issue_time import (
    estimate_runtime_issue_time,
    infer_issue_time_from_collection,
    infer_issue_time_from_filename,
)


def test_infer_issue_time_from_morning_collection():
    result = infer_issue_time_from_collection(
        forecast_date=date(2026, 4, 10),
        collection_time_local=datetime(2026, 4, 10, 4, 15, 30),
    )
    assert result.valid is True
    assert result.issue_cycle == "12Z"
    assert result.issue_time_local == datetime(2026, 4, 9, 20, 0)


def test_infer_issue_time_from_evening_collection():
    result = infer_issue_time_from_collection(
        forecast_date=date(2026, 4, 10),
        collection_time_local=datetime(2026, 4, 10, 16, 15, 30),
    )
    assert result.valid is True
    assert result.issue_cycle == "00Z"
    assert result.issue_time_local == datetime(2026, 4, 10, 8, 0)


def test_infer_issue_time_uses_tolerance_for_1804():
    result = infer_issue_time_from_filename("HZ_forecast_2026-04-10_20260410_180456.csv")
    assert result.valid is True
    assert result.issue_cycle == "00Z"
    assert result.used_tolerance is True


def test_infer_issue_time_rejects_1107_collection():
    result = infer_issue_time_from_filename("HZ_forecast_2026-02-15_20260215_110724.csv")
    assert result.valid is False
    assert result.issue_time_local is None


def test_estimate_runtime_issue_time_during_daytime_uses_previous_12z():
    result = estimate_runtime_issue_time(datetime(2026, 4, 11, 10, 0))
    assert result.valid is True
    assert result.issue_cycle == "12Z"
    assert result.issue_time_local == datetime(2026, 4, 10, 20, 0)


def test_estimate_runtime_issue_time_in_evening_uses_same_day_00z():
    result = estimate_runtime_issue_time(datetime(2026, 4, 11, 18, 0))
    assert result.valid is True
    assert result.issue_cycle == "00Z"
    assert result.issue_time_local == datetime(2026, 4, 11, 8, 0)
