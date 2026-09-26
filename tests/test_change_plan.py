from __future__ import annotations

import json

import pytest

from custom_components.entity_assistant.change_plan import (
    ChangePlan,
    FieldChange,
    NewRef,
    ObjectCreate,
    ObjectRemove,
)


def test_set_values_serialize_sorted() -> None:
    plan = ChangePlan(
        producer="t",
        updates=[FieldChange("entity", "k", "labels", from_={"b", "a"}, to={"z", "a"})],
    )
    update = plan.to_response(dry_run=True)["updates"][0]
    assert update["from"] == ["a", "b"]
    assert update["to"] == ["a", "z"]


def test_none_value_preserved() -> None:
    plan = ChangePlan(
        producer="t",
        updates=[FieldChange("entity", "k", "area_id", from_="kitchen", to=None)],
    )
    assert plan.to_response(dry_run=True)["updates"][0]["to"] is None


def test_dict_value_passthrough() -> None:
    plan = ChangePlan(
        producer="t",
        updates=[FieldChange("entity", "k", "categories", from_={}, to={"scope": "c1"})],
    )
    assert plan.to_response(dry_run=True)["updates"][0]["to"] == {"scope": "c1"}


def test_newref_serializes_as_placeholder() -> None:
    plan = ChangePlan(
        producer="t",
        creates=[ObjectCreate("area", temp_ref="garage", fields={"name": "Garage"})],
        updates=[FieldChange("entity", "k", "area_id", from_=None, to=NewRef("garage"))],
    )
    resp = plan.to_response(dry_run=True)
    assert resp["updates"][0]["to"] == "new:garage"
    assert resp["creates"][0]["temp_ref"] == "garage"
    assert resp["creates"][0]["fields"]["name"] == "Garage"


def test_counts_and_object_types() -> None:
    plan = ChangePlan(
        producer="t",
        creates=[ObjectCreate("area", "g", {"name": "G"})],
        updates=[FieldChange("entity", "k", "name", from_="a", to="b")],
        removes=[ObjectRemove("entity", "sensor.x", "sensor.x")],
    )
    assert plan.counts() == {"created": 1, "updated": 1, "removed": 1}
    assert plan.object_types() == ["area", "entity"]
    assert plan.is_empty is False


def test_empty_plan() -> None:
    assert ChangePlan(producer="t").is_empty is True


def test_capping_and_truncated_flag() -> None:
    plan = ChangePlan(
        producer="t",
        updates=[FieldChange("entity", f"k{i}", "name", from_="", to=str(i)) for i in range(5)],
    )
    capped = plan.to_response(dry_run=True, cap=2)
    assert len(capped["updates"]) == 2
    assert capped["truncated"] is True
    assert capped["counts"]["updated"] == 5
    assert plan.to_response(dry_run=True)["truncated"] is False


def test_inverted_reverses_and_swaps_updates() -> None:
    plan = ChangePlan(
        producer="p",
        updates=[FieldChange("entity", f"k{i}", "name", from_="", to=str(i)) for i in range(3)],
    )
    inverted = plan.inverted()
    assert inverted.producer == "undo:p"
    assert [change.key for change in inverted.updates] == ["k2", "k1", "k0"]
    assert inverted.updates[0].from_ == "2"
    assert inverted.updates[0].to == ""
    assert inverted.removes == []


def test_to_file_payload_is_uncapped() -> None:
    plan = ChangePlan(
        producer="p",
        removes=[ObjectRemove("entity", f"e{i}", f"e{i}") for i in range(10)],
    )
    payload = plan.to_file_payload()
    assert len(payload["removes"]) == 10
    assert payload["truncated"] is False


def test_response_is_json_serializable() -> None:
    plan = ChangePlan(
        producer="p",
        creates=[ObjectCreate("area", "g", {"name": "G", "labels": {"a", "b"}})],
        updates=[FieldChange("entity", "k", "area_id", from_=None, to=NewRef("g"))],
        removes=[ObjectRemove("device", "d1", "Device 1")],
    )
    json.dumps(plan.to_response(dry_run=True))


def test_unknown_object_type_rejected() -> None:
    with pytest.raises(ValueError):
        FieldChange("widget", "k", "name", from_=None, to="x")


def test_non_creatable_rejected() -> None:
    with pytest.raises(ValueError):
        ObjectCreate("entity", "t", {"name": "x"})


def test_create_requires_name() -> None:
    with pytest.raises(ValueError):
        ObjectCreate("area", "t", {"icon": "mdi:home"})


def test_non_removable_rejected() -> None:
    with pytest.raises(ValueError):
        ObjectRemove("floor", "k", "l")
