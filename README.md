# Entity Assistant

A Home Assistant custom integration that exports your registry — entities,
devices, or areas — to a CSV file, complete with `entity_id`, area, floor,
labels, device metadata, current state, and more.

## What it exports

Choose an `export_type`: **entities** (default), **devices**, or **areas**.

### Entities (one row per entity)

| Column | Description |
| --- | --- |
| `entity_id` | The entity ID (e.g. `light.kitchen`) |
| `name` | Friendly name (user override, falling back to the original) |
| `original_name` | Name assigned by the integration |
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
| `entity_category` | `config`, `diagnostic`, or blank |
| `device_class` | Device class (e.g. `temperature`, `motion`) |
| `unit_of_measurement` | Unit, if any |
| `state` | Current state at export time |
| `enabled` | `true` / `false` |
| `disabled_by` | Why it's disabled, if applicable |
| `hidden_by` | Why it's hidden, if applicable |
| `unique_id` | Integration-assigned unique ID |

### Devices (one row per device, including devices with no entities)

`device_id`, `name`, `name_by_user`, `manufacturer`, `model`, `sw_version`,
`hw_version`, `area_id`, `area_name`, `floor`, `labels`, `config_entries`,
`via_device_id`, `entity_count`, `disabled_by`.

### Areas (one row per area)

`area_id`, `name`, `floor_id`, `floor`, `labels`, `aliases`, `device_count`,
`entity_count`, `picture`.

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

Four ways to export, all sharing the same options:

1. **Button entity** — the quickest.
2. **Service** (`export_csv`) — for automations/scripts and custom filenames.
3. **Signed URL** (`get_download_url`) — a click-to-download link for dashboards.
4. **HTTP endpoint** — direct download for scripts, the HA app, or `curl`.

### Button

Adding the integration creates an **Entity Assistant** device with an
**Export entity list** button. Press it (from the device page, a dashboard, or
an automation) to write `entity_export.csv` to your config directory.

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
| `filename` | `entity_export.csv` | Output path, relative to the config directory. Subfolders are created automatically. Must stay inside the config directory. |
| `export_type` | `entities` | `entities`, `devices`, or `areas` |
| `include_disabled` | `true` | Include disabled entities/devices |
| `include_hidden` | `true` | Include hidden entities |
| `only_enabled` | `false` | Shortcut to exclude everything disabled/hidden |
| `domains` | — | Only these entity domains (entities export type) |
| `areas` | — | Only these areas (by area id or name) |

The file is written inside your config directory. The service returns
`{path, row_count}`.

### Service: `get_download_url`

Returns a **signed, time-limited URL** that downloads the CSV without an auth
header — ideal for a dashboard link. Accepts the same options plus `expires`
(seconds, default 300). Response only; writes no file.

```yaml
action: entity_assistant.get_download_url
data:
  export_type: devices
  expires: 600
response_variable: dl
# dl.url -> https://<your-ha>/api/entity_assistant/export.csv?...&authSig=...
```

### HTTP download endpoint

The integration also serves the export directly at:

```
/api/entity_assistant/export.csv
```

This endpoint is **authenticated**, so either use a signed URL from
`get_download_url`, or pass a
[long-lived access token](https://www.home-assistant.io/docs/authentication/#your-account-profile).
It accepts the same options as query flags: `export_type`, `include_disabled`,
`include_hidden`, `only_enabled`, `domains`, `areas` (comma-separated).

```bash
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  "http://homeassistant.local:8123/api/entity_assistant/export.csv?export_type=devices" \
  -o devices.csv
```

A plain browser link to this path returns 401 — use `get_download_url` for
browser downloads.

## Automations

- **`last_export` sensor** — a timestamp sensor on the Entity Assistant device,
  updated on every export, with `row_count`, `path`, `export_type`, and
  `triggered_by` attributes.
- **`entity_assistant_export_completed` event** — fired after each export with
  `path`, `row_count`, `export_type`, and `triggered_by`. Use it to, e.g.,
  email the file once it's written.

## Notes

- Exports reflect the **registries**, so they include entities/devices even
  when their integration is temporarily offline.
- File writes are restricted to the config directory to prevent path traversal.
- The HTTP endpoint is authenticated because it exposes your registry layout.
