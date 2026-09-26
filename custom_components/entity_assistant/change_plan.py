"""Change-plan data model for the Entity Assistant mutation spine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import CREATABLE_TYPES, OBJECT_TYPES, REMOVABLE_TYPES


@dataclass(slots=True, frozen=True)
class NewRef:
    temp_ref: str


@dataclass(slots=True)
class FieldChange:
    object_type: str
    key: str
    field: str
    from_: Any
    to: Any

    def __post_init__(self) -> None:
        if self.object_type not in OBJECT_TYPES:
            raise ValueError(f"unknown object_type {self.object_type!r}")


@dataclass(slots=True)
class ObjectCreate:
    object_type: str
    temp_ref: str
    fields: dict[str, Any]

    def __post_init__(self) -> None:
        if self.object_type not in CREATABLE_TYPES:
            raise ValueError(f"object_type {self.object_type!r} is not creatable")
        if "name" not in self.fields:
            raise ValueError("a create requires a 'name' field")


@dataclass(slots=True)
class ObjectRemove:
    object_type: str
    key: str
    label: str

    def __post_init__(self) -> None:
        if self.object_type not in REMOVABLE_TYPES:
            raise ValueError(f"object_type {self.object_type!r} is not removable")


def _json_safe(value: Any) -> Any:
    if isinstance(value, NewRef):
        return f"new:{value.temp_ref}"
    if isinstance(value, set):
        return sorted(str(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return value


def _create_to_dict(create: ObjectCreate) -> dict[str, Any]:
    return {
        "object_type": create.object_type,
        "temp_ref": create.temp_ref,
        "fields": {key: _json_safe(value) for key, value in create.fields.items()},
    }


def _update_to_dict(change: FieldChange) -> dict[str, Any]:
    return {
        "object_type": change.object_type,
        "key": change.key,
        "field": change.field,
        "from": _json_safe(change.from_),
        "to": _json_safe(change.to),
    }


def _remove_to_dict(remove: ObjectRemove) -> dict[str, Any]:
    return {
        "object_type": remove.object_type,
        "key": remove.key,
        "label": remove.label,
    }


@dataclass(slots=True)
class ChangePlan:
    producer: str
    creates: list[ObjectCreate] = field(default_factory=list)
    updates: list[FieldChange] = field(default_factory=list)
    removes: list[ObjectRemove] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.creates or self.updates or self.removes)

    def counts(self) -> dict[str, int]:
        return {
            "created": len(self.creates),
            "updated": len(self.updates),
            "removed": len(self.removes),
        }

    def object_types(self) -> list[str]:
        types = {create.object_type for create in self.creates}
        types |= {change.object_type for change in self.updates}
        types |= {remove.object_type for remove in self.removes}
        return sorted(types)

    def inverted(self) -> ChangePlan:
        return ChangePlan(
            producer=f"undo:{self.producer}",
            updates=[
                FieldChange(
                    change.object_type,
                    change.key,
                    change.field,
                    from_=change.to,
                    to=change.from_,
                )
                for change in reversed(self.updates)
            ],
        )

    def to_response(self, *, dry_run: bool, cap: int | None = None) -> dict[str, Any]:
        creates = self.creates if cap is None else self.creates[:cap]
        updates = self.updates if cap is None else self.updates[:cap]
        removes = self.removes if cap is None else self.removes[:cap]
        truncated = cap is not None and (
            len(self.creates) > cap or len(self.updates) > cap or len(self.removes) > cap
        )
        return {
            "dry_run": dry_run,
            "producer": self.producer,
            "counts": self.counts(),
            "object_types": self.object_types(),
            "creates": [_create_to_dict(create) for create in creates],
            "updates": [_update_to_dict(change) for change in updates],
            "removes": [_remove_to_dict(remove) for remove in removes],
            "truncated": truncated,
        }

    def to_file_payload(self) -> dict[str, Any]:
        return self.to_response(dry_run=True, cap=None)
