from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_plate(value: str) -> str:
    """Accept legible plate identifiers, including temporary and BH formats."""
    plate = re.sub(r"[ -]+", "", value.strip().upper())
    if not 4 <= len(plate) <= 16 or not plate.isascii() or not plate.isalnum():
        raise ValueError("Plate must be 4–16 ASCII letters/digits; spaces and hyphens are allowed")
    if not any(c.isalpha() for c in plate) or not any(c.isdigit() for c in plate):
        raise ValueError("Plate must contain letters and digits")
    return plate


class BayCreate(BaseModel):
    label: str = Field(min_length=2, max_length=12)

    @field_validator("label")
    @classmethod
    def valid_label(cls, value: str) -> str:
        label = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", label):
            raise ValueError("Bay label may contain letters, digits, and internal hyphens")
        return label


class AssignmentCreate(BaseModel):
    bay_id: int = Field(gt=0)
    unit: str = Field(min_length=1, max_length=24)
    plate: str

    @field_validator("unit")
    @classmethod
    def valid_unit(cls, value: str) -> str:
        unit = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9 /-]{0,23}", unit):
            raise ValueError("Unit may contain letters, digits, spaces, slash, and hyphen")
        return unit

    @field_validator("plate")
    @classmethod
    def valid_plate(cls, value: str) -> str:
        return clean_plate(value)


class MovementCreate(BaseModel):
    bay_id: int = Field(gt=0)
    kind: Literal["IN", "OUT"]
    occurred_at: datetime | None = None

    @field_validator("occurred_at")
    @classmethod
    def valid_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Timestamp must include a timezone offset")
        return value


class LoginRequest(BaseModel):
    username: str
    password: str
