# Entity Assistant

A Home Assistant custom integration that exports your full device/entity list —
`entity_id`, area, device metadata, current state, and more — to a CSV file.

## What it exports

One row per entity, with these columns:

| Column | Description |
| --- | --- |
| `entity_id` | The entity ID (e.g. `light.kitchen`) |
| `name` | Friendly name (user override, falling back to the original) |
| `original_name` | Name assigned by the integration |
| `platform` | Integration that created the entity (e.g. `hue`, `mqtt`) |
| `device_id` | Registry ID of the parent device |
| `device_name` | Device name (user override, falling back to the original) |
| `device_manufacturer` | Device manufacturer |
| `device_model` | Device model |
| `area_id` | Effective area ID (entity override, falling back to the device) |
| `area_name` | Effective area name |
| `entity_category` | `config`, `diagnostic`, or blank |
| `device_class` | Device class (e.g. `temperature`, `motion`) |
| `unit_of_measurement` | Unit, if any |
| `state` | Current state at export time |
| `enabled` | `true` / `false` |
| `disabled_by` | Why it's disabled, if applicable |
| `hidden_by` | Why it's hidden, if applicable |
| `unique_id` | Integration-assigned unique ID |

## Installation

1. Copy the `custom_components/entity_assistant` folder into your Home Assistant
   `config/custom_components/` directory. The result should be
   `config/custom_components/entity_assistant/`.
2. Add the following to your `configuration.yaml`:

   ```yaml
   entity_assistant:
   ```

3. Restart Home Assistant.

## Usage

Call the `entity_assistant.export_csv` service from
**Developer Tools → Actions** (or from an automation/script).

```yaml
action: entity_assistant.export_csv
data:
  filename: entity_export.csv
  include_disabled: true
  include_hidden: true
```

All fields are optional:

| Field | Default | Description |
| --- | --- | --- |
| `filename` | `entity_export.csv` | Output path, relative to the config directory. Subfolders are created automatically. Must stay inside the config directory. |
| `include_disabled` | `true` | Include disabled entities |
| `include_hidden` | `true` | Include hidden entities |

The file is written inside your Home Assistant configuration directory (the same
folder as `configuration.yaml`). The service returns the resolved path and the
number of entities exported.

### Downloading the file

To grab the CSV from the browser, write it into the `www` folder:

```yaml
action: entity_assistant.export_csv
data:
  filename: www/entity_export.csv
```

It's then available at `http://<your-ha>:8123/local/entity_export.csv`.

## Notes

- The export reflects the **entity registry**, so it includes entities even
  when their integration is temporarily offline.
- Writing is restricted to the config directory to prevent path traversal.
