from __future__ import annotations

import json

from homeassistant.core import HomeAssistant

from custom_components.entity_assistant.const import (
    DEFAULT_EXPIRES,
    DEFAULT_EXPORT_TYPE,
    DEFAULT_STALE_DAYS,
    DOWNLOAD_URL,
)
from custom_components.entity_assistant.http import options_from_query


def test_options_from_query_defaults() -> None:
    options = options_from_query({})
    assert options.export_type == DEFAULT_EXPORT_TYPE
    assert options.include_disabled is True
    assert options.include_hidden is True
    assert options.only_enabled is False
    assert options.domains is None
    assert options.areas is None
    assert options.stale_only is False
    assert options.stale_days == DEFAULT_STALE_DAYS
    assert options.utf8_bom is False
    assert options.output_format == "csv"
    assert options.sort_by is None
    assert options.sort_dir == "asc"


def test_options_from_query_all_params() -> None:
    query = {
        "export_type": "devices",
        "include_disabled": "false",
        "include_hidden": "false",
        "only_enabled": "true",
        "domains": "light,switch",
        "areas": "living,kitchen",
        "stale_only": "true",
        "stale_days": "14",
        "utf8_bom": "true",
        "output_format": "json",
        "sort_by": "name",
        "sort_dir": "desc",
    }
    options = options_from_query(query)
    assert options.export_type == "devices"
    assert options.include_disabled is False
    assert options.include_hidden is False
    assert options.only_enabled is True
    assert options.domains == frozenset(["light", "switch"])
    assert options.areas == frozenset(["living", "kitchen"])
    assert options.stale_only is True
    assert options.stale_days == 14
    assert options.utf8_bom is True
    assert options.output_format == "json"
    assert options.sort_by == "name"
    assert options.sort_dir == "desc"


def test_options_from_query_invalid_export_type_falls_back() -> None:
    options = options_from_query({"export_type": "bogus"})
    assert options.export_type == DEFAULT_EXPORT_TYPE


def test_options_from_query_invalid_output_format_falls_back() -> None:
    options = options_from_query({"output_format": "bogus"})
    assert options.output_format == "csv"


def test_options_from_query_invalid_sort_dir_falls_back() -> None:
    options = options_from_query({"sort_dir": "bogus"})
    assert options.sort_dir == "asc"


def test_options_from_query_bool_variations() -> None:
    for false_val in ("false", "0", "no", "FALSE", "No"):
        assert options_from_query({"only_enabled": false_val}).only_enabled is False
    for true_val in ("true", "1", "yes", "anything"):
        assert options_from_query({"only_enabled": true_val}).only_enabled is True


def test_options_from_query_negative_int_falls_back() -> None:
    options = options_from_query({"stale_days": "-5"})
    assert options.stale_days == DEFAULT_STALE_DAYS


def test_options_from_query_invalid_int_falls_back() -> None:
    options = options_from_query({"stale_days": "not_a_number"})
    assert options.stale_days == DEFAULT_STALE_DAYS


def test_options_from_query_empty_list_params() -> None:
    options = options_from_query({"domains": "", "areas": " , , "})
    assert options.domains is None
    assert options.areas is None


def test_default_expires_hardened() -> None:
    assert DEFAULT_EXPIRES == 120


async def test_download_requires_auth(
    hass: HomeAssistant, setup_integration, hass_client_no_auth
) -> None:
    client = await hass_client_no_auth()
    resp = await client.get(DOWNLOAD_URL)
    assert resp.status == 401


async def test_download_returns_csv(hass: HomeAssistant, setup_integration, hass_client) -> None:
    client = await hass_client()
    resp = await client.get(DOWNLOAD_URL)
    assert resp.status == 200
    assert resp.content_type == "text/csv"
    body = await resp.text()
    assert "entity_id" in body.splitlines()[0]


async def test_download_cache_control_header(
    hass: HomeAssistant, setup_integration, hass_client
) -> None:
    client = await hass_client()
    resp = await client.get(DOWNLOAD_URL)
    assert resp.headers.get("Cache-Control") == "no-store"


async def test_download_content_disposition(
    hass: HomeAssistant, setup_integration, hass_client
) -> None:
    client = await hass_client()
    resp = await client.get(DOWNLOAD_URL)
    disposition = resp.headers.get("Content-Disposition", "")
    assert "attachment" in disposition
    assert ".csv" in disposition


async def test_download_export_type_query(
    hass: HomeAssistant, setup_integration, hass_client
) -> None:
    client = await hass_client()
    resp = await client.get(f"{DOWNLOAD_URL}?export_type=devices")
    assert resp.status == 200
    body = await resp.text()
    assert body.splitlines()[0].startswith("device_id")


async def test_download_json_format(hass: HomeAssistant, setup_integration, hass_client) -> None:
    client = await hass_client()
    resp = await client.get(f"{DOWNLOAD_URL}?output_format=json")
    assert resp.status == 200
    assert resp.content_type == "application/json"
    disposition = resp.headers.get("Content-Disposition", "")
    assert ".json" in disposition
    data = json.loads(await resp.text())
    assert isinstance(data, list)


async def test_download_yaml_format(hass: HomeAssistant, setup_integration, hass_client) -> None:
    client = await hass_client()
    resp = await client.get(f"{DOWNLOAD_URL}?output_format=yaml")
    assert resp.status == 200
    assert resp.content_type == "application/yaml"
    disposition = resp.headers.get("Content-Disposition", "")
    assert ".yaml" in disposition
