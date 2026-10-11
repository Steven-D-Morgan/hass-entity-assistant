from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.entity_assistant.const import DOMAIN, SERVICE_IMPORT_CHANGES
from custom_components.entity_assistant.export import ExportOptions, build_export, rows_to_csv


def _write(hass: HomeAssistant, name: str, content: str) -> str:
    path = hass.config.path(name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write(content)
    return name


async def _call(hass: HomeAssistant, data: dict) -> dict:
    return await hass.services.async_call(
        DOMAIN, SERVICE_IMPORT_CHANGES, data, blocking=True, return_response=True
    )


def _seed_entity(hass: HomeAssistant) -> dict:
    integration = MockConfigEntry(domain="demo", title="Demo")
    integration.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    entity = ent_reg.async_get_or_create(
        "light", "demo", "lamp_1", config_entry=integration, original_name="Lamp"
    )
    return {"entity_id": entity.entity_id, "registry_id": entity.id}


async def test_update_entity_name_and_icon(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    content = f"registry_id,name,icon\n{seed['registry_id']},Reading Lamp,mdi:lamp\n"
    _write(hass, "import.csv", content)

    response = await _call(hass, {"filename": "import.csv", "confirm": True})

    assert response["dry_run"] is False
    assert response["counts"]["updated"] == 2
    entry = er.async_get(hass).async_get(seed["entity_id"])
    assert entry.name == "Reading Lamp"
    assert entry.icon == "mdi:lamp"


async def test_dry_run_default_makes_no_change(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    _write(hass, "import.csv", f"registry_id,name\n{seed['registry_id']},Changed\n")

    response = await _call(hass, {"filename": "import.csv"})

    assert response["dry_run"] is True
    assert response["counts"]["updated"] == 1
    assert len(response["updates"]) == 1
    entry = er.async_get(hass).async_get(seed["entity_id"])
    assert entry.name is None
    assert entry.original_name == "Lamp"


async def test_unchanged_roundtrip_is_empty_plan(hass: HomeAssistant, setup_integration) -> None:
    _seed_entity(hass)
    columns, rows = build_export(
        hass, ExportOptions(export_type="entities", include_disabled=True, include_hidden=True)
    )
    _write(hass, "roundtrip.csv", rows_to_csv(columns, rows))

    response = await _call(hass, {"filename": "roundtrip.csv", "confirm": True})

    assert response["counts"]["updated"] == 0
    assert response["counts"]["created"] == 0
    assert response["rows_matched"] == len(rows)
    assert response["rows_unmatched"] == 0


async def test_json_format_updates(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    content = f'[{{"registry_id": "{seed["registry_id"]}", "name": "From JSON"}}]'
    _write(hass, "import.json", content)

    response = await _call(hass, {"filename": "import.json", "confirm": True})

    assert response["import_type"] == "entities"
    assert er.async_get(hass).async_get(seed["entity_id"]).name == "From JSON"


async def test_clear_name_with_blank(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    er.async_get(hass).async_update_entity(seed["entity_id"], name="Override")
    _write(hass, "import.csv", f"registry_id,name\n{seed['registry_id']},\n")

    await _call(hass, {"filename": "import.csv", "confirm": True})

    assert er.async_get(hass).async_get(seed["entity_id"]).name is None


async def test_assign_area_by_id(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    area = ar.async_get(hass).async_create("Office")
    _write(hass, "import.csv", f"registry_id,area_id\n{seed['registry_id']},{area.id}\n")

    await _call(hass, {"filename": "import.csv", "confirm": True})

    assert er.async_get(hass).async_get(seed["entity_id"]).area_id == area.id


async def test_assign_area_by_name_autocreate(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    _write(hass, "import.csv", f"registry_id,area_name\n{seed['registry_id']},Garage\n")

    response = await _call(
        hass, {"filename": "import.csv", "create_missing": True, "confirm": True}
    )

    assert response["counts"]["created"] == 1
    new_area_id = response["created_ids"][0]
    assert ar.async_get(hass).async_get_area(new_area_id).name == "Garage"
    assert er.async_get(hass).async_get(seed["entity_id"]).area_id == new_area_id


async def test_labels_by_name_autocreate(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    _write(hass, "import.csv", f"registry_id,labels\n{seed['registry_id']},\"Cozy, Warm\"\n")

    response = await _call(
        hass, {"filename": "import.csv", "create_missing": True, "confirm": True}
    )

    assert response["counts"]["created"] == 2
    entry = er.async_get(hass).async_get(seed["entity_id"])
    label_reg = lr.async_get(hass)
    names = sorted(label_reg.async_get_label(lid).name for lid in entry.labels)
    assert names == ["Cozy", "Warm"]


async def test_labels_missing_without_create_warns(
    hass: HomeAssistant, setup_integration
) -> None:
    seed = _seed_entity(hass)
    _write(hass, "import.csv", f"registry_id,labels\n{seed['registry_id']},Nope\n")

    response = await _call(hass, {"filename": "import.csv", "confirm": True})

    assert response["counts"]["created"] == 0
    assert response["counts"]["updated"] == 0
    assert response["warning_count"] >= 1
    assert not er.async_get(hass).async_get(seed["entity_id"]).labels


async def test_entity_aliases_written_as_set(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    _write(hass, "import.csv", f'registry_id,aliases\n{seed["registry_id"]},"Reading, Desk"\n')

    await _call(hass, {"filename": "import.csv", "confirm": True})

    entry = er.async_get(hass).async_get(seed["entity_id"])
    assert isinstance(entry.aliases, set)
    assert entry.aliases == {"Reading", "Desk"}


async def test_area_aliases_written_as_set(hass: HomeAssistant, setup_integration) -> None:
    area = ar.async_get(hass).async_create("Den")
    _write(hass, "import.csv", f'area_id,aliases\n{area.id},"Lounge, Snug"\n')

    await _call(hass, {"filename": "import.csv", "confirm": True})

    updated = ar.async_get(hass).async_get_area(area.id)
    assert isinstance(updated.aliases, set)
    assert updated.aliases == {"Lounge", "Snug"}


async def test_blank_registry_id_matches_entity_id_with_warning(
    hass: HomeAssistant, setup_integration
) -> None:
    seed = _seed_entity(hass)
    _write(hass, "import.csv", f"registry_id,entity_id,name\n,{seed['entity_id']},Renamed\n")

    response = await _call(hass, {"filename": "import.csv", "confirm": True})

    assert response["warning_count"] >= 1
    assert er.async_get(hass).async_get(seed["entity_id"]).name == "Renamed"


async def test_area_name_casing_edit_is_noop(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    area = ar.async_get(hass).async_create("Office")
    er.async_get(hass).async_update_entity(seed["entity_id"], area_id=area.id)
    _write(hass, "import.csv", f"registry_id,area_name\n{seed['registry_id']},office\n")

    response = await _call(hass, {"filename": "import.csv", "confirm": True})

    assert response["counts"]["updated"] == 0


async def test_unknown_key_skipped_with_warning(hass: HomeAssistant, setup_integration) -> None:
    _seed_entity(hass)
    _write(hass, "import.csv", "registry_id,name\n01NONEXISTENT,Ghost\n")

    response = await _call(hass, {"filename": "import.csv", "confirm": True})

    assert response["rows_unmatched"] == 1
    assert response["counts"]["updated"] == 0
    assert response["warning_count"] >= 1


async def test_entity_id_fallback_warns(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    _write(hass, "import.csv", f"entity_id,name\n{seed['entity_id']},By Entity Id\n")

    response = await _call(hass, {"filename": "import.csv", "confirm": True})

    assert response["key_fallback"] is True
    assert response["warning_count"] >= 1
    assert er.async_get(hass).async_get(seed["entity_id"]).name == "By Entity Id"


async def test_ignores_readonly_columns(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    content = f"registry_id,state,stale,platform,name\n{seed['registry_id']},on,true,demo,Renamed\n"
    _write(hass, "import.csv", content)

    response = await _call(hass, {"filename": "import.csv", "confirm": True})

    assert response["counts"]["updated"] == 1
    assert er.async_get(hass).async_get(seed["entity_id"]).name == "Renamed"


async def test_device_name_by_user(hass: HomeAssistant, setup_integration) -> None:
    integration = MockConfigEntry(domain="demo", title="Demo")
    integration.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={("demo", "d1")},
        name="Factory Name",
    )
    _write(hass, "import.csv", f"device_id,name_by_user\n{device.id},My Device\n")

    response = await _call(hass, {"filename": "import.csv", "confirm": True})

    assert response["import_type"] == "devices"
    assert dr.async_get(hass).async_get(device.id).name_by_user == "My Device"


async def test_label_rename_and_color(hass: HomeAssistant, setup_integration) -> None:
    label = lr.async_get(hass).async_create("Old")
    _write(hass, "import.csv", f"label_id,name,color\n{label.label_id},New,red\n")

    await _call(hass, {"filename": "import.csv", "confirm": True})

    updated = lr.async_get(hass).async_get_label(label.label_id)
    assert updated.name == "New"
    assert updated.color == "red"


async def test_floor_level_and_name(hass: HomeAssistant, setup_integration) -> None:
    floor = fr.async_get(hass).async_create("Ground")
    _write(hass, "import.csv", f"floor_id,name,level\n{floor.floor_id},Main,2\n")

    response = await _call(hass, {"filename": "import.csv", "confirm": True})

    assert response["import_type"] == "floors"
    updated = fr.async_get(hass).async_get_floor(floor.floor_id)
    assert updated.name == "Main"
    assert updated.level == 2


async def test_area_floor_by_name_autocreate(hass: HomeAssistant, setup_integration) -> None:
    area = ar.async_get(hass).async_create("Kitchen")
    _write(hass, "import.csv", f"area_id,floor\n{area.id},Upstairs\n")

    response = await _call(
        hass, {"filename": "import.csv", "create_missing": True, "confirm": True}
    )

    assert response["counts"]["created"] == 1
    new_floor_id = response["created_ids"][0]
    assert fr.async_get(hass).async_get_floor(new_floor_id).name == "Upstairs"
    assert ar.async_get(hass).async_get_area(area.id).floor_id == new_floor_id


async def test_explicit_type_override(hass: HomeAssistant, setup_integration) -> None:
    label = lr.async_get(hass).async_create("Tag")
    _write(hass, "ambiguous.csv", f"label_id,name\n{label.label_id},Renamed\n")

    response = await _call(
        hass, {"filename": "ambiguous.csv", "import_type": "labels", "confirm": True}
    )

    assert response["import_type"] == "labels"
    assert lr.async_get(hass).async_get_label(label.label_id).name == "Renamed"


async def test_file_not_found_raises(hass: HomeAssistant, setup_integration) -> None:
    with pytest.raises(HomeAssistantError):
        await _call(hass, {"filename": "nope.csv", "confirm": True})


async def test_requires_admin(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_entity(hass)
    _write(hass, "import.csv", f"registry_id,name\n{seed['registry_id']},X\n")
    mock_user = MagicMock()
    mock_user.is_admin = False
    hass.auth.async_get_user = AsyncMock(return_value=mock_user)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_IMPORT_CHANGES,
            {"filename": "import.csv", "confirm": True},
            context=Context(user_id="non_admin"),
            blocking=True,
            return_response=True,
        )
