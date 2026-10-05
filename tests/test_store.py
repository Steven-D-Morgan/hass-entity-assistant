from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import Context, HomeAssistant
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

from custom_components.entity_assistant import spine
from custom_components.entity_assistant.change_plan import ChangePlan, FieldChange, json_safe
from custom_components.entity_assistant.const import (
    DATA_STORE,
    DEFAULT_KEEP_JOURNAL,
    DEFAULT_KEEP_SNAPSHOTS,
    DOMAIN,
    OBJECT_ENTITY,
    OBJECT_LABEL,
    SERVICE_CAPTURE_SNAPSHOT,
)
from custom_components.entity_assistant.store import EntityAssistantStore


def _seed_writable(hass: HomeAssistant) -> dict:
    integration = MockConfigEntry(domain="store_test", title="Store")
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
        identifiers={("store_test", "d1")},
        name="Lamp Device",
    )
    entity = ent_reg.async_get_or_create(
        "light",
        "store_test",
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


def _rename_label_plan(label_id: str, to: str, *, frm: str = "Cozy") -> ChangePlan:
    return ChangePlan(
        producer="test",
        updates=[FieldChange(OBJECT_LABEL, label_id, "name", from_=frm, to=to)],
    )


async def test_store_present_and_empty_after_setup(
    hass: HomeAssistant, setup_integration
) -> None:
    store = hass.data[DATA_STORE]
    assert isinstance(store, EntityAssistantStore)
    assert store._snapshots == []
    assert store._journals == []


async def test_load_tolerates_missing_file(hass: HomeAssistant, setup_integration) -> None:
    fresh = EntityAssistantStore(hass, setup_integration)
    await fresh.async_load()
    assert fresh._snapshots == []
    assert fresh._journals == []


async def test_commit_creates_auto_snapshot(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_writable(hass)
    store = hass.data[DATA_STORE]

    await spine.async_commit_plan(
        hass, _rename_label_plan(seed["label_id"], "Warm"), triggered_by="test"
    )

    assert len(store._snapshots) == 1
    record = store._snapshots[0]
    assert record["trigger"] == "auto"
    assert record["producer"] == "test"
    assert record["object_types"] == ["labels"]


async def test_auto_snapshot_captures_pre_mutation_state(
    hass: HomeAssistant, setup_integration
) -> None:
    seed = _seed_writable(hass)
    store = hass.data[DATA_STORE]

    await spine.async_commit_plan(
        hass, _rename_label_plan(seed["label_id"], "Warm"), triggered_by="test"
    )

    assert lr.async_get(hass).async_get_label(seed["label_id"]).name == "Warm"
    rows = store._snapshots[0]["data"]["labels"]["rows"]
    captured = next(row for row in rows if row["label_id"] == seed["label_id"])
    assert captured["name"] == "Cozy"


async def test_dry_run_preview_creates_no_snapshot(
    hass: HomeAssistant, setup_integration
) -> None:
    seed = _seed_writable(hass)
    store = hass.data[DATA_STORE]

    plan = _rename_label_plan(seed["label_id"], "Warm")
    plan.to_response(dry_run=True)

    assert store._snapshots == []
    assert lr.async_get(hass).async_get_label(seed["label_id"]).name == "Cozy"


async def test_commit_records_journal_with_real_id(
    hass: HomeAssistant, setup_integration
) -> None:
    seed = _seed_writable(hass)
    store = hass.data[DATA_STORE]

    result = await spine.async_commit_plan(
        hass, _rename_label_plan(seed["label_id"], "Warm"), triggered_by="test"
    )

    assert result.journal_id is not None
    assert len(store._journals) == 1
    record = store._journals[0]
    assert record["journal_id"] == result.journal_id
    assert record["producer"] == "test"
    change = record["changes"][0]
    assert change["from"] == "Cozy"
    assert change["to"] == "Warm"


async def test_journal_sanitizes_set_before_values(
    hass: HomeAssistant, setup_integration
) -> None:
    seed = _seed_writable(hass)
    store = hass.data[DATA_STORE]

    plan = ChangePlan(
        producer="test",
        updates=[
            FieldChange(
                OBJECT_ENTITY,
                seed["registry_id"],
                "labels",
                from_=set(),
                to={seed["label_id"]},
            )
        ],
    )
    await spine.async_commit_plan(hass, plan, triggered_by="test")

    change = store._journals[0]["changes"][0]
    assert isinstance(change["from"], list)
    assert isinstance(change["to"], list)
    assert change["to"] == [seed["label_id"]]
    assert er.async_get(hass).async_get(seed["entity_id"]).labels == {seed["label_id"]}


async def test_journal_survives_reload(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_writable(hass)
    store = hass.data[DATA_STORE]

    await spine.async_commit_plan(
        hass, _rename_label_plan(seed["label_id"], "Warm"), triggered_by="test"
    )
    await store.async_save_now()

    reloaded = EntityAssistantStore(hass, setup_integration)
    await reloaded.async_load()
    assert len(reloaded._journals) == 1
    assert reloaded._journals[0]["changes"][0]["from"] == "Cozy"


async def test_snapshot_survives_reload(hass: HomeAssistant, setup_integration) -> None:
    _seed_writable(hass)
    store = hass.data[DATA_STORE]

    await store.async_capture_snapshot(label="baseline", export_types=None, context=None)

    reloaded = EntityAssistantStore(hass, setup_integration)
    await reloaded.async_load()
    assert len(reloaded._snapshots) == 1
    assert reloaded._snapshots[0]["label"] == "baseline"


async def test_keep_last_n_snapshots(hass: HomeAssistant, setup_integration) -> None:
    store = hass.data[DATA_STORE]

    for i in range(DEFAULT_KEEP_SNAPSHOTS + 3):
        await store.async_capture_snapshot(label=f"s{i}", export_types=["labels"], context=None)

    assert len(store._snapshots) == DEFAULT_KEEP_SNAPSHOTS
    assert store._snapshots[0]["label"] == f"s{3}"
    assert store._snapshots[-1]["label"] == f"s{DEFAULT_KEEP_SNAPSHOTS + 2}"


async def test_keep_last_n_journals(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_writable(hass)
    store = hass.data[DATA_STORE]

    for i in range(DEFAULT_KEEP_JOURNAL + 2):
        await spine.async_commit_plan(
            hass,
            _rename_label_plan(seed["label_id"], f"N{i}", frm=f"prev{i}"),
            triggered_by="test",
        )

    assert len(store._journals) == DEFAULT_KEEP_JOURNAL


async def test_retention_reapplied_on_load(hass: HomeAssistant, setup_integration) -> None:
    store = hass.data[DATA_STORE]
    store._snapshots = [{"snapshot_id": str(i)} for i in range(DEFAULT_KEEP_SNAPSHOTS + 4)]
    await store.async_save_now()

    reloaded = EntityAssistantStore(hass, setup_integration)
    await reloaded.async_load()
    assert len(reloaded._snapshots) == DEFAULT_KEEP_SNAPSHOTS


async def test_capture_snapshot_service_returns_summary(
    hass: HomeAssistant, setup_integration
) -> None:
    _seed_writable(hass)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CAPTURE_SNAPSHOT,
        {"label": "before relabel"},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    assert response["trigger"] == "manual"
    assert response["label"] == "before relabel"
    assert set(response["object_types"]) == {"entities", "devices", "areas", "floors", "labels"}
    assert response["total_rows"] == sum(response["counts"].values())
    assert response["kept"] == 1


async def test_capture_snapshot_subset_of_types(
    hass: HomeAssistant, setup_integration
) -> None:
    _seed_writable(hass)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CAPTURE_SNAPSHOT,
        {"export_types": ["labels"]},
        blocking=True,
        return_response=True,
    )
    assert response["object_types"] == ["labels"]
    assert set(response["counts"]) == {"labels"}


async def test_capture_snapshot_non_admin_rejected(
    hass: HomeAssistant, setup_integration
) -> None:
    mock_user = MagicMock()
    mock_user.is_admin = False
    hass.auth.async_get_user = AsyncMock(return_value=mock_user)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CAPTURE_SNAPSHOT,
            {},
            context=Context(user_id="non_admin"),
            blocking=True,
            return_response=True,
        )


async def test_capture_snapshot_admin_allowed(
    hass: HomeAssistant, setup_integration
) -> None:
    mock_user = MagicMock()
    mock_user.is_admin = True
    hass.auth.async_get_user = AsyncMock(return_value=mock_user)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CAPTURE_SNAPSHOT,
        {},
        context=Context(user_id="admin"),
        blocking=True,
        return_response=True,
    )
    assert response is not None


async def test_capture_snapshot_system_call_allowed(
    hass: HomeAssistant, setup_integration
) -> None:
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CAPTURE_SNAPSHOT,
        {},
        blocking=True,
        return_response=True,
    )
    assert response is not None


async def test_capture_snapshot_unknown_user_rejected(
    hass: HomeAssistant, setup_integration
) -> None:
    hass.auth.async_get_user = AsyncMock(return_value=None)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CAPTURE_SNAPSHOT,
            {},
            context=Context(user_id="ghost"),
            blocking=True,
            return_response=True,
        )


async def test_async_remove_clears_store(hass: HomeAssistant, setup_integration) -> None:
    store = hass.data[DATA_STORE]
    await store.async_capture_snapshot(label="x", export_types=["labels"], context=None)
    assert len(store._snapshots) == 1

    await store.async_remove()
    assert store._snapshots == []
    assert store._journals == []

    reloaded = EntityAssistantStore(hass, setup_integration)
    await reloaded.async_load()
    assert reloaded._snapshots == []


def test_json_safe_coerces_native_types() -> None:
    assert json_safe({"b", "a"}) == ["a", "b"]
    assert json_safe((1, 2)) == [1, 2]
    assert json_safe({"k": {"x", "y"}}) == {"k": ["x", "y"]}
    assert json_safe(None) is None
    assert json_safe("plain") == "plain"
