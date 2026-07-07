# Versioning

Changelog for the Entity Assistant integration. Newest version at the top.
Follows [Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

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
