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
> ambiguous to split back apart — a known CSV limitation that a future
> structured output format (JSON) will round-trip losslessly.

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

## Usage

### Export

Four ways to export, all sharing the same options:

1. **Button entity** — the quickest.
2. **Service** (`export_csv`) — for automations/scripts and custom filenames.
3. **Signed URL** (`get_download_url`) — a click-to-download link for dashboards.
4. **HTTP endpoint** — direct download for scripts, the HA app, or `curl`.

### Registry cleanup

An additional button and a service for removing orphaned registry entries:

1. **Export orphaned entities** button — writes only stale rows to `entity_export_stale.csv`.
2. **Service** (`remove_orphaned`) — deletes orphaned entries, callable from
   Developer Tools or automations/scripts (no button, to prevent accidental use).

### Buttons

Adding the integration creates an **Entity Assistant** device with two buttons:

- **Export entity list** — writes `entity_export.csv` to your config directory.
- **Export orphaned entities** — writes only stale rows (orphaned, unavailable,
  restored, not changed) to `entity_export_stale.csv`.

**Configure the Export entity list button:** press **Configure** on the
integration (Settings → Devices & Services → Entity Assistant) to set the
defaults it uses — export type, filename, output format, the include/only-enabled
flags, stale filtering, and the UTF-8 BOM. Changes take effect on the next press,
no reload needed. (The orphaned button always exports stale entries.)

### Service: `export_csv`

Call `entity_assistant.export_csv` from **Developer Tools → Actions** (or from
an automation/script).

```yaml
action: entity_assistant.export_csv
data:
  filename: entity_export.csv
  export_type: entities
  only_enabled: true
  domains: [light, switch]
```

All fields are optional:

| Field | Default | Description |
| --- | --- | --- |
| `filename` | `entity_export.csv` | Output path, relative to the config directory. Subfolders are created automatically. Must stay inside the config directory. Give it a `.json`/`.yaml` extension to match `output_format`. |
| `export_type` | `entities` | `entities`, `devices`, `areas`, `floors`, or `labels` |
| `output_format` | `csv` | Serialization format: `csv`, `json`, or `yaml`. JSON and YAML are lossless structured formats; CSV is best for spreadsheets |
| `sort_by` | — | Column name to sort rows by (e.g. `name`, `area_name`). Unknown columns are ignored; values sort as text |
| `sort_dir` | `asc` | `asc` or `desc`; only applies when `sort_by` is set |
| `columns` | — | Ordered list of columns to output; others are dropped and unknown names are ignored. Overrides `preset` |
| `preset` | — | Named column set: `minimal` (all types), `identity` (entities), `stale` (entities/devices) |
| `include_disabled` | `true` | Include disabled entities/devices |
| `include_hidden` | `true` | Include hidden entities |
| `only_enabled` | `false` | Shortcut to exclude everything disabled/hidden |
| `domains` | — | Only these entity domains (entities export type) |
| `areas` | — | Only these areas (by area id or name) |
| `stale_only` | `false` | Only export rows flagged stale (see [Finding stale entities/devices](#finding-stale-entitiesdevices)) |
| `stale_days` | `30` | Threshold for the `not_changed_<N>d` stale reason |
| `utf8_bom` | `false` | Prepend a UTF-8 byte order mark so Excel on Windows renders non-ASCII characters correctly (CSV only) |
| `return_data` | `false` | Return the data directly in the service response instead of writing a file (`export_csv` only) |
| `max_rows` | `1000` | Row cap for `return_data` (`export_csv` only) |

The file is written inside your config directory. The service returns
`{path, row_count}`.

**Inline data return:** set `return_data: true` on `export_csv` to get the data
straight back in the service response — `{columns, rows, row_count, truncated}` —
without touching the filesystem. Handy for template sensors or dashboards.
`rows` is capped at `max_rows` (default 1000) and `truncated` is `true` when more
rows were available; `output_format` is ignored (rows come back as structured
data).

**Choosing columns:** by default every column for the export type is included.
Pass `columns` for an exact, reordered subset (great for a short sheet or a
specific import shape), or `preset` for a named set — `minimal` (all types),
`identity` (entities), or `stale` (entities/devices). `columns` wins over
`preset`, unknown column names are dropped, and if nothing valid is left the full
set is used. `sort_by` can still reference a column you didn't output.

**Output formats:** `csv` (default) is one header row plus one row per object,
with formula-injection guarding and the optional Excel BOM. `json` and `yaml`
emit a list of objects (one per row) preserving the column order — the lossless
shape a future import will read back. The CSV-only formula guard and BOM don't
apply to JSON/YAML, so their values are verbatim.

### Service: `get_download_url`

Returns a **signed, time-limited URL** that downloads the export without an auth
header — ideal for a dashboard link. Accepts the same options (including
`output_format`) plus `expires` (seconds, default 300) and `download_filename`.
Response only; writes no file.

`download_filename` sets the name the browser saves the file as (via
`Content-Disposition`). It's sanitized to a bare basename and its extension is
set from `output_format`, so a dated name like `entities_2026-09-24` downloads as
`entities_2026-09-24.csv` — handy for names that don't overwrite each other.

```yaml
action: entity_assistant.get_download_url
data:
  export_type: devices
  expires: 600
  download_filename: entities_2026-09-24
response_variable: dl
# dl.url -> https://<your-ha>/api/entity_assistant/export.csv?...&authSig=...
```

### Service: `remove_orphaned`

Removes orphaned entities (config entry removed), orphaned devices (all config
entries removed), and empty areas (no devices or entities) from the registries.
Area emptiness is recalculated after entity/device removal, so cascading cleanup
works in a single call.

```yaml
action: entity_assistant.remove_orphaned
```

No parameters. Returns `{entities_removed, devices_removed, areas_removed,
entity_ids, device_ids, area_ids}`.

### HTTP download endpoint

The integration also serves the export directly at:

```
/api/entity_assistant/export.csv
```

This endpoint is **authenticated**, so either use a signed URL from
`get_download_url`, or pass a
[long-lived access token](https://www.home-assistant.io/docs/authentication/#your-account-profile).
It accepts the same options as query flags: `export_type`, `output_format`,
`sort_by`, `sort_dir`, `download_filename`, `include_disabled`, `include_hidden`,
`only_enabled`, `stale_only`, `stale_days`, `utf8_bom`, `domains`, `areas` (the
last two comma-separated). `output_format` sets the response `Content-Type` and
download extension (`.csv`/`.json`/`.yaml`); `download_filename` sets the saved
name.

```bash
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  "http://homeassistant.local:8123/api/entity_assistant/export.csv?export_type=devices" \
  -o devices.csv
```

A plain browser link to this path returns 401 — use `get_download_url` for
browser downloads.

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

See [roadmap.md](roadmap.md) for recommended future capabilities — where this
integration could grow from a read-only exporter into a genuine registry
assistant. It's a recommendation, not a commitment.
