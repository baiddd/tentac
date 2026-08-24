"""ISO-week arithmetic, UTC throughout. Every pipeline stage uses this."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def week_bounds(week: str) -> tuple[datetime, datetime]:
    """Half-open UTC interval [monday 00:00, next monday 00:00) for an ISO week."""
    match = _WEEK_RE.match(week)
    if not match:
        raise ValueError(f"expected ISO week like '2026-W34', got {week!r}")
    year, week_num = int(match.group(1)), int(match.group(2))
    monday = datetime.fromisocalendar(year, week_num, 1).replace(tzinfo=timezone.utc)
    return monday, monday + timedelta(days=7)


def current_week() -> str:
    """ISO week string of the last complete week as of now (UTC)."""
    now = datetime.now(timezone.utc)
    last_complete_monday = now - timedelta(days=now.isoweekday())
    iso = last_complete_monday.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"
