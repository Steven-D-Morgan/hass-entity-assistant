from __future__ import annotations

from homeassistant.core import HomeAssistant
from syrupy.assertion import SnapshotAssertion

from custom_components.entity_assistant.export import ExportOptions, build_export, rows_to_csv


async def test_entity_csv_header_snapshot(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    columns, _ = build_export(hass, ExportOptions())
    header = rows_to_csv(columns, []).strip()
    assert header == snapshot


async def test_device_csv_header_snapshot(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    columns, _ = build_export(hass, ExportOptions(export_type="devices"))
    header = rows_to_csv(columns, []).strip()
    assert header == snapshot


async def test_area_csv_header_snapshot(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    columns, _ = build_export(hass, ExportOptions(export_type="areas"))
    header = rows_to_csv(columns, []).strip()
    assert header == snapshot


async def test_floor_csv_header_snapshot(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    columns, _ = build_export(hass, ExportOptions(export_type="floors"))
    header = rows_to_csv(columns, []).strip()
    assert header == snapshot


async def test_label_csv_header_snapshot(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    columns, _ = build_export(hass, ExportOptions(export_type="labels"))
    header = rows_to_csv(columns, []).strip()
    assert header == snapshot


async def test_entity_columns_list_snapshot(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    columns, _ = build_export(hass, ExportOptions())
    assert columns == snapshot


async def test_device_columns_list_snapshot(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    columns, _ = build_export(hass, ExportOptions(export_type="devices"))
    assert columns == snapshot


async def test_area_columns_list_snapshot(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    columns, _ = build_export(hass, ExportOptions(export_type="areas"))
    assert columns == snapshot


async def test_floor_columns_list_snapshot(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    columns, _ = build_export(hass, ExportOptions(export_type="floors"))
    assert columns == snapshot


async def test_label_columns_list_snapshot(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    columns, _ = build_export(hass, ExportOptions(export_type="labels"))
    assert columns == snapshot
