from __future__ import annotations

from datetime import timedelta
import os

from freezegun import freeze_time
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.entity_assistant.const import (
    AREA_COLUMNS,
    DEVICE_COLUMNS,
    ENTITY_COLUMNS,
    FLOOR_COLUMNS,
    LABEL_COLUMNS,
)
from custom_components.entity_assistant.export import (
    ExportOptions,
    _alias_names,
    _category_pairs,
    _sanitize_csv_value,
    build_export,
    resolve_path,
    rows_to_csv,
)


def _seed_basic(hass: HomeAssistant) -> dict:
    floor_reg = fr.async_get(hass)
    area_reg = ar.async_get(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    label_reg = lr.async_get(hass)

    floor_entry = floor_reg.async_create("Ground Floor")
    living_room = area_reg.async_create("Living Room")
    area_reg.async_update(living_room.id, floor_id=floor_entry.floor_id)
    kitchen = area_reg.async_create("Kitchen")
    empty_area = area_reg.async_create("Empty Room")

    label = label_reg.async_create("Critical")

    integration = MockConfigEntry(domain="test", title="Test Integration")
    integration.add_to_hass(hass)

    device_a = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={("test", "device_a")},
        name="Device A",
        manufacturer="TestCo",
        model="Model A",
    )
    dev_reg.async_update_device(device_a.id, area_id=living_room.id)

    light = ent_reg.async_get_or_create(
        "light",
        "test",
        "light_1",
        config_entry=integration,
        device_id=device_a.id,
        original_name="Living Room Light",
        suggested_object_id="living_room",
    )
    hass.states.async_set(light.entity_id, "on")

    switch = ent_reg.async_get_or_create(
        "switch",
        "test",
        "switch_1",
        config_entry=integration,
        original_name="Kitchen Switch",
        suggested_object_id="kitchen",
    )
    ent_reg.async_update_entity(switch.entity_id, area_id=kitchen.id)
    hass.states.async_set(switch.entity_id, "on")

    sensor = ent_reg.async_get_or_create(
        "sensor",
        "test",
        "sensor_1",
        config_entry=integration,
        device_id=device_a.id,
        original_name="Temperature",
        suggested_object_id="temperature",
    )
    hass.states.async_set(sensor.entity_id, "unavailable")

    disabled = ent_reg.async_get_or_create(
        "sensor",
        "test",
        "sensor_disabled",
        config_entry=integration,
        original_name="Disabled Sensor",
        suggested_object_id="disabled",
    )
    ent_reg.async_update_entity(disabled.entity_id, disabled_by=er.RegistryEntryDisabler.USER)

    hidden = ent_reg.async_get_or_create(
        "binary_sensor",
        "test",
        "bs_hidden",
        config_entry=integration,
        original_name="Hidden Sensor",
        suggested_object_id="hidden",
    )
    ent_reg.async_update_entity(hidden.entity_id, hidden_by=er.RegistryEntryHider.USER)
    hass.states.async_set(hidden.entity_id, "off")

    return {
        "integration": integration,
        "floor": floor_entry,
        "living_room": living_room,
        "kitchen": kitchen,
        "empty_area": empty_area,
        "label": label,
        "device_a": device_a,
        "light": light,
        "switch": switch,
        "sensor": sensor,
        "disabled": disabled,
        "hidden": hidden,
    }


