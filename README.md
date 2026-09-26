<div align="center">

<img src="entity-assistant.jpg" alt="Entity Assistant" width="180">

# Entity Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/Steven-D-Morgan/hass-entity-assistant?style=for-the-badge&color=41BDF5&label=Release)](https://github.com/Steven-D-Morgan/hass-entity-assistant/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Steven-D-Morgan/hass-entity-assistant/total?style=for-the-badge&color=41BDF5&label=Downloads)](https://github.com/Steven-D-Morgan/hass-entity-assistant/releases)

A Home Assistant custom integration that exports your registry — entities,
devices, or areas — to a CSV file, complete with `entity_id`, area, floor,
labels, device metadata, current state, and more. Also identifies and removes
orphaned entities, orphaned devices, and empty areas.

</div>

## What it exports

Choose an `export_type`: **entities** (default), **devices**, **areas**,
**floors**, or **labels**.

### Entities (one row per entity)

| Column | Description |
| --- | --- |
| `entity_id` | The entity ID (e.g. `light.kitchen`) |
| `registry_id` | Stable registry ULID — survives an `entity_id` rename; the round-trip key |
| `name` | Friendly name (user override, falling back to the original) |
| `original_name` | Name assigned by the integration |
| `icon` | Icon override (`mdi:…`), blank if none set |
| `platform` | Integration that created the entity (e.g. `hue`, `mqtt`) |
| `config_entry` | Title of the config entry it belongs to |
| `device_id` | Registry ID of the parent device |
| `device_name` | Device name (user override, falling back to the original) |
| `device_manufacturer` | Device manufacturer |
| `device_model` | Device model |
| `area_id` | Effective area ID (entity override, falling back to the device) |
| `area_name` | Effective area name |
| `floor` | Floor the area belongs to |
| `labels` | Labels assigned to the entity |
| `aliases` | Voice/Assist aliases, `", "`-joined |
| `categories` | Category assignments as `scope:category_id`, `", "`-joined |
| `entity_category` | `config`, `diagnostic`, or blank |
| `device_class` | Device class (e.g. `temperature`, `motion`) |
| `unit_of_measurement` | Unit, if any |
| `state` | Current state at export time |
| `available` | `true`/`false` (blank if not currently provided) |
| `last_changed` | When the state last changed (ISO 8601) |
| `last_changed_days` | Days since the last state change |
| `stale` | `true` if flagged stale (see below) |
| `stale_reason` | Why it's stale — e.g. `unavailable, orphaned` |
| `enabled` | `true` / `false` |
| `disabled_by` | Why it's disabled, if applicable |
| `hidden_by` | Why it's hidden, if applicable |
| `unique_id` | Integration-assigned unique ID |

### Devices (one row per device, including devices with no entities)

`device_id`, `name`, `name_by_user`, `manufacturer`, `model`, `sw_version`,
`hw_version`, `area_id`, `area_name`, `floor`, `labels`, `config_entries`,
`via_device_id`, `entity_count`, `available_entity_count`, `disabled_by`,
`stale`, `stale_reason`.

### Areas (one row per area)

`area_id`, `name`, `icon`, `floor_id`, `floor`, `labels`, `aliases`,
`device_count`, `entity_count`, `picture`, `stale`, `stale_reason`.

### Floors (one row per floor)

`floor_id`, `name`, `level`, `icon`, `aliases`, `area_count` (number of areas
assigned to the floor).

### Labels (one row per label)

`label_id`, `name`, `color`, `icon`, `description`, `entity_count`,
`device_count`, `area_count` (how many entities, devices, and areas the label is
assigned to — `0` across all three means the label is unused).

> **Multi-value columns** (`labels`, `aliases`, `categories`) are joined with
> `", "` in CSV. A label or alias that itself contains a comma is therefore
> ambiguous to split back apart — a CSV limitation; the `json`/`yaml`
> `output_format`s round-trip these losslessly.

Floors and labels have no `stale` flag — filter on `area_count` (or the label
usage counts) being `0` to find unused ones.

### Finding stale entities/devices

Every export includes a `stale` flag and a `stale_reason` column that spells out
*why* something is flagged, so you can sort/filter in your spreadsheet or pull
only the offenders with `stale_only: true`.

| Export type | `stale_reason` values |
| --- | --- |
| entities | `unavailable` (state is unavailable/unknown), `orphaned` (its config entry/integration is gone), `restored` (in the registry but not provided since the last restart), `not_changed_<N>d` (no state change in `stale_days` days) |
| devices | `orphaned` (all config entries gone), `no_entities`, `all_unavailable` |
| areas | `empty` (no devices or entities) |

`stale_days` (default 30) controls the `not_changed_<N>d` threshold. A row can
have multiple reasons, comma-separated.

## Installation

### Via HACS (recommended)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/Steven-D-Morgan/hass-entity-assistant` with category
   **Integration**.
3. Search for **Entity Assistant** in HACS, install it, and restart Home
   Assistant.
4. Continue with **Add the integration** below.

