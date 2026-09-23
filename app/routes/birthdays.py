"""Birthday routes."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from ..models import Birthday, BirthdayCreate, BirthdayUpdate, User
from ..auth import get_current_active_user
from ..dates import month_day_error
from ..storage import birthday_storage

router = APIRouter(prefix="/api/birthdays", tags=["birthdays"])


@router.get("", response_model=List[Birthday])
async def get_birthdays(current_user: User = Depends(get_current_active_user)):
    """Get all birthdays."""
    return birthday_storage.get_all()


@router.get("/{birthday_id}", response_model=Birthday)
async def get_birthday(
    birthday_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get a specific birthday."""
    birthday = birthday_storage.get_by_id(birthday_id)
    if not birthday:
        raise HTTPException(status_code=404, detail="Birthday not found")
    return birthday


@router.post("", response_model=Birthday)
async def create_birthday(
    birthday_data: BirthdayCreate, current_user: User = Depends(get_current_active_user)
):
    """Create a new birthday."""
    birthday = Birthday(**birthday_data.model_dump())
    return birthday_storage.create(birthday)


@router.put("/{birthday_id}", response_model=Birthday)
async def update_birthday(
    birthday_id: str,
    birthday_data: BirthdayUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update a birthday."""
    existing = birthday_storage.get_by_id(birthday_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Birthday not found")

    # Update only provided fields
    update_dict = birthday_data.model_dump(exclude_unset=True)
    updated_birthday = existing.model_copy(update=update_dict)

    # model_copy(update=...) does not re-run validation, so a partial update that
    # changes only the day could still land on an impossible date -- setting
    # day=31 on an entry already in February, say. Check the merged pair.
    date_error = month_day_error(updated_birthday.month, updated_birthday.day)
    if date_error:
        raise HTTPException(status_code=422, detail=date_error)

    result = birthday_storage.update(birthday_id, updated_birthday)
    if not result:
        raise HTTPException(status_code=404, detail="Birthday not found")

    return result


@router.delete("/{birthday_id}")
async def delete_birthday(
    birthday_id: str, current_user: User = Depends(get_current_active_user)
):
    """Delete a birthday."""
    if not birthday_storage.delete(birthday_id):
        raise HTTPException(status_code=404, detail="Birthday not found")
    return {"message": "Birthday deleted"}
