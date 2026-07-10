"""Pydantic-level test for the owner contact-update schema — `specs/02-flat-owner-tenant/
backend.md` unit test plan: a payload containing `full_name` under `MANAGE_OWN_FLAT` scope
must be rejected by the schema itself (`extra="forbid"`), never merely ignored."""

import pytest
from pydantic import ValidationError

from app.schemas.owner import OwnerContactUpdate, OwnerFullUpdate


def test_owner_contact_update_rejects_full_name_extra_field():
    with pytest.raises(ValidationError) as exc_info:
        OwnerContactUpdate.model_validate(
            {"phone": "9998887777", "full_name": "Smuggled Name"}
        )
    errors = exc_info.value.errors()
    assert any(e["type"] == "extra_forbidden" for e in errors)


def test_owner_contact_update_accepts_phone_and_email():
    payload = OwnerContactUpdate.model_validate({"phone": "9998887777", "email": "a@b.com"})
    assert payload.phone == "9998887777"
    assert payload.email == "a@b.com"


def test_owner_full_update_accepts_full_name_and_id_number():
    payload = OwnerFullUpdate.model_validate({"full_name": "New Name", "id_number": "AB123"})
    assert payload.full_name == "New Name"
    assert payload.id_number == "AB123"
