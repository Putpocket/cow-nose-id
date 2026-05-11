from __future__ import annotations

from dataclasses import dataclass


class ValidationError(ValueError):
    """Raised when request payload has invalid or missing fields."""


@dataclass(frozen=True)
class CowCreate:
    owner_id: int
    name: str

    @classmethod
    def from_payload(cls, payload: dict) -> "CowCreate":
        owner_id = payload.get("owner_id")
        name = (payload.get("name") or "").strip()

        if not isinstance(owner_id, int) or owner_id <= 0:
            raise ValidationError("owner_id must be a positive integer")
        if not name:
            raise ValidationError("name is required")
        if len(name) > 80:
            raise ValidationError("name is too long (max 80 chars)")

        return cls(owner_id=owner_id, name=name)


@dataclass(frozen=True)
class CowUpdate:
    owner_id: int
    name: str

    @classmethod
    def from_payload(cls, payload: dict) -> "CowUpdate":
        # same rules as create for now
        return cls(**CowCreate.from_payload(payload).__dict__)
