"""Patch-semantics registry import for Entity Assistant."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import json
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
import voluptuous as vol

from .change_plan import ChangePlan, FieldChange, NewRef, ObjectCreate
from .const import (
    ATTR_CONFIRM,
    ATTR_CREATE_MISSING,
    ATTR_FILENAME,
    ATTR_FORMAT,
    ATTR_IMPORT_TYPE,
    DEFAULT_MAX_ROWS,
    EXPORT_TYPE_AREAS,
    EXPORT_TYPE_DEVICES,
    EXPORT_TYPE_ENTITIES,
    EXPORT_TYPE_FLOORS,
    EXPORT_TYPE_LABELS,
    IMPORT_FORMAT_CSV,
    IMPORT_FORMAT_JSON,
    IMPORT_TYPE_AUTO,
    KEY_COLUMN,
    OBJECT_AREA,
    OBJECT_DEVICE,
    OBJECT_ENTITY,
    OBJECT_FLOOR,
    OBJECT_LABEL,
)
from .export import ExportOptions, build_export, resolve_path
from .spine import async_commit_plan, async_require_admin

PRODUCER = "import_changes"

_UNCHANGED = object()

OBJECT_BY_TYPE = {
    EXPORT_TYPE_ENTITIES: OBJECT_ENTITY,
    EXPORT_TYPE_DEVICES: OBJECT_DEVICE,
    EXPORT_TYPE_AREAS: OBJECT_AREA,
    EXPORT_TYPE_FLOORS: OBJECT_FLOOR,
    EXPORT_TYPE_LABELS: OBJECT_LABEL,
}

_INFER_ORDER = [
    EXPORT_TYPE_ENTITIES,
    EXPORT_TYPE_DEVICES,
    EXPORT_TYPE_AREAS,
    EXPORT_TYPE_FLOORS,
    EXPORT_TYPE_LABELS,
]
_INFER_COLUMNS = {
    EXPORT_TYPE_ENTITIES: ("registry_id", "entity_id"),
    EXPORT_TYPE_DEVICES: ("device_id",),
    EXPORT_TYPE_AREAS: ("area_id",),
    EXPORT_TYPE_FLOORS: ("floor_id",),
    EXPORT_TYPE_LABELS: ("label_id",),
}

_SCALAR_FIELDS: dict[str, list[tuple[str, bool]]] = {
    EXPORT_TYPE_ENTITIES: [("name", False), ("icon", False)],
    EXPORT_TYPE_DEVICES: [("name_by_user", False)],
    EXPORT_TYPE_AREAS: [("name", True), ("icon", False), ("picture", False)],
    EXPORT_TYPE_FLOORS: [("name", True), ("icon", False)],
    EXPORT_TYPE_LABELS: [("name", True), ("color", False), ("icon", False), ("description", False)],
}
_SET_FIELDS: dict[str, list[str]] = {
    EXPORT_TYPE_ENTITIES: ["aliases"],
    EXPORT_TYPE_AREAS: ["aliases"],
    EXPORT_TYPE_FLOORS: ["aliases"],
}
_LABEL_TYPES = frozenset({EXPORT_TYPE_ENTITIES, EXPORT_TYPE_DEVICES, EXPORT_TYPE_AREAS})
_AREA_REF_TYPES = frozenset({EXPORT_TYPE_ENTITIES, EXPORT_TYPE_DEVICES})


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _split_set(value: str) -> set[str]:
    return {part.strip() for part in value.split(",") if part.strip()}


def _warn(row: int | None, key: str, column: str, message: str) -> dict[str, Any]:
    return {"row": row, "key": key, "column": column, "message": message}


@dataclass(slots=True)
class ParsedFile:
    columns: set[str]
    rows: list[dict[str, str]]


@dataclass(slots=True)
class ImportReport:
    export_type: str
    rows_total: int
    rows_matched: int
    rows_unmatched: int
    warnings: list[dict[str, Any]]
    key_fallback: bool


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def _parse_text(text: str, fmt: str) -> ParsedFile:
    if fmt == IMPORT_FORMAT_JSON:
        return _parse_json(text)
    return _parse_csv(text)


def _parse_json(text: str) -> ParsedFile:
    data: Any = json.loads(text)
    if isinstance(data, dict) and "rows" in data:
        data = data["rows"]
    if not isinstance(data, list):
        raise ValueError("JSON import must be a list of row objects")
    rows: list[dict[str, str]] = []
    columns: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("each JSON row must be an object")
        row = {str(key): _norm(_stringify(value)) for key, value in item.items()}
        rows.append(row)
        columns.update(row)
    return ParsedFile(columns, rows)


def _parse_csv(text: str) -> ParsedFile:
    delimiter = _sniff_delimiter(text[:4096])
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows: list[dict[str, str]] = []
    for raw in reader:
        row = {key: _norm(value) for key, value in raw.items() if key is not None}
        rows.append(row)
    columns = {name for name in (reader.fieldnames or []) if name}
    return ParsedFile(columns, rows)


def _detect_format(filename: str, text: str, fmt_opt: str) -> str:
    if fmt_opt in (IMPORT_FORMAT_CSV, IMPORT_FORMAT_JSON):
        return fmt_opt
    lower = filename.lower()
    if lower.endswith(".json"):
        return IMPORT_FORMAT_JSON
    if lower.endswith((".csv", ".tsv", ".txt")):
        return IMPORT_FORMAT_CSV
    stripped = text.lstrip()
    if stripped[:1] in ("[", "{"):
        return IMPORT_FORMAT_JSON
    return IMPORT_FORMAT_CSV


def read_import_file(hass: HomeAssistant, filename: str, fmt_opt: str) -> tuple[str, ParsedFile]:
    path = resolve_path(hass, filename)
    with open(path, encoding="utf-8-sig", newline="") as file:
        text = file.read()
    fmt = _detect_format(filename, text, fmt_opt)
    return fmt, _parse_text(text, fmt)


def infer_import_type(columns: set[str]) -> str | None:
    for export_type in _INFER_ORDER:
        if any(column in columns for column in _INFER_COLUMNS[export_type]):
            return export_type
    return None


class _Resolver:
    def __init__(self, hass: HomeAssistant, *, create_missing: bool) -> None:
        self.create_missing = create_missing
        self.creates: list[ObjectCreate] = []
        self._refs: dict[tuple[str, str], str] = {}
        self._labels: dict[str, str] = {}
        for label in lr.async_get(hass).labels.values():
            self._labels.setdefault(label.name.casefold(), label.label_id)
        self._areas: dict[str, str] = {}
        for area in ar.async_get(hass).areas.values():
            self._areas.setdefault(area.name.casefold(), area.id)
        self._floors: dict[str, str] = {}
        for floor in fr.async_get(hass).floors.values():
            self._floors.setdefault(floor.name.casefold(), floor.floor_id)

    def _resolve(
        self,
        kind: str,
        existing: dict[str, str],
        object_type: str,
        name: str,
        warnings: list[dict[str, Any]],
        row: int,
        key: str,
        column: str,
    ) -> str | NewRef | None:
        folded = name.casefold()
        if folded in existing:
            return existing[folded]
        if not self.create_missing:
            warnings.append(
                _warn(
                    row,
                    key,
                    column,
                    f"{kind} '{name}' not found; skipped "
                    "(set create_missing: true to auto-create it)",
                )
            )
            return None
        ref_key = (object_type, folded)
        ref = self._refs.get(ref_key)
        if ref is None:
            ref = f"{object_type}-{len(self._refs)}"
            self._refs[ref_key] = ref
            self.creates.append(ObjectCreate(object_type, temp_ref=ref, fields={"name": name}))
        return NewRef(ref)

    def resolve_label(
        self, name: str, warnings: list[dict[str, Any]], row: int, key: str
    ) -> str | NewRef | None:
        return self._resolve(
            "label", self._labels, OBJECT_LABEL, name, warnings, row, key, "labels"
        )

    def resolve_area(
        self, name: str, warnings: list[dict[str, Any]], row: int, key: str
    ) -> str | NewRef | None:
        return self._resolve(
            "area", self._areas, OBJECT_AREA, name, warnings, row, key, "area_name"
        )

    def resolve_floor(
        self, name: str, warnings: list[dict[str, Any]], row: int, key: str
    ) -> str | NewRef | None:
        return self._resolve(
            "floor", self._floors, OBJECT_FLOOR, name, warnings, row, key, "floor"
        )


def _scalar_changes(
    export_type: str,
    key: str,
    file_row: dict[str, str],
    canon_row: dict[str, str],
    warnings: list[dict[str, Any]],
    row: int,
) -> list[FieldChange]:
    object_type = OBJECT_BY_TYPE[export_type]
    changes: list[FieldChange] = []
    for field_name, required in _SCALAR_FIELDS[export_type]:
        if field_name not in file_row:
            continue
        new_value = file_row[field_name]
        old_value = canon_row.get(field_name, "")
        if new_value == old_value:
            continue
        if required and new_value == "":
            warnings.append(
                _warn(row, key, field_name, f"{field_name} cannot be blank; field skipped")
            )
            continue
        changes.append(
            FieldChange(
                object_type,
                key,
                field_name,
                from_=old_value or None,
                to=new_value or None,
            )
        )
    return changes


def _set_changes(
    export_type: str,
    key: str,
    file_row: dict[str, str],
    canon_row: dict[str, str],
    live: Any,
) -> list[FieldChange]:
    object_type = OBJECT_BY_TYPE[export_type]
    changes: list[FieldChange] = []
    for field_name in _SET_FIELDS.get(export_type, []):
        if field_name not in file_row:
            continue
        new_set = _split_set(file_row[field_name])
        old_set = _split_set(canon_row.get(field_name, ""))
        if new_set == old_set:
            continue
        current = getattr(live, field_name)
        to_value: Any = sorted(new_set) if isinstance(current, list) else set(new_set)
        changes.append(FieldChange(object_type, key, field_name, from_=current, to=to_value))
    return changes


def _level_change(
    key: str,
    file_row: dict[str, str],
    canon_row: dict[str, str],
    warnings: list[dict[str, Any]],
    row: int,
) -> list[FieldChange]:
    if "level" not in file_row:
        return []
    new_value = file_row["level"]
    old_value = canon_row.get("level", "")
    if new_value == old_value:
        return []
    to_value: int | None
    if new_value == "":
        to_value = None
    else:
        try:
            to_value = int(new_value)
        except ValueError:
            warnings.append(_warn(row, key, "level", f"level {new_value!r} is not an integer"))
            return []
    from_value = int(old_value) if old_value else None
    return [FieldChange(OBJECT_FLOOR, key, "level", from_=from_value, to=to_value)]


def _labels_change(
    export_type: str,
    key: str,
    file_row: dict[str, str],
    canon_row: dict[str, str],
    live: Any,
    resolver: _Resolver,
    warnings: list[dict[str, Any]],
    row: int,
) -> list[FieldChange]:
    if export_type not in _LABEL_TYPES or "labels" not in file_row:
        return []
    new_names = _split_set(file_row["labels"])
    old_names = _split_set(canon_row.get("labels", ""))
    if new_names == old_names:
        return []
    resolved: set[str | NewRef] = set()
    for name in sorted(new_names):
        label = resolver.resolve_label(name, warnings, row, key)
        if label is not None:
            resolved.add(label)
    current = set(live.labels)
    if all(isinstance(item, str) for item in resolved) and resolved == current:
        return []
    return [FieldChange(OBJECT_BY_TYPE[export_type], key, "labels", from_=current, to=resolved)]


def _area_ref_change(
    export_type: str,
    key: str,
    file_row: dict[str, str],
    canon_row: dict[str, str],
    hass: HomeAssistant,
    resolver: _Resolver,
    warnings: list[dict[str, Any]],
    row: int,
) -> list[FieldChange]:
    if export_type not in _AREA_REF_TYPES:
        return []
    to_value = _resolve_reference(
        file_row,
        canon_row,
        id_column="area_id",
        name_column="area_name",
        exists=lambda value: ar.async_get(hass).async_get_area(value) is not None,
        resolve_name=lambda name: resolver.resolve_area(name, warnings, row, key),
        warnings=warnings,
        row=row,
        key=key,
        kind="area",
    )
    if to_value is _UNCHANGED:
        return []
    return [
        FieldChange(
            OBJECT_BY_TYPE[export_type],
            key,
            "area_id",
            from_=canon_row.get("area_id") or None,
            to=to_value,
        )
    ]


def _floor_ref_change(
    key: str,
    file_row: dict[str, str],
    canon_row: dict[str, str],
    hass: HomeAssistant,
    resolver: _Resolver,
    warnings: list[dict[str, Any]],
    row: int,
) -> list[FieldChange]:
    to_value = _resolve_reference(
        file_row,
        canon_row,
        id_column="floor_id",
        name_column="floor",
        exists=lambda value: fr.async_get(hass).async_get_floor(value) is not None,
        resolve_name=lambda name: resolver.resolve_floor(name, warnings, row, key),
        warnings=warnings,
        row=row,
        key=key,
        kind="floor",
    )
    if to_value is _UNCHANGED:
        return []
    return [
        FieldChange(
            OBJECT_AREA, key, "floor_id", from_=canon_row.get("floor_id") or None, to=to_value
        )
    ]


def _resolve_reference(
    file_row: dict[str, str],
    canon_row: dict[str, str],
    *,
    id_column: str,
    name_column: str,
    exists: Any,
    resolve_name: Any,
    warnings: list[dict[str, Any]],
    row: int,
    key: str,
    kind: str,
) -> Any:
    if id_column in file_row and file_row[id_column] != canon_row.get(id_column, ""):
        new_id = file_row[id_column]
        if new_id == "":
            return None
        if exists(new_id):
            return new_id
        warnings.append(_warn(row, key, id_column, f"{kind} id {new_id!r} not found; skipped"))
        return _UNCHANGED
    if name_column in file_row and file_row[name_column] != canon_row.get(name_column, ""):
        new_name = file_row[name_column]
        if new_name == "":
            return None
        resolved = resolve_name(new_name)
        if resolved is None:
            return _UNCHANGED
        if not isinstance(resolved, NewRef) and resolved == canon_row.get(id_column, ""):
            return _UNCHANGED
        return resolved
    return _UNCHANGED


def _live_object(hass: HomeAssistant, export_type: str, key: str) -> Any:
    if export_type == EXPORT_TYPE_ENTITIES:
        return er.async_get(hass).entities.get_entry(key)
    if export_type == EXPORT_TYPE_DEVICES:
        return dr.async_get(hass).async_get(key)
    if export_type == EXPORT_TYPE_AREAS:
        return ar.async_get(hass).async_get_area(key)
    if export_type == EXPORT_TYPE_FLOORS:
        return fr.async_get(hass).async_get_floor(key)
    return lr.async_get(hass).async_get_label(key)


def _row_changes(
    hass: HomeAssistant,
    export_type: str,
    key: str,
    file_row: dict[str, str],
    canon_row: dict[str, str],
    live: Any,
    resolver: _Resolver,
    warnings: list[dict[str, Any]],
    row: int,
) -> list[FieldChange]:
    changes: list[FieldChange] = []
    changes += _scalar_changes(export_type, key, file_row, canon_row, warnings, row)
    changes += _set_changes(export_type, key, file_row, canon_row, live)
    if export_type == EXPORT_TYPE_FLOORS:
        changes += _level_change(key, file_row, canon_row, warnings, row)
    changes += _labels_change(
        export_type, key, file_row, canon_row, live, resolver, warnings, row
    )
    changes += _area_ref_change(
        export_type, key, file_row, canon_row, hass, resolver, warnings, row
    )
    if export_type == EXPORT_TYPE_AREAS:
        changes += _floor_ref_change(key, file_row, canon_row, hass, resolver, warnings, row)
    return changes


def _match_key(
    export_type: str,
    file_row: dict[str, str],
    canon_by_id: dict[str, dict[str, str]],
    canon_by_entity: dict[str, dict[str, str]],
    key_column: str,
    warnings: list[dict[str, Any]],
    row: int,
) -> tuple[str, dict[str, str]] | None:
    raw_key = file_row.get(key_column, "")
    if raw_key and raw_key in canon_by_id:
        return raw_key, canon_by_id[raw_key]
    if export_type == EXPORT_TYPE_ENTITIES:
        entity_id = file_row.get("entity_id", "")
        if entity_id and entity_id in canon_by_entity:
            canon = canon_by_entity[entity_id]
            message = (
                "registry_id not found; matched by entity_id"
                if raw_key
                else "no registry_id; matched by entity_id (less stable across renames)"
            )
            warnings.append(_warn(row, raw_key or entity_id, key_column, message))
            return canon[key_column], canon
    shown = raw_key or file_row.get("entity_id", "")
    warnings.append(_warn(row, shown, key_column, "no registry object matches this row; skipped"))
    return None


def compile_import(
    hass: HomeAssistant,
    parsed: ParsedFile,
    *,
    export_type: str,
    create_missing: bool,
) -> tuple[ChangePlan, ImportReport]:
    _, raw_canon_rows = build_export(
        hass,
        ExportOptions(export_type=export_type, include_disabled=True, include_hidden=True),
    )
    canon_rows = [{key: _norm(value) for key, value in row.items()} for row in raw_canon_rows]
    key_column = KEY_COLUMN[export_type]
    canon_by_id = {canon[key_column]: canon for canon in canon_rows}
    canon_by_entity = (
        {canon["entity_id"]: canon for canon in canon_rows}
        if export_type == EXPORT_TYPE_ENTITIES
        else {}
    )

    resolver = _Resolver(hass, create_missing=create_missing)

    warnings: list[dict[str, Any]] = []
    key_fallback = (
        export_type == EXPORT_TYPE_ENTITIES
        and key_column not in parsed.columns
        and "entity_id" in parsed.columns
    )
    if key_fallback:
        warnings.append(
            _warn(
                None,
                "",
                key_column,
                "no registry_id column; keying by entity_id (less stable across renames)",
            )
        )

    updates: list[FieldChange] = []
    matched = 0
    for index, file_row in enumerate(parsed.rows):
        match = _match_key(
            export_type, file_row, canon_by_id, canon_by_entity, key_column, warnings, index
        )
        if match is None:
            continue
        key, canon_row = match
        matched += 1
        live = _live_object(hass, export_type, key)
        if live is None:
            continue
        updates += _row_changes(
            hass, export_type, key, file_row, canon_row, live, resolver, warnings, index
        )

    plan = ChangePlan(producer=PRODUCER, creates=resolver.creates, updates=updates)
    report = ImportReport(
        export_type=export_type,
        rows_total=len(parsed.rows),
        rows_matched=matched,
        rows_unmatched=len(parsed.rows) - matched,
        warnings=warnings,
        key_fallback=key_fallback,
    )
    return plan, report


def import_response(
    plan: ChangePlan,
    report: ImportReport,
    result: Any,
    *,
    dry_run: bool,
    cap: int = DEFAULT_MAX_ROWS,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "dry_run": dry_run,
        "producer": PRODUCER,
        "import_type": report.export_type,
        "rows_total": report.rows_total,
        "rows_matched": report.rows_matched,
        "rows_unmatched": report.rows_unmatched,
        "key_fallback": report.key_fallback,
        "warning_count": len(report.warnings),
        "warnings": report.warnings[:cap],
    }
    if dry_run or result is None:
        preview = plan.to_response(dry_run=True, cap=cap)
        base["counts"] = preview["counts"]
        base["object_types"] = preview["object_types"]
        base["creates"] = preview["creates"]
        base["updates"] = preview["updates"]
        base["truncated"] = preview["truncated"]
    else:
        applied = result.to_response(cap=cap)
        base["counts"] = applied["counts"]
        base["object_types"] = plan.object_types()
        base["created_ids"] = applied["created_ids"]
        base["updated_keys"] = applied["updated_keys"]
        base["errors"] = applied["errors"]
        base["journal_id"] = applied["journal_id"]
    return base


async def async_handle_import(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    await async_require_admin(hass, call.context)
    filename = call.data[ATTR_FILENAME]
    fmt_opt = call.data[ATTR_FORMAT]
    type_opt = call.data[ATTR_IMPORT_TYPE]
    create_missing = call.data[ATTR_CREATE_MISSING]

    try:
        _, parsed = await hass.async_add_executor_job(
            read_import_file, hass, filename, fmt_opt
        )
    except FileNotFoundError as err:
        raise HomeAssistantError(f"Import file not found: {filename}") from err
    except (OSError, ValueError, vol.Invalid) as err:
        raise HomeAssistantError(f"Could not read import file {filename!r}: {err}") from err

    export_type = type_opt if type_opt != IMPORT_TYPE_AUTO else infer_import_type(parsed.columns)
    if export_type is None:
        raise HomeAssistantError(
            "Could not determine the import type from the file's columns. Set import_type "
            "explicitly, or include a registry_id / device_id / area_id / floor_id / label_id "
            "column."
        )

    plan, report = compile_import(
        hass, parsed, export_type=export_type, create_missing=create_missing
    )
    if not call.data[ATTR_CONFIRM]:
        return import_response(plan, report, None, dry_run=True)
    result = await async_commit_plan(hass, plan, triggered_by="service", context=call.context)
    return import_response(plan, report, result, dry_run=False)
