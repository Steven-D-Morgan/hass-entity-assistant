from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import Context, HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.entity_assistant import spine
from custom_components.entity_assistant.change_plan import (
    ChangePlan,
    FieldChange,
    NewRef,
    ObjectCreate,
    ObjectRemove,
)
from custom_components.entity_assistant.const import (
    DOMAIN,
    EVENT_CHANGES_APPLIED,
    OBJECT_AREA,
    OBJECT_DEVICE,
    OBJECT_ENTITY,
    OBJECT_FLOOR,
    OBJECT_LABEL,
)


def _seed_writable(hass: HomeAssistant) -> dict:
    integration = MockConfigEntry(domain="spine_test", title="Spine")
    integration.add_to_hass(hass)
    floor_reg = fr.async_get(hass)
    area_reg = ar.async_get(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    label_reg = lr.async_get(hass)

    floor = floor_reg.async_create("Ground")
    area = area_reg.async_create("Living Room")
    label = label_reg.async_create("Cozy")
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={("spine_test", "d1")},
        name="Lamp Device",
    )
    entity = ent_reg.async_get_or_create(
        "light",
        "spine_test",
        "lamp_1",
        config_entry=integration,
        device_id=device.id,
        original_name="Lamp",
    )
    return {
        "floor_id": floor.floor_id,
        "area_id": area.id,
        "label_id": label.label_id,
        "device_id": device.id,
        "entity_id": entity.entity_id,
        "registry_id": entity.id,
    }


