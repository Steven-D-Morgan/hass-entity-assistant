"""Shared export logic for Entity Assistant.

Used by the service, the button entity, and the HTTP download view so they
all produce identical output. Supports three export modes (entities, devices,
areas), filtering, staleness detection, and emits a completion event.
"""
from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass

import voluptuous as vol

from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.util import dt as dt_util

from .const import (
    COLUMNS_BY_TYPE,
    DEFAULT_EXPORT_TYPE,
    DEFAULT_STALE_DAYS,
    EVENT_EXPORT_COMPLETED,
    EXPORT_TYPE_AREAS,
    EXPORT_TYPE_DEVICES,
)

# State values that mean an entity has no usable value right now.
_DEAD_STATES = ("unavailable", "unknown")


@dataclass(slots=True)
class ExportOptions:
    """Options controlling what gets exported."""

    export_type: str = DEFAULT_EXPORT_TYPE
    include_disabled: bool = True
    include_hidden: bool = True
    only_enabled: bool = False
    domains: frozenset[str] | None = None
    areas: frozenset[str] | None = None
    stale_only: bool = False
    stale_days: int = DEFAULT_STALE_DAYS

    @property
    def want_disabled(self) -> bool:
        """Whether disabled items should be included."""
        return self.include_disabled and not self.only_enabled

    @property
    def want_hidden(self) -> bool:
        """Whether hidden items should be included."""
        return self.include_hidden and not self.only_enabled

    def area_matches(self, area_id: str | None, area_name: str | None) -> bool:
        """Whether a row's area passes the area filter (by id or name)."""
        if self.areas is None:
            return True
        return (area_id in self.areas) or (
            area_name is not None and area_name in self.areas
        )


def resolve_path(hass: HomeAssistant, filename: str) -> str:
    """Resolve a user-supplied filename to a path inside the config dir.

    Guards against path traversal so the export can only be written
    somewhere under the Home Assistant configuration directory.
    """
    config_dir = os.path.realpath(hass.config.config_dir)
    target = os.path.realpath(os.path.join(config_dir, filename))
    if target != config_dir and not target.startswith(config_dir + os.sep):
        raise vol.Invalid(
            f"filename must resolve to a path inside the config directory ({config_dir})"
        )
    return target


def _label_names(label_reg: lr.LabelRegistry, label_ids: set[str] | None) -> str:
    """Resolve label ids to a sorted, comma-joined list of label names."""
    if not label_ids:
        return ""
    names = []
    for label_id in label_ids:
        label = label_reg.async_get_label(label_id)
        names.append(label.name if label else label_id)
    return ", ".join(sorted(names))


def _entity_staleness(
    entity: er.RegistryEntry,
    state: State | None,
    config_entry_missing: bool,
    stale_days: int,
) -> tuple[list[str], str, str]:
    """Return (reasons, last_changed_iso, last_changed_days) for an entity.

    Reasons are clear category labels: ``orphaned``, ``restored``,
    ``unavailable``, ``not_changed_<N>d``.
    """
    reasons: list[str] = []
    last_changed_iso = ""
    last_changed_days = ""

    # Registry entry whose config entry / integration no longer exists.
    if config_entry_missing:
        reasons.append("orphaned")

    if state is None:
        # No live state and not intentionally disabled -> not being provided.
        if not entity.disabled:
            reasons.append("restored")
    else:
        if state.state in _DEAD_STATES:
            reasons.append("unavailable")
        if state.attributes.get("restored") and "restored" not in reasons:
            reasons.append("restored")
        if state.last_changed:
            last_changed_iso = state.last_changed.isoformat()
            age_days = max(0, (dt_util.utcnow() - state.last_changed).days)
            last_changed_days = str(age_days)
            if age_days >= stale_days:
                reasons.append(f"not_changed_{stale_days}d")

    return reasons, last_changed_iso, last_changed_days


