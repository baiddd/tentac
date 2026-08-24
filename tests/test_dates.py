from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from dates import week_bounds, current_week


def test_week_bounds_mid_year():
    start, end = week_bounds("2026-W34")
    assert start == datetime(2026, 8, 17, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 24, tzinfo=timezone.utc)


def test_week_bounds_year_boundary():
    start, end = week_bounds("2026-W01")
    assert start == datetime(2025, 12, 29, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 5, tzinfo=timezone.utc)


def test_week_bounds_rejects_bad_format():
    with pytest.raises(ValueError):
        week_bounds("2026-34")


@freeze_time("2026-08-24 10:00:00")  # a Monday
def test_current_week_on_monday_returns_prior_week():
    # Monday 06:00 UTC cron covers the week that just closed.
    assert current_week() == "2026-W34"


@freeze_time("2026-08-20 10:00:00")  # a Thursday, mid-week
def test_current_week_midweek_returns_prior_complete_week():
    assert current_week() == "2026-W33"