async def test_commit_updates_all_object_types(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_writable(hass)
    plan = ChangePlan(
        producer="test",
        updates=[
            FieldChange(
                OBJECT_ENTITY, seed["registry_id"], "name", from_="Lamp", to="Reading Lamp"
            ),
            FieldChange(OBJECT_DEVICE, seed["device_id"], "name_by_user", from_=None, to="Corner"),
            FieldChange(OBJECT_AREA, seed["area_id"], "name", from_="Living Room", to="Lounge"),
            FieldChange(OBJECT_FLOOR, seed["floor_id"], "level", from_=None, to=2),
            FieldChange(OBJECT_LABEL, seed["label_id"], "name", from_="Cozy", to="Warm"),
        ],
    )

    result = await spine.async_commit_plan(hass, plan, triggered_by="test")

    assert result.counts()["updated"] == 5
    assert result.counts()["failed"] == 0
    assert er.async_get(hass).async_get(seed["entity_id"]).name == "Reading Lamp"
    assert dr.async_get(hass).async_get(seed["device_id"]).name_by_user == "Corner"
    assert ar.async_get(hass).async_get_area(seed["area_id"]).name == "Lounge"
    assert fr.async_get(hass).async_get_floor(seed["floor_id"]).level == 2
    assert lr.async_get(hass).async_get_label(seed["label_id"]).name == "Warm"


async def test_commit_resolves_entity_ulid(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_writable(hass)
    plan = ChangePlan(
        producer="test",
        updates=[
            FieldChange(OBJECT_ENTITY, seed["registry_id"], "icon", from_=None, to="mdi:lamp")
        ],
    )

    result = await spine.async_commit_plan(hass, plan, triggered_by="test")

    assert result.counts()["updated"] == 1
    assert er.async_get(hass).async_get(seed["entity_id"]).icon == "mdi:lamp"


async def test_commit_captures_before_values(
    hass: HomeAssistant, setup_integration, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = _seed_writable(hass)
    captured: dict = {}

    async def fake_journal(hass, producer, batch, context) -> str:
        captured["producer"] = producer
        captured["batch"] = batch
        return "journal-1"

    monkeypatch.setattr(spine, "async_record_journal", fake_journal)

    plan = ChangePlan(
        producer="test",
        updates=[FieldChange(OBJECT_LABEL, seed["label_id"], "name", from_="ignored", to="Warm")],
    )
    result = await spine.async_commit_plan(hass, plan, triggered_by="test")

    assert result.journal_id == "journal-1"
    assert captured["producer"] == "test"
    assert captured["batch"][0]["from"] == "Cozy"
    assert captured["batch"][0]["to"] == "Warm"


async def test_commit_create_and_newref(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_writable(hass)
    plan = ChangePlan(
        producer="test",
        creates=[ObjectCreate(OBJECT_AREA, temp_ref="garage", fields={"name": "Garage"})],
        updates=[
            FieldChange(
                OBJECT_ENTITY, seed["registry_id"], "area_id", from_=None, to=NewRef("garage")
            )
        ],
    )

    result = await spine.async_commit_plan(hass, plan, triggered_by="test")

    assert result.counts()["created"] == 1
    assert result.counts()["updated"] == 1
    new_area_id = result.created_ids[0]
    assert ar.async_get(hass).async_get_area(new_area_id).name == "Garage"
    assert er.async_get(hass).async_get(seed["entity_id"]).area_id == new_area_id


async def test_commit_removes(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_writable(hass)
    plan = ChangePlan(
        producer="test",
        removes=[
            ObjectRemove(OBJECT_ENTITY, key=seed["entity_id"], label=seed["entity_id"]),
            ObjectRemove(OBJECT_DEVICE, key=seed["device_id"], label="Lamp Device"),
            ObjectRemove(OBJECT_AREA, key=seed["area_id"], label="Living Room"),
        ],
    )

    result = await spine.async_commit_plan(hass, plan, triggered_by="test")

    assert result.counts()["removed"] == 3
    assert er.async_get(hass).async_get(seed["entity_id"]) is None
    assert dr.async_get(hass).async_get(seed["device_id"]) is None
    assert ar.async_get(hass).async_get_area(seed["area_id"]) is None


async def test_commit_chunking_applies_all(hass: HomeAssistant, setup_integration) -> None:
    _seed_writable(hass)
    label_reg = lr.async_get(hass)
    labels = [label_reg.async_create(f"L{i}") for i in range(5)]
    plan = ChangePlan(
        producer="test",
        updates=[
            FieldChange(OBJECT_LABEL, label.label_id, "name", from_=label.name, to=f"R{i}")
            for i, label in enumerate(labels)
        ],
    )

    result = await spine.async_commit_plan(hass, plan, triggered_by="test", chunk_size=2)

    assert result.counts()["updated"] == 5
    for i, label in enumerate(labels):
        assert label_reg.async_get_label(label.label_id).name == f"R{i}"


async def test_commit_partial_failure_is_best_effort(
    hass: HomeAssistant, setup_integration
) -> None:
    seed = _seed_writable(hass)
    plan = ChangePlan(
        producer="test",
        updates=[
            FieldChange(OBJECT_LABEL, seed["label_id"], "name", from_="Cozy", to="Warm"),
            FieldChange(OBJECT_LABEL, "does_not_exist", "name", from_="x", to="y"),
        ],
    )

    result = await spine.async_commit_plan(hass, plan, triggered_by="test")

    assert result.counts()["updated"] == 1
    assert result.counts()["failed"] == 1
    assert result.errors[0]["object_type"] == "label"
    assert result.errors[0]["key"] == "does_not_exist"
    assert lr.async_get(hass).async_get_label(seed["label_id"]).name == "Warm"


async def test_changes_applied_event_fires(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_writable(hass)
    events = []
    hass.bus.async_listen(EVENT_CHANGES_APPLIED, events.append)

    plan = ChangePlan(
        producer="test",
        updates=[FieldChange(OBJECT_LABEL, seed["label_id"], "name", from_="Cozy", to="Warm")],
    )
    await spine.async_commit_plan(hass, plan, triggered_by="test")
    await hass.async_block_till_done()

    assert len(events) == 1
    data = events[0].data
    assert data["producer"] == "test"
    assert data["triggered_by"] == "test"
    assert data["counts"]["updated"] == 1
    assert data["object_types"] == ["label"]


async def test_handle_mutation_previews_then_applies(
    hass: HomeAssistant, setup_integration
) -> None:
    seed = _seed_writable(hass)

    def compile_fn(call_hass: HomeAssistant, call: ServiceCall) -> ChangePlan:
        return ChangePlan(
            producer="probe",
            updates=[
                FieldChange(OBJECT_LABEL, seed["label_id"], "name", from_="Cozy", to="Renamed")
            ],
        )

    async def handler(call: ServiceCall):
        return await spine.async_handle_mutation(hass, call, compile_fn)

    hass.services.async_register(
        DOMAIN,
        "spine_probe",
        handler,
        schema=vol.Schema({**spine.MUTATION_FIELDS}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    label_reg = lr.async_get(hass)

    preview = await hass.services.async_call(
        DOMAIN, "spine_probe", {}, blocking=True, return_response=True
    )
    assert preview["dry_run"] is True
    assert preview["counts"]["updated"] == 1
    assert label_reg.async_get_label(seed["label_id"]).name == "Cozy"

    applied = await hass.services.async_call(
        DOMAIN, "spine_probe", {"confirm": True}, blocking=True, return_response=True
    )
    assert applied["dry_run"] is False
    assert label_reg.async_get_label(seed["label_id"]).name == "Renamed"


async def test_handle_mutation_requires_admin(hass: HomeAssistant, setup_integration) -> None:
    _seed_writable(hass)

    def compile_fn(call_hass: HomeAssistant, call: ServiceCall) -> ChangePlan:
        return ChangePlan(producer="probe")

    async def handler(call: ServiceCall):
        return await spine.async_handle_mutation(hass, call, compile_fn)

    hass.services.async_register(
        DOMAIN,
        "spine_probe_admin",
        handler,
        schema=vol.Schema({**spine.MUTATION_FIELDS}),
        supports_response=SupportsResponse.OPTIONAL,
    )

    mock_user = MagicMock()
    mock_user.is_admin = False
    hass.auth.async_get_user = AsyncMock(return_value=mock_user)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "spine_probe_admin",
            {"confirm": True},
            context=Context(user_id="non_admin"),
            blocking=True,
            return_response=True,
        )
