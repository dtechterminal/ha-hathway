"""Billing-cycle arithmetic for a quota that resets on a fixed day of the month.

Pure functions with no Home Assistant imports, so they are unit-tested directly.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time


def _reset_date(year: int, month: int, reset_day: int) -> date:
    """The reset date in a month, clamped for short months (day 31 -> 30 Apr, 28/29 Feb)."""
    return date(year, month, min(reset_day, calendar.monthrange(year, month)[1]))


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


@dataclass(frozen=True)
class Cycle:
    start: date
    next_reset: date

    @property
    def length_days(self) -> int:
        return (self.next_reset - self.start).days

    def days_elapsed(self, today: date) -> int:
        """Whole days since the cycle started; 0 on the reset day itself."""
        return (today - self.start).days

    def days_until_reset(self, today: date) -> int:
        return (self.next_reset - today).days

    def elapsed_fraction_days(self, now: datetime) -> float:
        """Elapsed time in days, counting from local midnight of the reset day."""
        start = datetime.combine(self.start, time.min, tzinfo=now.tzinfo)
        return max((now - start).total_seconds() / 86400, 0.0)


def cycle_for(today: date, reset_day: int) -> Cycle:
    """Return the billing cycle containing ``today``.

    The cycle starts on the reset day (inclusive) and ends the day before the
    next reset day. With reset_day=26: 26 Oct .. 25 Nov, next reset 26 Nov.
    """
    if not 1 <= reset_day <= 31:
        raise ValueError("reset_day must be between 1 and 31")
    this_month = _reset_date(today.year, today.month, reset_day)
    if today >= this_month:
        start = this_month
        year, month = _shift_month(today.year, today.month, 1)
    else:
        year, month = _shift_month(today.year, today.month, -1)
        start = _reset_date(year, month, reset_day)
        year, month = today.year, today.month
    return Cycle(start=start, next_reset=_reset_date(year, month, reset_day))


def projected_usage(used: float, cycle: Cycle, now: datetime,
                    min_elapsed_days: float = 1.0) -> float | None:
    """Linear projection of usage at the end of the cycle.

    Returns None until ``min_elapsed_days`` have passed: on the reset day the
    ISP counter may still hold the previous cycle's total (Hathway has reset
    as late as 18:00), and a few hours of data extrapolate wildly.
    """
    elapsed = cycle.elapsed_fraction_days(now)
    if elapsed < min_elapsed_days:
        return None
    return used / elapsed * cycle.length_days