async def test_build_entity_rows_default(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    columns, rows = build_export(hass, ExportOptions())
    assert columns == ENTITY_COLUMNS
    entity_ids = {r["entity_id"] for r in rows}
    assert refs["light"].entity_id in entity_ids
    assert refs["switch"].entity_id in entity_ids
    assert refs["sensor"].entity_id in entity_ids
    assert refs["disabled"].entity_id in entity_ids
    assert refs["hidden"].entity_id in entity_ids


async def test_build_entity_rows_only_enabled(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions(only_enabled=True))
    entity_ids = {r["entity_id"] for r in rows}
    assert refs["disabled"].entity_id not in entity_ids
    assert refs["hidden"].entity_id not in entity_ids
    assert refs["light"].entity_id in entity_ids


async def test_build_entity_rows_exclude_disabled(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions(include_disabled=False))
    entity_ids = {r["entity_id"] for r in rows}
    assert refs["disabled"].entity_id not in entity_ids
    assert refs["hidden"].entity_id in entity_ids


async def test_build_entity_rows_exclude_hidden(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions(include_hidden=False))
    entity_ids = {r["entity_id"] for r in rows}
    assert refs["hidden"].entity_id not in entity_ids
    assert refs["disabled"].entity_id in entity_ids


async def test_build_entity_rows_domain_filter(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions(domains=frozenset(["light"])))
    entity_ids = {r["entity_id"] for r in rows}
    assert refs["light"].entity_id in entity_ids
    assert refs["switch"].entity_id not in entity_ids


async def test_build_entity_rows_area_filter_by_name(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions(areas=frozenset(["Kitchen"])))
    entity_ids = {r["entity_id"] for r in rows}
    assert refs["switch"].entity_id in entity_ids
    assert refs["light"].entity_id not in entity_ids


async def test_build_entity_rows_area_filter_by_id(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    area_id = refs["living_room"].id
    _, rows = build_export(hass, ExportOptions(areas=frozenset([area_id])))
    entity_ids = {r["entity_id"] for r in rows}
    assert refs["light"].entity_id in entity_ids


async def test_build_entity_rows_stable_key(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions())
    row = next(r for r in rows if r["entity_id"] == refs["light"].entity_id)
    assert row["registry_id"] == refs["light"].id
    assert row["registry_id"]


async def test_build_entity_rows_writable_fields(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_update_entity(
        refs["light"].entity_id,
        icon="mdi:lightbulb",
        aliases=["Main Light", "Lounge Light"],
        categories={"cleaning": "cat_weekly"},
    )
    _, rows = build_export(hass, ExportOptions())
    row = next(r for r in rows if r["entity_id"] == refs["light"].entity_id)
    assert row["icon"] == "mdi:lightbulb"
    assert row["aliases"] == "Lounge Light, Main Light"
    assert row["categories"] == "cleaning:cat_weekly"


async def test_build_entity_rows_stale_only(hass: HomeAssistant) -> None:
    _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions(stale_only=True))
    assert rows
    for row in rows:
        assert row["stale"] == "true"


async def test_entity_staleness_unavailable(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions())
    temp_row = next(r for r in rows if r["entity_id"] == refs["sensor"].entity_id)
    assert temp_row["stale"] == "true"
    assert "unavailable" in temp_row["stale_reason"]


async def test_entity_staleness_orphaned(hass: HomeAssistant) -> None:
    integration = MockConfigEntry(domain="orphan_test", title="Orphan")
    integration.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    orphan = ent_reg.async_get_or_create(
        "sensor",
        "orphan_test",
        "orphan_1",
        config_entry=integration,
        original_name="Orphan Sensor",
    )
    hass.config_entries._entries.pop(integration.entry_id, None)

    _, rows = build_export(hass, ExportOptions())
    orphan_row = next(r for r in rows if r["entity_id"] == orphan.entity_id)
    assert orphan_row["stale"] == "true"
    assert "orphaned" in orphan_row["stale_reason"]


async def test_entity_staleness_not_changed(hass: HomeAssistant) -> None:
    integration = MockConfigEntry(domain="test_stale", title="Test Stale")
    integration.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    entity = ent_reg.async_get_or_create(
        "sensor",
        "test_stale",
        "stale_1",
        config_entry=integration,
        original_name="Stale Sensor",
    )

    past = dt_util.utcnow() - timedelta(days=60)
    with freeze_time(past):
        hass.states.async_set(entity.entity_id, "42")

    _, rows = build_export(hass, ExportOptions(stale_days=30))
    stale_row = next(r for r in rows if r["entity_id"] == entity.entity_id)
    assert stale_row["stale"] == "true"
    assert "not_changed_30d" in stale_row["stale_reason"]


async def test_entity_staleness_restored_attribute(hass: HomeAssistant) -> None:
    integration = MockConfigEntry(domain="test_rest", title="Test Restored")
    integration.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    entity = ent_reg.async_get_or_create(
        "sensor",
        "test_rest",
        "restored_1",
        config_entry=integration,
        original_name="Restored Sensor",
    )
    hass.states.async_set(entity.entity_id, "on", {"restored": True})

    _, rows = build_export(hass, ExportOptions())
    row = next(r for r in rows if r["entity_id"] == entity.entity_id)
    assert row["stale"] == "true"
    assert "restored" in row["stale_reason"]


async def test_build_device_rows_default(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    columns, rows = build_export(hass, ExportOptions(export_type="devices"))
    assert columns == DEVICE_COLUMNS
    device_ids = {r["device_id"] for r in rows}
    assert refs["device_a"].id in device_ids


async def test_build_device_rows_orphaned(hass: HomeAssistant) -> None:
    integration = MockConfigEntry(domain="orphan_dev", title="Orphan Dev")
    integration.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={("orphan_dev", "d1")},
        name="Orphaned Device",
    )
    hass.config_entries._entries.pop(integration.entry_id, None)

    _, rows = build_export(hass, ExportOptions(export_type="devices"))
    row = next(r for r in rows if r["device_id"] == device.id)
    assert row["stale"] == "true"
    assert "orphaned" in row["stale_reason"]


async def test_build_area_rows_default(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    columns, rows = build_export(hass, ExportOptions(export_type="areas"))
    assert columns == AREA_COLUMNS
    area_ids = {r["area_id"] for r in rows}
    assert refs["living_room"].id in area_ids
    assert refs["kitchen"].id in area_ids
    assert refs["empty_area"].id in area_ids


async def test_build_area_rows_empty_area(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions(export_type="areas"))
    empty_row = next(r for r in rows if r["area_id"] == refs["empty_area"].id)
    assert empty_row["stale"] == "true"
    assert "empty" in empty_row["stale_reason"]


async def test_build_area_rows_populated_not_stale(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    _, rows = build_export(hass, ExportOptions(export_type="areas"))
    living_row = next(r for r in rows if r["area_id"] == refs["living_room"].id)
    assert living_row["stale"] == "false"


async def test_build_area_rows_icon(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    ar.async_get(hass).async_update(refs["kitchen"].id, icon="mdi:silverware-fork-knife")
    _, rows = build_export(hass, ExportOptions(export_type="areas"))
    row = next(r for r in rows if r["area_id"] == refs["kitchen"].id)
    assert row["icon"] == "mdi:silverware-fork-knife"


async def test_build_floor_rows_default(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    columns, rows = build_export(hass, ExportOptions(export_type="floors"))
    assert columns == FLOOR_COLUMNS
    row = next(r for r in rows if r["floor_id"] == refs["floor"].floor_id)
    assert row["name"] == "Ground Floor"
    assert row["area_count"] == "1"


async def test_build_floor_rows_fields(hass: HomeAssistant) -> None:
    _seed_basic(hass)
    floor = fr.async_get(hass).async_create(
        "Upstairs", aliases={"Top"}, icon="mdi:home-floor-2", level=2
    )
    _, rows = build_export(hass, ExportOptions(export_type="floors"))
    row = next(r for r in rows if r["floor_id"] == floor.floor_id)
    assert row["level"] == "2"
    assert row["icon"] == "mdi:home-floor-2"
    assert row["aliases"] == "Top"
    assert row["area_count"] == "0"


async def test_build_label_rows_default(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    columns, rows = build_export(hass, ExportOptions(export_type="labels"))
    assert columns == LABEL_COLUMNS
    row = next(r for r in rows if r["label_id"] == refs["label"].label_id)
    assert row["name"] == "Critical"
    assert row["entity_count"] == "0"
    assert row["device_count"] == "0"
    assert row["area_count"] == "0"


async def test_build_label_rows_usage_counts(hass: HomeAssistant) -> None:
    refs = _seed_basic(hass)
    label_id = refs["label"].label_id
    er.async_get(hass).async_update_entity(refs["light"].entity_id, labels={label_id})
    dr.async_get(hass).async_update_device(refs["device_a"].id, labels={label_id})
    _, rows = build_export(hass, ExportOptions(export_type="labels"))
    row = next(r for r in rows if r["label_id"] == label_id)
    assert row["entity_count"] == "1"
    assert row["device_count"] == "1"
    assert row["area_count"] == "0"


async def test_build_label_rows_fields(hass: HomeAssistant) -> None:
    _seed_basic(hass)
    label = lr.async_get(hass).async_create(
        "Zone A", color="red", icon="mdi:tag", description="Test zone"
    )
    _, rows = build_export(hass, ExportOptions(export_type="labels"))
    row = next(r for r in rows if r["label_id"] == label.label_id)
    assert row["color"] == "red"
    assert row["icon"] == "mdi:tag"
    assert row["description"] == "Test zone"


def test_resolve_path_inside_config(hass: HomeAssistant) -> None:
    path = resolve_path(hass, "subdir/file.csv")
    config_dir = os.path.realpath(hass.config.config_dir)
    assert path.startswith(config_dir + os.sep)


def test_resolve_path_traversal_blocked(hass: HomeAssistant) -> None:
    with pytest.raises(vol.Invalid):
        resolve_path(hass, "../../etc/passwd")


def test_resolve_path_absolute_outside_blocked(hass: HomeAssistant) -> None:
    outside = "/tmp/evil.csv" if os.name != "nt" else "C:/Windows/evil.csv"
    with pytest.raises(vol.Invalid):
        resolve_path(hass, outside)


def test_rows_to_csv_header_and_rows() -> None:
    columns = ["a", "b"]
    rows = [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
    output = rows_to_csv(columns, rows)
    lines = output.strip().splitlines()
    assert lines[0] == "a,b"
    assert lines[1] == "1,2"
    assert lines[2] == "3,4"


def test_rows_to_csv_utf8_bom() -> None:
    output = rows_to_csv(["a"], [{"a": "1"}], utf8_bom=True)
    assert output.startswith("\ufeff")


def test_rows_to_csv_no_bom_default() -> None:
    output = rows_to_csv(["a"], [{"a": "1"}])
    assert not output.startswith("\ufeff")


def test_alias_names_sorts_and_joins() -> None:
    assert _alias_names(["Zebra", "apple"]) == "Zebra, apple"
    assert _alias_names({"one", "two"}) == "one, two"
    assert _alias_names(None) == ""
    assert _alias_names([]) == ""


def test_alias_names_filters_non_strings() -> None:
    class _Sentinel:
        pass

    # Mirrors HA 2026.9's list[AliasEntry], where a non-str COMPUTED_NAME
    # sentinel can appear alongside the user-set string aliases.
    assert _alias_names(["beta", _Sentinel(), "alpha"]) == "alpha, beta"


def test_category_pairs_serializes_sorted() -> None:
    assert _category_pairs({"toys": "cat_1", "cleaning": "cat_2"}) == "cleaning:cat_2, toys:cat_1"
    assert _category_pairs({}) == ""
    assert _category_pairs(None) == ""


def test_sanitize_csv_value_prefixes_formula_chars() -> None:
    assert _sanitize_csv_value("=SUM(A1)") == "\t=SUM(A1)"
    assert _sanitize_csv_value("+1") == "\t+1"
    assert _sanitize_csv_value("-1") == "\t-1"
    assert _sanitize_csv_value("@formula") == "\t@formula"
    assert _sanitize_csv_value("\tstart") == "\t\tstart"


def test_sanitize_csv_value_leaves_safe_values() -> None:
    assert _sanitize_csv_value("normal text") == "normal text"
    assert _sanitize_csv_value("") == ""
    assert _sanitize_csv_value("123") == "123"


def test_export_options_want_disabled_and_hidden() -> None:
    default = ExportOptions()
    assert default.want_disabled is True
    assert default.want_hidden is True

    only_enabled = ExportOptions(only_enabled=True)
    assert only_enabled.want_disabled is False
    assert only_enabled.want_hidden is False

    exclude_disabled = ExportOptions(include_disabled=False)
    assert exclude_disabled.want_disabled is False


def test_export_options_area_matches() -> None:
    opts = ExportOptions(areas=frozenset(["kitchen_id", "Living Room"]))
    assert opts.area_matches("kitchen_id", None)
    assert opts.area_matches("any_id", "Living Room")
    assert not opts.area_matches("other_id", "Other Area")

    no_filter = ExportOptions()
    assert no_filter.area_matches("any", "any")