@callback
def _build_entity_rows(hass: HomeAssistant, options: ExportOptions) -> list[dict[str, str]]:
    """Build one row per entity, enriched with device, area, floor and labels."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    floor_reg = fr.async_get(hass)
    label_reg = lr.async_get(hass)

    rows: list[dict[str, str]] = []

    for entity in sorted(ent_reg.entities.values(), key=lambda e: e.entity_id):
        if entity.disabled and not options.want_disabled:
            continue
        if entity.hidden and not options.want_hidden:
            continue
        if options.domains is not None and entity.domain not in options.domains:
            continue

        device = dev_reg.async_get(entity.device_id) if entity.device_id else None

        # Entity-level area override falls back to the device's area.
        area_id = entity.area_id or (device.area_id if device else None)
        area = area_reg.async_get_area(area_id) if area_id else None
        area_name = area.name if area else None

        if not options.area_matches(area_id, area_name):
            continue

        floor = (
            floor_reg.async_get_floor(area.floor_id)
            if area and area.floor_id
            else None
        )

        config_entry = (
            hass.config_entries.async_get_entry(entity.config_entry_id)
            if entity.config_entry_id
            else None
        )
        config_entry_missing = bool(entity.config_entry_id) and config_entry is None

        state = hass.states.get(entity.entity_id)
        state_value = state.state if state else ""
        unit = ""
        device_class = entity.device_class or entity.original_device_class or ""
        if state:
            unit = state.attributes.get("unit_of_measurement", "") or ""
            if not device_class:
                device_class = state.attributes.get("device_class", "") or ""

        reasons, last_changed_iso, last_changed_days = _entity_staleness(
            entity, state, config_entry_missing, options.stale_days
        )

        if options.stale_only and not reasons:
            continue

        if state is None:
            available = ""
        else:
            available = "false" if state.state in _DEAD_STATES else "true"

        rows.append(
            {
                "entity_id": entity.entity_id,
                "name": entity.name or entity.original_name or "",
                "original_name": entity.original_name or "",
                "platform": entity.platform or "",
                "config_entry": config_entry.title if config_entry else "",
                "device_id": entity.device_id or "",
                "device_name": (device.name_by_user or device.name) if device else "",
                "device_manufacturer": device.manufacturer if device else "",
                "device_model": device.model if device else "",
                "area_id": area_id or "",
                "area_name": area_name or "",
                "floor": floor.name if floor else "",
                "labels": _label_names(label_reg, entity.labels),
                "entity_category": entity.entity_category or "",
                "device_class": device_class,
                "unit_of_measurement": unit,
                "state": state_value,
                "available": available,
                "last_changed": last_changed_iso,
                "last_changed_days": last_changed_days,
                "stale": "true" if reasons else "false",
                "stale_reason": ", ".join(reasons),
                "enabled": "false" if entity.disabled else "true",
                "disabled_by": entity.disabled_by or "",
                "hidden_by": entity.hidden_by or "",
                "unique_id": entity.unique_id or "",
            }
        )

    return rows


@callback
def _build_device_rows(hass: HomeAssistant, options: ExportOptions) -> list[dict[str, str]]:
    """Build one row per device, including devices with no entities."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    floor_reg = fr.async_get(hass)
    label_reg = lr.async_get(hass)

    # Total and available (live) entity counts per device.
    total_counts: dict[str, int] = {}
    available_counts: dict[str, int] = {}
    for entity in ent_reg.entities.values():
        if not entity.device_id:
            continue
        total_counts[entity.device_id] = total_counts.get(entity.device_id, 0) + 1
        state = hass.states.get(entity.entity_id)
        if state and state.state not in _DEAD_STATES:
            available_counts[entity.device_id] = (
                available_counts.get(entity.device_id, 0) + 1
            )

    rows: list[dict[str, str]] = []

    for device in sorted(dev_reg.devices.values(), key=lambda d: d.id):
        if device.disabled and not options.want_disabled:
            continue

        area = area_reg.async_get_area(device.area_id) if device.area_id else None
        area_name = area.name if area else None
        if not options.area_matches(device.area_id, area_name):
            continue

        floor = (
            floor_reg.async_get_floor(area.floor_id)
            if area and area.floor_id
            else None
        )

        entry_titles = []
        any_entry = False
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry:
                any_entry = True
                entry_titles.append(entry.title)

        total = total_counts.get(device.id, 0)
        available = available_counts.get(device.id, 0)

        reasons: list[str] = []
        if device.config_entries and not any_entry:
            reasons.append("orphaned")
        if total == 0:
            reasons.append("no_entities")
        elif available == 0:
            reasons.append("all_unavailable")

        if options.stale_only and not reasons:
            continue

        rows.append(
            {
                "device_id": device.id,
                "name": device.name or "",
                "name_by_user": device.name_by_user or "",
                "manufacturer": device.manufacturer or "",
                "model": device.model or "",
                "sw_version": device.sw_version or "",
                "hw_version": device.hw_version or "",
                "area_id": device.area_id or "",
                "area_name": area_name or "",
                "floor": floor.name if floor else "",
                "labels": _label_names(label_reg, device.labels),
                "config_entries": ", ".join(sorted(entry_titles)),
                "via_device_id": device.via_device_id or "",
                "entity_count": str(total),
                "available_entity_count": str(available),
                "disabled_by": device.disabled_by or "",
                "stale": "true" if reasons else "false",
                "stale_reason": ", ".join(reasons),
            }
        )

    return rows


