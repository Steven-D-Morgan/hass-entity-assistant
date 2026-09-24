# Changelog

Changelog for the Entity Assistant integration. Newest version at the top.
Follows [Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

## 1.8.0 — 2026-09-24

The first slice of the **round-trip-ready export** milestone (1.8): stable
keys and writable-column completeness, so a future `import_changes` can key
rows unambiguously and round-trip every user-editable field. Additive only —
no removals, no behavior change to existing columns.

- **Entity export** gains four columns:
  - `registry_id` — the stable registry ULID (`RegistryEntry.id`). It survives
    an `entity_id` rename, making it the key the import path will match rows on.
  - `icon` — the entity's icon override (blank when unset).
  - `aliases` — voice/Assist aliases, `", "`-joined. Home Assistant 2026.9
    changed the entity alias model to a list that can carry a non-string
    "computed name" sentinel; the exporter filters to real string aliases, so
    it stays correct on both that core and older ones where aliases were a
    plain `set[str]`.
  - `categories` — category assignments serialized as `scope:category_id`,
    `", "`-joined.
- **Area export** gains an `icon` column (the area's icon override).
- **Docs:** README documents the new columns and the comma-in-name limitation
  of the `", "`-joined multi-value columns (`labels`, `aliases`, `categories`),
  which a later structured (JSON) output format will round-trip losslessly.
- **Tests:** new coverage for the stable key, the writable fields, area icon,
  and the alias/category serializers (including sentinel filtering). The CSV
  column-contract snapshots were regenerated for the added columns.

## 1.7.1 — 2026-09-13

- **CI:** committed the missing `tests/snapshots/test_snapshots.ambr` file so
  the six 1.7 snapshot tests actually pass. `pytest-homeassistant-custom-component`
  overrides syrupy's default snapshot directory to `snapshots/` (no
  underscores), so the file has to live at `tests/snapshots/`, not the
  syrupy-default `tests/__snapshots__/`. No integration behavior change.
- Bumped Dependabot-managed CI action versions: `actions/checkout` 4 → 7,
  `actions/setup-python` 5 → 7, `softprops/action-gh-release` 2 → 3.

## 1.7.0 — 2026-09-09

The **trust gate** milestone from the roadmap: tests, CI, and safety gating
on the one shipped mutation. No new user-facing features.

- **Safety:** `remove_orphaned` now defaults to `dry_run: true`, returning
  the would-remove lists without touching the registries. Applying requires
  explicit `confirm: true`, and the caller must be an admin — a
  non-admin call raises `Unauthorized`. Automations that called the service
  bare will now preview instead of mutate; opt back into the old behavior
  with `confirm: true`.
- **Tests:** first real pytest suite (`pytest-homeassistant-custom-component`)
  covering row generation, staleness classification, `ExportOptions` filters,
  path-traversal guard, HTTP endpoint auth, admin gating, the button, and
  translation key parity across all 13 locales. syrupy golden-file snapshots
  lock down the CSV column contract so any column addition, reorder, or
  rename fails CI and forces a deliberate `--snapshot-update`.
- **CI:** new `ci.yml` running ruff (check + format) and mypy strict on every
  push/PR — mirrors HA core's ruff selection (`B, C, E, F, I, N, RUF, S, UP,
  W`) with a 100-char line length. Dependabot enabled for the
  `github-actions` ecosystem, weekly. Python 3.13 required (`requires-python`
  bumped) — HA 2026.9+ parses on 3.13/3.14 only.
- **HTTP:** download responses now send `Cache-Control: no-store` so
  registry data isn't cached by browsers or intermediaries. Shorter safe
  default `expires` (120s) on signed URLs.
- **Source hygiene:** stripped all comments from the integration source;
  design notes live in the private code-notes doc so the shipped package
  stays lean.

## 1.6.2 — 2026-09-04

- **Reliability:** wrapped every export trigger (services, buttons, HTTP
  endpoint) in explicit error handling. A disk-full, permission, or path
  error now surfaces as an actionable log message instead of a raw traceback,
  and the sensor no longer silently ignores the failure.
- Added `entity_assistant_export_failed` event fired on any failing export,
  carrying `path`, `error`, `error_type`, `export_type`, and `triggered_by`
  so automations can react to failures the same way they already react to
  `entity_assistant_export_completed`.
- The **Last export** sensor now records the most recent failure as four
  attributes (`last_error`, `last_error_at`, `last_error_type`,
  `last_error_triggered_by`) while keeping its state pinned to the last
  **successful** export timestamp. Attributes survive a restart via
  `RestoreEntity`.
- The HTTP endpoint now returns a clean `500` with the exception class name
  on failure instead of a Home Assistant error page, and fires the same
  failure event so the sensor stays consistent across trigger paths.

## 1.6.1 — 2026-09-01

- **Security:** CSV formula-injection hardening — cell values starting with
  `=`, `+`, `-`, `@`, tab, or newline are now prefixed with a tab character so
  spreadsheet applications treat them as text instead of executable formulas.
  Always on; no opt-in needed.
- Added opt-in **UTF-8 BOM** (`utf8_bom`) option to the `export_csv`,
  `get_download_url` services, and the HTTP endpoint. When enabled, the CSV
  starts with a UTF-8 byte order mark so Excel on Windows renders non-ASCII
  characters correctly. Default off.
- Removed the **Remove orphaned entries** button to prevent accidental presses.
  The `entity_assistant.remove_orphaned` service remains available for
  intentional use from Developer Tools or automations.
- All 13 translations updated with the new `utf8_bom` field strings.

## 1.6.0 — 2026-09-01

- Added **Export orphaned entities** button — writes only stale rows
  (orphaned, unavailable, restored, not changed) to `entity_export_stale.csv`.
- Added **Remove orphaned entries** button — deletes orphaned entities (config
  entry removed), orphaned devices (all config entries removed), and empty
  areas (no devices or entities) from the Home Assistant registries.
- Added `entity_assistant.remove_orphaned` service with optional response
  support, returning `{entities_removed, devices_removed, areas_removed,
  entity_ids, device_ids, area_ids}`.
- New `entity_assistant_orphaned_removed` event fired after each removal.
- All 13 translations updated with the new service strings.

## 1.5.1 — 2026-08-28

- Backfilled the `stale_only` and `stale_days` service field labels and
  descriptions into all 12 non-English translations (German, French, Spanish,
  Italian, Dutch, Portuguese (Brazil), Polish, Russian, Norwegian Bokmål,
  Swedish, Czech, Simplified Chinese), closing the gap noted in 1.5.0.
- Docs: the HTTP endpoint's query-flag list was missing `stale_only` and
  `stale_days`, which it has accepted since 1.5.0.

## 1.5.0 — 2026-08-28

- Added **stale detection** for entities, devices, and areas, with a
  `stale` flag and a categorized `stale_reason` column so end users can see
  *why* a row is flagged:
  - Entities: `unavailable`, `orphaned` (config entry/integration gone),
    `restored` (not provided since restart), `not_changed_<N>d`.
  - Devices: `orphaned`, `no_entities`, `all_unavailable`.
  - Areas: `empty` (no devices or entities).
- Added entity columns `available`, `last_changed`, `last_changed_days`, and
  device column `available_entity_count`.
- Added `stale_only` filter and `stale_days` option (default 30) to the
  `export_csv` and `get_download_url` services and the HTTP endpoint.
- Packaging: each release now ships an `entity_assistant.zip` asset, built by a
  new `release` workflow, and `hacs.json` sets `zip_release` so HACS installs
  from that asset instead of fetching files one at a time. This also makes
  GitHub's download counter reflect real installs — added a Downloads badge to
  the README. Versions 1.4.2 and earlier are unaffected and still install the
  old way, since HACS reads `hacs.json` from the version being installed.
- Note: the 12 non-English translations fall back to English for the two new
  service fields until backfilled.

## 1.4.2 — 2026-07-07

- Fixed a setup crash (`ModuleNotFoundError: homeassistant.helpers.device_info`)
  in the button and sensor platforms — import `DeviceInfo` from
  `homeassistant.helpers.device_registry` instead.

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
