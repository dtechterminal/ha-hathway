from datetime import date, datetime, timedelta, timezone

import pytest

from hathway_lib.cycle import cycle_for, projected_usage

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.mark.parametrize("today,start,next_reset", [
    (date(2026, 11, 12), date(2026, 10, 26), date(2026, 11, 26)),
    (date(2026, 10, 26), date(2026, 10, 26), date(2026, 11, 26)),  # reset day starts a cycle
    (date(2026, 10, 25), date(2026, 9, 26), date(2026, 10, 26)),
    (date(2026, 12, 31), date(2026, 12, 26), date(2027, 1, 26)),   # year rollover
    (date(2027, 1, 3), date(2026, 12, 26), date(2027, 1, 26)),
])
def test_cycle_on_26th(today, start, next_reset):
    cycle = cycle_for(today, 26)
    assert (cycle.start, cycle.next_reset) == (start, next_reset)


def test_real_history_matches():
    # Hathway's counter dropped to 0 on these dates (HA history, 2026).
    for reset in ["2026-06-26", "2026-07-26", "2026-08-26", "2026-09-26", "2026-10-26"]:
        d = date.fromisoformat(reset)
        assert cycle_for(d, 26).start == d
        assert cycle_for(d - timedelta(days=1), 26).next_reset == d


def test_counts_today():
    cycle = cycle_for(date(2026, 11, 12), 26)
    assert cycle.length_days == 31
    assert cycle.days_elapsed(date(2026, 11, 12)) == 17
    assert cycle.days_until_reset(date(2026, 11, 12)) == 14


def test_short_month_clamps():
    assert cycle_for(date(2027, 2, 28), 31).start == date(2027, 2, 28)
    assert cycle_for(date(2027, 3, 5), 31).start == date(2027, 2, 28)
    assert cycle_for(date(2027, 3, 5), 31).next_reset == date(2027, 3, 31)
    assert cycle_for(date(2028, 2, 29), 30).start == date(2028, 2, 29)  # leap year
    assert cycle_for(date(2026, 4, 30), 31).start == date(2026, 4, 30)


def test_reset_day_1():
    cycle = cycle_for(date(2026, 11, 1), 1)
    assert (cycle.start, cycle.next_reset) == (date(2026, 11, 1), date(2026, 12, 1))


def test_invalid_day():
    with pytest.raises(ValueError):
        cycle_for(date(2026, 1, 1), 0)


def test_projection():
    cycle = cycle_for(date(2026, 11, 12), 26)
    now = datetime(2026, 11, 12, 12, 0, tzinfo=IST)  # 17.5 days in
    assert projected_usage(1750, cycle, now) == pytest.approx(1750 / 17.5 * 31)


def test_projection_waits_a_day():
    cycle = cycle_for(date(2026, 10, 26), 26)
    # On the reset day the counter may still show last cycle's total.
    assert projected_usage(2_700_000, cycle, datetime(2026, 10, 26, 20, 0, tzinfo=IST)) is None
    assert projected_usage(100, cycle, datetime(2026, 10, 27, 1, 0, tzinfo=IST)) is not None
