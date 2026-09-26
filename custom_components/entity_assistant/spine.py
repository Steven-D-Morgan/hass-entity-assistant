"""Mutation spine for Entity Assistant: compile -> preview -> commit."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.core import Context, HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
import voluptuous as vol

from .change_plan import ChangePlan, FieldChange, NewRef, ObjectCreate, ObjectRemove
from .const import (
    ATTR_CONFIRM,
    ATTR_DRY_RUN,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_ROWS,
    EVENT_CHANGES_APPLIED,
    EVENT_ORPHANED_REMOVED,
    OBJECT_AREA,
    OBJECT_DEVICE,
    OBJECT_ENTITY,
    OBJECT_FLOOR,
    OBJECT_LABEL,
)
from .export import scan_orphaned

_LOGGER = logging.getLogger(__name__)

MUTATION_FIELDS = {
    vol.Optional(ATTR_DRY_RUN, default=True): cv.boolean,
    vol.Optional(ATTR_CONFIRM, default=False): cv.boolean,
}

_CREATE_ORDER = {OBJECT_LABEL: 0, OBJECT_FLOOR: 1, OBJECT_AREA: 2}
_REMOVE_ORDER = {OBJECT_ENTITY: 0, OBJECT_DEVICE: 1, OBJECT_AREA: 2}


async def async_require_admin(hass: HomeAssistant, context: Context) -> None:
    if context.user_id is None:
        return
    user = await hass.auth.async_get_user(context.user_id)
    if user is None or not user.is_admin:
        raise Unauthorized(context=context)


@dataclass(slots=True)
class CommitResult:
    producer: str
    created_ids: list[str] = field(default_factory=list)
    updated_keys: list[str] = field(default_factory=list)
    removed_keys: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    journal_id: str | None = None

    def counts(self) -> dict[str, int]:
        return {
            "created": len(self.created_ids),
            "updated": len(self.updated_keys),
            "removed": len(self.removed_keys),
            "failed": len(self.errors),
        }

    def to_response(self, *, cap: int = DEFAULT_MAX_ROWS) -> dict[str, Any]:
        return {
            "dry_run": False,
            "producer": self.producer,
            "counts": self.counts(),
            "created_ids": self.created_ids[:cap],
            "updated_keys": self.updated_keys[:cap],
            "removed_keys": self.removed_keys[:cap],
            "errors": self.errors[:cap],
            "journal_id": self.journal_id,
        }


def _resolve(value: Any, ref_map: dict[str, str]) -> Any:
    if isinstance(value, NewRef):
        return ref_map[value.temp_ref]
    return value


def _error(
    index: int,
    object_type: str,
    key: str,
    field_name: str | None,
    err: Exception,
) -> dict[str, Any]:
    return {
        "index": index,
        "object_type": object_type,
        "key": key,
        "field": field_name,
        "error": str(err),
        "error_type": type(err).__name__,
    }


def _apply_create(hass: HomeAssistant, create: ObjectCreate, ref_map: dict[str, str]) -> str:
    fields = {key: _resolve(value, ref_map) for key, value in create.fields.items()}
    name = fields.pop("name")
    real_id: str
    if create.object_type == OBJECT_AREA:
        real_id = ar.async_get(hass).async_create(name, **fields).id
    elif create.object_type == OBJECT_FLOOR:
        real_id = fr.async_get(hass).async_create(name, **fields).floor_id
    elif create.object_type == OBJECT_LABEL:
        real_id = lr.async_get(hass).async_create(name, **fields).label_id
    else:
        raise ValueError(f"cannot create object_type {create.object_type!r}")
    return real_id


def _apply_update(hass: HomeAssistant, change: FieldChange, ref_map: dict[str, str]) -> Any:
    value = _resolve(change.to, ref_map)
    if change.object_type == OBJECT_ENTITY:
        ent_reg = er.async_get(hass)
        entry = ent_reg.entities.get_entry(change.key)
        if entry is None:
            raise KeyError(f"entity registry id {change.key!r} not found")
        before = getattr(entry, change.field)
        ent_reg.async_update_entity(entry.entity_id, **{change.field: value})
        return before
    if change.object_type == OBJECT_DEVICE:
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(change.key)
        if device is None:
            raise KeyError(f"device id {change.key!r} not found")
        before = getattr(device, change.field)
        dev_reg.async_update_device(change.key, **{change.field: value})
        return before
    if change.object_type == OBJECT_AREA:
        area_reg = ar.async_get(hass)
        area = area_reg.async_get_area(change.key)
        if area is None:
            raise KeyError(f"area id {change.key!r} not found")
        before = getattr(area, change.field)
        area_reg.async_update(change.key, **{change.field: value})
        return before
    if change.object_type == OBJECT_FLOOR:
        floor_reg = fr.async_get(hass)
        floor = floor_reg.async_get_floor(change.key)
        if floor is None:
            raise KeyError(f"floor id {change.key!r} not found")
        before = getattr(floor, change.field)
        floor_reg.async_update(change.key, **{change.field: value})
        return before
    if change.object_type == OBJECT_LABEL:
        label_reg = lr.async_get(hass)
        label = label_reg.async_get_label(change.key)
        if label is None:
            raise KeyError(f"label id {change.key!r} not found")
        before = getattr(label, change.field)
        label_reg.async_update(change.key, **{change.field: value})
        return before
    raise ValueError(f"cannot update object_type {change.object_type!r}")


def _apply_remove(hass: HomeAssistant, remove: ObjectRemove) -> None:
    if remove.object_type == OBJECT_ENTITY:
        er.async_get(hass).async_remove(remove.key)
        return
    if remove.object_type == OBJECT_DEVICE:
        dr.async_get(hass).async_remove_device(remove.key)
        return
    if remove.object_type == OBJECT_AREA:
        ar.async_get(hass).async_delete(remove.key)
        return
    raise ValueError(f"cannot remove object_type {remove.object_type!r}")


async def _maybe_yield(processed: int, chunk_size: int) -> int:
    processed += 1
    if chunk_size > 0 and processed % chunk_size == 0:
        await asyncio.sleep(0)
    return processed


async def async_run_pre_commit_hooks(
    hass: HomeAssistant, plan: ChangePlan, context: Context | None
) -> None:
    return


async def async_record_journal(
    hass: HomeAssistant,
    producer: str,
    journal_batch: list[dict[str, Any]],
    context: Context | None,
) -> str | None:
    return None


async def async_commit_plan(
    hass: HomeAssistant,
    plan: ChangePlan,
    *,
    triggered_by: str,
    context: Context | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> CommitResult:
    result = CommitResult(producer=plan.producer)
    ref_map: dict[str, str] = {}
    journal_batch: list[dict[str, Any]] = []
    processed = 0

    await async_run_pre_commit_hooks(hass, plan, context)

    for create in sorted(plan.creates, key=lambda item: _CREATE_ORDER.get(item.object_type, 99)):
        try:
            real_id = _apply_create(hass, create, ref_map)
            ref_map[create.temp_ref] = real_id
            result.created_ids.append(real_id)
        except Exception as err:
            result.errors.append(_error(processed, create.object_type, create.temp_ref, None, err))
        processed = await _maybe_yield(processed, chunk_size)

    for change in plan.updates:
        try:
            before = _apply_update(hass, change, ref_map)
            result.updated_keys.append(change.key)
            journal_batch.append(
                {
                    "object_type": change.object_type,
                    "key": change.key,
                    "field": change.field,
                    "from": before,
                    "to": _resolve(change.to, ref_map),
                }
            )
        except Exception as err:
            result.errors.append(
                _error(processed, change.object_type, change.key, change.field, err)
            )
        processed = await _maybe_yield(processed, chunk_size)

    for remove in sorted(plan.removes, key=lambda item: _REMOVE_ORDER.get(item.object_type, 99)):
        try:
            _apply_remove(hass, remove)
            result.removed_keys.append(remove.key)
        except Exception as err:
            result.errors.append(_error(processed, remove.object_type, remove.key, None, err))
        processed = await _maybe_yield(processed, chunk_size)

    result.journal_id = await async_record_journal(hass, plan.producer, journal_batch, context)

    if result.errors:
        _LOGGER.warning(
            "Change plan %r applied with %d error(s)", plan.producer, len(result.errors)
        )

    hass.bus.async_fire(
        EVENT_CHANGES_APPLIED,
        {
            "producer": plan.producer,
            "triggered_by": triggered_by,
            "counts": result.counts(),
            "object_types": plan.object_types(),
            "created_ids": result.created_ids[:DEFAULT_MAX_ROWS],
            "updated_keys": result.updated_keys[:DEFAULT_MAX_ROWS],
            "removed_keys": result.removed_keys[:DEFAULT_MAX_ROWS],
            "errors": result.errors[:DEFAULT_MAX_ROWS],
            "journal_id": result.journal_id,
        },
    )
    return result


async def async_handle_mutation(
    hass: HomeAssistant,
    call: ServiceCall,
    compile_fn: Callable[[HomeAssistant, ServiceCall], ChangePlan],
    *,
    cap: int = DEFAULT_MAX_ROWS,
) -> ServiceResponse:
    await async_require_admin(hass, call.context)
    plan = compile_fn(hass, call)
    if not call.data[ATTR_CONFIRM]:
        return plan.to_response(dry_run=True, cap=cap)
    result = await async_commit_plan(hass, plan, triggered_by="service", context=call.context)
    return result.to_response(cap=cap)


def _device_label(hass: HomeAssistant, device_id: str) -> str:
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return device_id
    return device.name_by_user or device.name or device_id


def _area_label(hass: HomeAssistant, area_id: str) -> str:
    area = ar.async_get(hass).async_get_area(area_id)
    if area is None:
        return area_id
    return area.name or area_id


def compile_remove_orphaned(hass: HomeAssistant) -> ChangePlan:
    entity_ids, device_ids, area_ids = scan_orphaned(hass)
    removes: list[ObjectRemove] = [
        ObjectRemove(OBJECT_ENTITY, key=entity_id, label=entity_id) for entity_id in entity_ids
    ]
    removes += [
        ObjectRemove(OBJECT_DEVICE, key=device_id, label=_device_label(hass, device_id))
        for device_id in device_ids
    ]
    removes += [
        ObjectRemove(OBJECT_AREA, key=area_id, label=_area_label(hass, area_id))
        for area_id in area_ids
    ]
    return ChangePlan(producer="remove_orphaned", removes=removes)


def _remove_ids(plan: ChangePlan, result: CommitResult | None, object_type: str) -> list[str]:
    if result is None:
        return [remove.key for remove in plan.removes if remove.object_type == object_type]
    removed = set(result.removed_keys)
    return [
        remove.key
        for remove in plan.removes
        if remove.object_type == object_type and remove.key in removed
    ]


def remove_orphaned_response(
    plan: ChangePlan,
    result: CommitResult | None,
    *,
    dry_run: bool,
    triggered_by: str,
) -> dict[str, Any]:
    entity_ids = _remove_ids(plan, result, OBJECT_ENTITY)
    device_ids = _remove_ids(plan, result, OBJECT_DEVICE)
    area_ids = _remove_ids(plan, result, OBJECT_AREA)
    return {
        "dry_run": dry_run,
        "entities_removed": len(entity_ids),
        "devices_removed": len(device_ids),
        "areas_removed": len(area_ids),
        "entity_ids": entity_ids,
        "device_ids": device_ids,
        "area_ids": area_ids,
        "triggered_by": triggered_by,
    }


async def async_handle_remove_orphaned(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    await async_require_admin(hass, call.context)
    plan = compile_remove_orphaned(hass)
    if not call.data[ATTR_CONFIRM]:
        return remove_orphaned_response(plan, None, dry_run=True, triggered_by="service")
    result = await async_commit_plan(hass, plan, triggered_by="service", context=call.context)
    response = remove_orphaned_response(plan, result, dry_run=False, triggered_by="service")
    hass.bus.async_fire(EVENT_ORPHANED_REMOVED, response)
    return response