@callback
def _build_area_rows(hass: HomeAssistant, options: ExportOptions) -> list[dict[str, str]]:
    """Build one row per area with device and entity counts."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    floor_reg = fr.async_get(hass)
    label_reg = lr.async_get(hass)

    # Devices per area.
    device_counts: dict[str, int] = {}
    for device in dev_reg.devices.values():
        if device.area_id:
            device_counts[device.area_id] = device_counts.get(device.area_id, 0) + 1

    # Entities per effective area (entity override, else its device's area).
    entity_counts: dict[str, int] = {}
    for entity in ent_reg.entities.values():
        area_id = entity.area_id
        if not area_id and entity.device_id:
            device = dev_reg.async_get(entity.device_id)
            area_id = device.area_id if device else None
        if area_id:
            entity_counts[area_id] = entity_counts.get(area_id, 0) + 1

    rows: list[dict[str, str]] = []

    for area in sorted(area_reg.areas.values(), key=lambda a: a.name):
        if not options.area_matches(area.id, area.name):
            continue

        floor = floor_reg.async_get_floor(area.floor_id) if area.floor_id else None

        devices = device_counts.get(area.id, 0)
        entities = entity_counts.get(area.id, 0)

        reasons: list[str] = []
        if devices == 0 and entities == 0:
            reasons.append("empty")

        if options.stale_only and not reasons:
            continue

        rows.append(
            {
                "area_id": area.id,
                "name": area.name,
                "floor_id": area.floor_id or "",
                "floor": floor.name if floor else "",
                "labels": _label_names(label_reg, area.labels),
                "aliases": ", ".join(sorted(area.aliases)) if area.aliases else "",
                "device_count": str(devices),
                "entity_count": str(entities),
                "picture": area.picture or "",
                "stale": "true" if reasons else "false",
                "stale_reason": ", ".join(reasons),
            }
        )

    return rows


@callback
def build_export(
    hass: HomeAssistant, options: ExportOptions
) -> tuple[list[str], list[dict[str, str]]]:
    """Return (columns, rows) for the requested export type."""
    if options.export_type == EXPORT_TYPE_DEVICES:
        rows = _build_device_rows(hass, options)
    elif options.export_type == EXPORT_TYPE_AREAS:
        rows = _build_area_rows(hass, options)
    else:
        rows = _build_entity_rows(hass, options)
    return COLUMNS_BY_TYPE[options.export_type], rows


def rows_to_csv(columns: list[str], rows: list[dict[str, str]]) -> str:
    """Serialize rows to a CSV string."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def write_csv(path: str, columns: list[str], rows: list[dict[str, str]]) -> None:
    """Write rows to disk (runs in the executor — blocking IO)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write(rows_to_csv(columns, rows))


async def async_run_export(
    hass: HomeAssistant,
    options: ExportOptions,
    filename: str,
    triggered_by: str,
) -> tuple[str, int]:
    """Run an export to a file and fire the completion event.

    Returns (path, row_count).
    """
    path = resolve_path(hass, filename)
    columns, rows = build_export(hass, options)
    await hass.async_add_executor_job(write_csv, path, columns, rows)

    hass.bus.async_fire(
        EVENT_EXPORT_COMPLETED,
        {
            "path": path,
            "row_count": len(rows),
            "export_type": options.export_type,
            "triggered_by": triggered_by,
        },
    )
    return path, len(rows)
