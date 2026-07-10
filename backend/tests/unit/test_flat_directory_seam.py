"""Unit test for the Module 2 integration seam (`app/services/flat_directory.py`) — locks
in that the production placeholder fails loudly instead of silently fabricating flat data,
per the scope note in `specs/04-special-collections-expenditure/backend.md`."""

from uuid import uuid4

import pytest

from app.core.errors import AppError
from app.services.flat_directory import Module2NotIntegratedFlatDirectory


@pytest.mark.asyncio
async def test_module2_not_integrated_flat_directory_raises_clear_error():
    directory = Module2NotIntegratedFlatDirectory()
    with pytest.raises(AppError) as exc_info:
        await directory.list_active_flats(tower_id=uuid4())
    assert exc_info.value.error_code == "FLAT_DIRECTORY_NOT_AVAILABLE"
    assert exc_info.value.status_code == 501
