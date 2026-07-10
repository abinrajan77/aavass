"""Pure unit tests for `app.services.special_collection.compute_equal_split` — no DB, no
HTTP. Covers backend.md test plan items 2 and 3 at the algorithm level (the integration
tests in `tests/integration/test_special_collections.py` cover the same scenarios end to
end through the HTTP API with a `FakeFlatDirectory`)."""

from decimal import Decimal

from app.services.special_collection import compute_equal_split
from tests.factories import make_active_flat_record


def test_equal_split_sums_to_total_amount_exactly():
    flats = [make_active_flat_record(flat_number=str(100 + i)) for i in range(7)]
    allocations, skipped = compute_equal_split(Decimal("100000.00"), flats)

    assert skipped == []
    assert len(allocations) == 7
    assert sum(a.amount for a in allocations) == Decimal("100000.00")


def test_equal_split_remainder_goes_to_first_flats_by_flat_number_ascending():
    # 100000.00 -> 10,000,000 paise / 7 = 1,428,571 remainder 3 -> 3 flats get 1 extra paisa.
    flats = [make_active_flat_record(flat_number=str(107 - i)) for i in range(7)]  # unsorted
    allocations, skipped = compute_equal_split(Decimal("100000.00"), flats)

    assert skipped == []
    total_paise = 100000 * 100
    n = 7
    base_paise, remainder = divmod(total_paise, n)
    assert remainder == 3

    ordered = sorted(allocations, key=lambda a: int(a.flat_number))
    extra_paisa_flats = [a.flat_number for a in ordered[:remainder]]
    base_paisa_flats = [a.flat_number for a in ordered[remainder:]]

    assert extra_paisa_flats == ["101", "102", "103"]
    assert base_paisa_flats == ["104", "105", "106", "107"]
    for a in ordered[:remainder]:
        assert a.amount == (Decimal(base_paise + 1) / 100).quantize(Decimal("0.01"))
    for a in ordered[remainder:]:
        assert a.amount == (Decimal(base_paise) / 100).quantize(Decimal("0.01"))


def test_equal_split_is_deterministic_across_repeated_runs():
    flats = [make_active_flat_record(flat_number=str(100 + i)) for i in range(7)]
    first, _ = compute_equal_split(Decimal("100000.00"), flats)
    second, _ = compute_equal_split(Decimal("100000.00"), flats)

    first_by_flat = {a.flat_number: a.amount for a in first}
    second_by_flat = {a.flat_number: a.amount for a in second}
    assert first_by_flat == second_by_flat


def test_flat_with_no_active_owner_is_skipped_not_fatal():
    flats = [make_active_flat_record(flat_number=str(100 + i)) for i in range(9)]
    flats.append(make_active_flat_record(flat_number="110", no_active_owner=True))

    allocations, skipped = compute_equal_split(Decimal("90000.00"), flats)

    assert len(allocations) == 9
    assert len(skipped) == 1
    assert skipped[0].flat_number == "110"
    assert skipped[0].reason == "NO_ACTIVE_OWNER"
    assert sum(a.amount for a in allocations) == Decimal("90000.00")
    assert all(a.flat_number != "110" for a in allocations)


def test_all_flats_skipped_yields_no_allocations_and_no_crash():
    flats = [make_active_flat_record(flat_number="101", no_active_owner=True)]
    allocations, skipped = compute_equal_split(Decimal("1000.00"), flats)
    assert allocations == []
    assert len(skipped) == 1


def test_natural_sort_orders_numeric_flat_numbers_correctly():
    # Plain string sort would put "10" before "2" — natural sort must not. Use a total with a
    # remainder of exactly 1 so only the first flat (by correct ordering) gets the extra
    # paisa, making the ordering directly observable.
    flats = [
        make_active_flat_record(flat_number="10"),
        make_active_flat_record(flat_number="2"),
        make_active_flat_record(flat_number="1"),
    ]
    allocations, _ = compute_equal_split(Decimal("30.01"), flats)
    # 3001 paise / 3 = 1000 remainder 1 -> exactly one flat gets the extra paisa, and by
    # natural-sort ascending order that must be flat "1", not "10".
    max_amount = max(a.amount for a in allocations)
    flats_with_extra = [a.flat_number for a in allocations if a.amount == max_amount]
    assert flats_with_extra == ["1"]


def test_single_eligible_flat_gets_the_full_amount():
    flats = [make_active_flat_record(flat_number="101")]
    allocations, skipped = compute_equal_split(Decimal("500.50"), flats)
    assert skipped == []
    assert len(allocations) == 1
    assert allocations[0].amount == Decimal("500.50")


def test_due_generation_targets_owner_not_tenant():
    """backend.md test plan item 1, at the algorithm level: `ActiveFlatRecord` only ever
    carries an owner id (never a tenant id) by construction — the `FlatDirectory` seam is
    the single place tenant-vs-owner resolution happens, and this test locks in that the
    split algorithm faithfully propagates whatever owner it's given (as opposed to, say,
    silently falling back to some other identity)."""
    from uuid import uuid4

    owner_id = uuid4()
    tenant_id = uuid4()  # never passed in anywhere — must never leak onto the allocation
    flats = [make_active_flat_record(flat_number="101", owner_id=owner_id, owner_name="Jane Owner")]

    allocations, _ = compute_equal_split(Decimal("1000.00"), flats)
    assert allocations[0].owner_id == owner_id
    assert allocations[0].owner_id != tenant_id
    assert allocations[0].owner_name == "Jane Owner"
