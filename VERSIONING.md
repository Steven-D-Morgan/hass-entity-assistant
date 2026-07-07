# Versioning

Changelog for the Entity Assistant integration. Newest version at the top.
Follows [Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

## 1.4.1 — 2026-07-07

- Added UI translations for the config flow and both services in 12 common
  Home Assistant languages: German, French, Spanish, Italian, Dutch,
  Portuguese (Brazil), Polish, Russian, Norwegian Bokmål, Swedish, Czech, and
  Simplified Chinese.

## 1.4.0 — 2026-07-07

- Added a `get_download_url` service returning a **signed, time-limited URL**
  so the download endpoint is click-to-download from a dashboard (no auth
  header needed).
- Added a **`last_export` timestamp sensor** on the Entity Assistant device
  (attributes: `row_count`, `path`, `export_type`, `triggered_by`), restored
  across restarts.
- Fire an **`entity_assistant_export_completed`** event after every export.
- Added **export types**: `entities` (default), `devices` (incl. devices with
  no entities), and `areas`.
- Added **richer columns**: `labels`, `floor`, and `config_entry` for entities;
  full metadata for devices/areas.
- Added **filters**: `domains`, `areas`, and `only_enabled`; the HTTP endpoint
  and signed URL honor the same options.
- Added CI: `hassfest` + HACS validation GitHub Actions. Set `integration_type`
  to `service` and moved brand icons to
  `custom_components/entity_assistant/brand/` so HACS validation passes.
- Refactored `export.py` around an `ExportOptions` dataclass and
  `async_run_export`; added `sensor.py`.

## 1.3.0 — 2026-07-07

- Added an **Export entity list** button entity, attached to a new
  "Entity Assistant" service device, so the export can be triggered from the
  UI or automations without Developer Tools.
- Added an authenticated **HTTP download endpoint** at
  `/api/entity_assistant/export.csv` (supports `include_disabled` /
  `include_hidden` query flags) for fetching the CSV directly.
- Refactored shared export logic into `export.py` (used by the service, the
  button, and the HTTP view); added `button.py` and `http.py`.
- manifest.json: declare `http` dependency, add the `button` platform.

## 1.2.1 — 2026-07-07

- Added brand icon assets (`brand/icon.png` 256×256, `brand/icon@2x.png`
  512×512) for submission to the home-assistant/brands repo so the logo shows
  in the integrations list.

## 1.2.0 — 2026-07-07

- Added HACS support: `hacs.json` at the repo root so the integration can be
  installed as a HACS custom repository.
- Updated README with HACS installation instructions.

## 1.1.0 — 2026-07-07

- Added a config flow so the integration appears in **Settings → Devices &
  Services** and is addable via **Add Integration** (single-instance).
- Replaced YAML setup (`async_setup`) with config-entry setup
  (`async_setup_entry` / `async_unload_entry`); the `export_csv` service now
  registers on entry setup and is removed on unload.
- Added `strings.json` and `translations/en.json` for the add-integration
  dialog.
- Updated README: install is now UI-based (no `configuration.yaml` entry).

## 1.0.0 — 2026-07-07

- Initial release.
- New `entity_assistant.export_csv` service that exports the full entity
  registry to a CSV file (one row per entity: `entity_id`, name, platform,
  device name/manufacturer/model, effective area, entity category, device
  class, unit, current state, enabled/disabled/hidden flags, unique_id).
- Optional service parameters: `filename`, `include_disabled`,
  `include_hidden`.
- Output path restricted to the config directory (path-traversal guard);
  parent subfolders created automatically; file I/O runs in the executor.
- Service returns `{path, entity_count}` as a response.
