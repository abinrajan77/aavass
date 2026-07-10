"""backend.md §8.1 / §3 — `is_overdue` unit tests (day-granularity boundary conditions,
overview.md edge case 2). Pure function, no DB needed."""

from datetime import date

from app.services.overdue import is_overdue


def test_still_within_grace_period_is_not_overdue():
    assert is_overdue(date(2026, 7, 10), 5, date(2026, 7, 15)) is False


def test_one_day_past_grace_period_is_overdue():
    assert is_overdue(date(2026, 7, 10), 5, date(2026, 7, 16)) is True


def test_zero_grace_period_on_due_date_itself_is_not_overdue():
    assert is_overdue(date(2026, 7, 10), 0, date(2026, 7, 10)) is False


def test_zero_grace_period_the_day_after_due_date_is_overdue():
    """overview.md edge case 2 — a grace period of 0 means Overdue the day *after* the due
    date, not on the due date itself."""
    assert is_overdue(date(2026, 7, 10), 0, date(2026, 7, 11)) is True


def test_exact_grace_boundary_is_not_yet_overdue():
    """`as_of == due_date + grace_period_days` must not be overdue — only strictly after."""
    assert is_overdue(date(2026, 7, 10), 5, date(2026, 7, 15)) is False
    assert is_overdue(date(2026, 7, 10), 5, date(2026, 7, 16)) is True