Once this repository is added to the
[HACS default store](https://hacs.xyz/), steps 1–2 won't be needed — you'll be
able to find it directly.

### Manual

1. Copy the `custom_components/entity_assistant` folder into your Home Assistant
   `config/custom_components/` directory. The result should be
   `config/custom_components/entity_assistant/`.
2. Restart Home Assistant.

### Add the integration

Go to **Settings → Devices & Services → Add Integration**, search for
**Entity Assistant**, and add it. (It's a single-instance integration with no
configuration — this just registers the export service and shows the card in
your integrations list.)

## Using it

Four ways to export, all sharing the [options](#options) below:

- **Export entity list** button — one click. Press **Configure** on the
  integration to set its defaults (export type, filename, output format, the
  filters, UTF-8 BOM); they apply on the next press, no reload.
- **`export_csv`** service — for automations and scripts. Writes a file and
  returns `{path, row_count}`, or set `return_data: true` to get
  `{columns, rows, row_count, truncated}` back with no file written.
- **`get_download_url`** service — returns a signed, time-limited URL for a
  no-auth dashboard or browser download. Adds `expires` and `download_filename`.
  Response only.
- **HTTP endpoint** at `/api/entity_assistant/export.csv` — authenticated
  (signed URL, or a [long-lived token](https://www.home-assistant.io/docs/authentication/#your-account-profile)).
  Every option below works as a query flag (multi-value ones comma-separated).

**Registry cleanup:** the **Export orphaned entities** button writes only the
stale rows to `entity_export_stale.csv`, and the admin-only **`remove_orphaned`**
service previews by default (`dry_run: true`) or deletes orphaned
entities/devices and empty areas with `confirm: true` (returns counts + ID
lists). Removals aren't undoable — back up first.

> **Worked examples** — filtered exports, JSON/YAML, column presets, sorting,
> dashboard download links, inline template-sensor data, and orphan cleanup —
> are in **[COOKBOOK.md](COOKBOOK.md)**.

### Options

All optional. Shared by `export_csv`, `get_download_url`, and the HTTP endpoint
unless a row says otherwise.

| Field | Default | Description |
| --- | --- | --- |
| `export_type` | `entities` | `entities`, `devices`, `areas`, `floors`, or `labels` |
| `output_format` | `csv` | `csv`, `json`, or `yaml`; JSON/YAML are lossless (values verbatim, no BOM/formula guard) and set the download `Content-Type`/extension |
| `columns` | — | Ordered subset of columns; unknown names dropped, full set used if none valid. Overrides `preset` |
| `preset` | — | Named set: `minimal` (all types), `identity` (entities), `stale` (entities/devices) |
| `sort_by` / `sort_dir` | — / `asc` | Sort by any column, `asc`/`desc` (stable, sorts as text) |
| `include_disabled` | `true` | Include disabled entities/devices |
| `include_hidden` | `true` | Include hidden entities |
| `only_enabled` | `false` | Exclude everything disabled/hidden |
| `domains` | — | Only these entity domains (entities type) |
| `areas` | — | Only these areas (by area id or name) |
| `stale_only` | `false` | Only rows flagged stale (see [above](#finding-stale-entitiesdevices)) |
| `stale_days` | `30` | Threshold for the `not_changed_<N>d` reason |
| `utf8_bom` | `false` | UTF-8 BOM so Excel on Windows renders non-ASCII (CSV only) |
| `filename` | `entity_export.csv` | **`export_csv` only** — output path in the config dir; subfolders auto-created; keep inside the config dir |
| `return_data` / `max_rows` | `false` / `1000` | **`export_csv` only** — return rows inline instead of writing a file, capped at `max_rows` |
| `expires` | `300` | **`get_download_url` only** — signed-URL lifetime (seconds) |
| `download_filename` | — | **`get_download_url` / HTTP** — browser save name; sanitized to a basename, extension from `output_format` |

## Automations

- **`last_export` sensor** — a timestamp sensor on the Entity Assistant device,
  updated on every successful export, with `row_count`, `path`, `export_type`,
  and `triggered_by` attributes. If an export fails, the state stays pinned to
  the last successful timestamp and four additional attributes appear:
  `last_error`, `last_error_at`, `last_error_type`, and
  `last_error_triggered_by`.
- **`entity_assistant_export_completed` event** — fired after each successful
  export with `path`, `row_count`, `export_type`, and `triggered_by`. Use it
  to, e.g., email the file once it's written.
- **`entity_assistant_export_failed` event** — fired after each failed export
  with `path`, `error`, `error_type`, `export_type`, and `triggered_by`. Use
  it to alert on disk-full or permission problems without scraping the log.
- **`entity_assistant_orphaned_removed` event** — fired after each removal with
  `entities_removed`, `devices_removed`, `areas_removed`, and the corresponding
  ID lists.
- **`entity_assistant_changes_applied` event** — fired after any registry change
  plan is committed (currently a confirmed `remove_orphaned`; more mutating
  services to come) with `producer`, `triggered_by`, `counts`
  (`created`/`updated`/`removed`/`failed`), `object_types`, the affected id
  lists, and `journal_id`. A stable contract for reacting to bulk edits.

## Notes

- Exports reflect the **registries**, so they include entities/devices even
  when their integration is temporarily offline.
- Cell values starting with `=`, `+`, `-`, `@`, tab, or newline are
  automatically prefixed to prevent spreadsheet formula injection.
- File writes are restricted to the config directory to prevent path traversal.
- The HTTP endpoint is authenticated because it exposes your registry layout.

## Recipes

Task-driven recipes (filtered exports, dashboard download links, orphan
cleanup with a backup, failure alerts, and more) live in
[COOKBOOK.md](COOKBOOK.md).

## Changelog

Per-version release notes live in [CHANGELOG.md](CHANGELOG.md).

## Roadmap

See [ROADMAP.md](ROADMAP.md) for recommended future capabilities — where this
integration could grow from a read-only exporter into a genuine registry
assistant. It's a recommendation, not a commitment.
