"""backend.md §8.1 — `calculate_monthly_maintenance` unit tests. Pure function, no DB/fixtures
needed (mirrors `tests/unit/test_security.py`'s style)."""

from decimal import Decimal

from app.services.billing_formula import calculate_monthly_maintenance


def test_base_only_formula():
    assert calculate_monthly_maintenance(
        Decimal("2000"), Decimal("0"), Decimal("850")
    ) == Decimal("2000.00")


def test_per_sqft_only_formula():
    assert calculate_monthly_maintenance(
        Decimal("0"), Decimal("2"), Decimal("850")
    ) == Decimal("1700.00")


def test_combined_base_and_per_sqft_formula():
    assert calculate_monthly_maintenance(
        Decimal("1000"), Decimal("1.5"), Decimal("600")
    ) == Decimal("1900.00")


def test_rounding_half_up_boundary():
    """`999.995` rounds half-up to `1000.00`, not down to `999.99` (banker's rounding would
    round to even and give the wrong answer here since 9 is odd)."""
    assert calculate_monthly_maintenance(
        Decimal("999.995"), Decimal("0"), Decimal("0")
    ) == Decimal("1000.00")


def test_both_components_zero_is_a_valid_zero_due():
    """overview.md edge case 6 — base=0, rate=0 must compute to exactly 0.00, not raise."""
    assert calculate_monthly_maintenance(
        Decimal("0"), Decimal("0"), Decimal("850")
    ) == Decimal("0.00")


def test_area_component_rounds_before_adding_base():
    """overview.md edge case 13 — the area component is rounded to the nearest paisa before
    being added to the base amount, not rounded only once at the very end."""
    # 733 * 1.005 = 736.665 -> rounds half-up to 736.67 before adding base.
    result = calculate_monthly_maintenance(Decimal("1000.00"), Decimal("1.005"), Decimal("733"))
    assert result == Decimal("1736.67")
