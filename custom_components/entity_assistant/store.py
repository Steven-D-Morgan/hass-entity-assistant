"""Unified snapshot + journal store for the Entity Assistant mutation spine."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.ulid import ulid_now

from .change_plan import ChangePlan, json_safe
from .const import (
    DATA_STORE,
    DEFAULT_KEEP_JOURNAL,
    DEFAULT_KEEP_SNAPSHOTS,
    EXPORT_TYPES,
    OBJECT_TO_EXPORT,
    STORAGE_KEY_JOURNAL,
    STORAGE_KEY_SNAPSHOTS,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
    STORE_SAVE_DELAY,
    TRIGGER_AUTO,
    TRIGGER_MANUAL,
)
from .export import ExportOptions, build_export


class EntityAssistantStore:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._snap_store: Any = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_SNAPSHOTS,
            private=True,
            atomic_writes=True,
            minor_version=STORAGE_MINOR_VERSION,
        )
        self._journal_store: Any = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_JOURNAL,
            private=True,
            atomic_writes=True,
            minor_version=STORAGE_MINOR_VERSION,
        )
        self._snapshots: list[dict[str, Any]] = []
        self._journals: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        snap: dict[str, Any] | None = await self._snap_store.async_load()
        self._snapshots = list((snap or {}).get("snapshots", []))
        journal: dict[str, Any] | None = await self._journal_store.async_load()
        self._journals = list((journal or {}).get("journals", []))
        self._prune_snapshots()
        self._prune_journals()

    def _prune_snapshots(self) -> None:
        self._snapshots = self._snapshots[-DEFAULT_KEEP_SNAPSHOTS:]

    def _prune_journals(self) -> None:
        self._journals = self._journals[-DEFAULT_KEEP_JOURNAL:]

    @callback
    def _snap_data(self) -> dict[str, Any]:
        return {"snapshots": self._snapshots}

    @callback
    def _journal_data(self) -> dict[str, Any]:
        return {"journals": self._journals}

    def _build_snapshot_record(
        self, export_types: list[str], *, trigger: str, label: str, producer: str
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        counts: dict[str, int] = {}
        for export_type in export_types:
            columns, rows = build_export(
                self._hass,
                ExportOptions(export_type=export_type, include_disabled=True, include_hidden=True),
            )
            data[export_type] = {"columns": columns, "rows": rows}
            counts[export_type] = len(rows)
        record: dict[str, Any] = {
            "snapshot_id": ulid_now(),
            "created_at": dt_util.utcnow().isoformat(),
            "trigger": trigger,
            "label": label,
            "producer": producer,
            "object_types": list(export_types),
            "counts": counts,
            "data": data,
        }
        return record

    async def async_auto_snapshot(self, plan: ChangePlan, context: Context | None) -> None:
        export_types = sorted({OBJECT_TO_EXPORT[obj] for obj in plan.object_types()})
        if not export_types:
            return
        record = self._build_snapshot_record(
            export_types, trigger=TRIGGER_AUTO, label="", producer=plan.producer
        )
        self._snapshots.append(record)
        self._prune_snapshots()
        self._snap_store.async_delay_save(self._snap_data, STORE_SAVE_DELAY)

    async def async_capture_snapshot(
        self, *, label: str, export_types: list[str] | None, context: Context | None
    ) -> dict[str, Any]:
        types = list(export_types) if export_types else list(EXPORT_TYPES)
        record = self._build_snapshot_record(
            types, trigger=TRIGGER_MANUAL, label=label, producer=""
        )
        self._snapshots.append(record)
        self._prune_snapshots()
        await self._snap_store.async_save(self._snap_data())
        counts: dict[str, int] = record["counts"]
        return {
            "snapshot_id": record["snapshot_id"],
            "created_at": record["created_at"],
            "label": record["label"],
            "trigger": record["trigger"],
            "object_types": record["object_types"],
            "counts": counts,
            "total_rows": sum(counts.values()),
            "kept": len(self._snapshots),
        }

    async def async_record_journal(
        self,
        producer: str,
        journal_batch: list[dict[str, Any]],
        context: Context | None,
    ) -> str:
        jid: str = ulid_now()
        changes: list[dict[str, Any]] = [
            {
                "object_type": change["object_type"],
                "key": change["key"],
                "field": change["field"],
                "from": json_safe(change["from"]),
                "to": json_safe(change["to"]),
            }
            for change in journal_batch
        ]
        record: dict[str, Any] = {
            "journal_id": jid,
            "created_at": dt_util.utcnow().isoformat(),
            "producer": producer,
            "changes": changes,
        }
        self._journals.append(record)
        self._prune_journals()
        self._journal_store.async_delay_save(self._journal_data, STORE_SAVE_DELAY)
        return jid

    async def async_save_now(self) -> None:
        await self._snap_store.async_save(self._snap_data())
        await self._journal_store.async_save(self._journal_data())

    async def async_remove(self) -> None:
        await self._snap_store.async_remove()
        await self._journal_store.async_remove()
        self._snapshots = []
        self._journals = []


@callback
def async_get_store(hass: HomeAssistant) -> EntityAssistantStore:
    store: EntityAssistantStore = hass.data[DATA_STORE]
    return store


async def async_remove_storage(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await EntityAssistantStore(hass, entry).async_remove()
