# Roadmap

Entity Assistant today is a read-only exporter: it walks the entity, device, and area registries and writes them to CSV (plus a `stale`/`stale_reason` audit), triggered from a button, two services, or an authenticated HTTP endpoint. This roadmap sketches how it could grow into what its name promises — a genuine registry *assistant* that not only reports on registry hygiene but helps you act on it safely — while adding native Home Assistant surfaces (sensors, diagnostics, repairs) around the same registry walk. It is a recommendation and a set of options, not a commitment; horizons and priorities will shift with maintainer time and user demand.

### 1. Registry maintenance — the "assistant" track

The headline evolution: turn the read-only exporter into a curation tool that can fix what it already flags. This is the highest-value, highest-risk track, and it is gated. Every write rides a shared safety spine (dry-run by default, change plan for review, explicit confirm, timestamped JSON journal + registry backup, `undo`), and nothing here ships before the automated test suite lands. The spine can fully reverse *updates* (area, labels, enable/hide, name) but cannot resurrect a *removed* registry entry — a HA backup is the only real undo for removals, which the plan states plainly.

| Capability | What it adds | Effort | Risk | Horizon |
| --- | --- | --- | --- | --- |
| Preview / commit / undo safety spine | Shared mutation framework every write uses: `dry_run:true` default returning a structured change plan via `SupportsResponse`, explicit non-default `confirm` to apply, per-commit change journal + config-dir registry backup, `entity_assistant_changes_applied` event, and `undo_last` / `undo` replaying before-values in reverse. Foundational; the item mutates nothing itself. | L | medium | Next |
| Bulk (re)assign area & floor | Assign or move the filtered set of entities/devices to an area (`er.async_update_entity(area_id=…)`, `dr.async_update_device(area_id=…)`), and set an area's floor (`ar.async_update(floor_id=…)`), with optional auto-create. The single most common post-install chore, fully reversible. | M | low | Next |
| Bulk label curation (add / remove / replace) | Set-union / set-difference / set-replace of labels across the filtered set of entities, devices, and areas, auto-creating missing labels (`lr.async_create`). Organisational metadata; lowest-risk mutation and a good confidence-builder. | M | low | Next |
| Bulk enable / disable / hide / unhide | Flip `disabled_by` / `hidden_by` across the filtered set (pairs with `stale_only` to disable dead entities), preview showing each id's current→target state. Reversible, but disabling removes an entity's state, so the plan warns when a target is referenced. (Devices have `disabled_by` but no `hidden_by`.) | M | medium | Next |
| Bulk set friendly name | Bulk-set the **friendly name override** (`name`) across the filtered set (`name=None` clears it). Deliberately excludes `entity_id` rewrites — see Non-goals. Low-risk, separately gated from any id change. | S | low | Next |
| ~~Remove orphaned & empty registry entries~~ | ~~The flagship cleanup: delete only entries the existing classifier already flags stale — orphaned entities/devices, restored-but-never-provided entities, no-entity/all-unavailable devices, and empty areas / unused labels / unused floors. Candidate set intersected with the staleness classification so a live entity can never be a target. Genuinely destructive and only partly reversible; hard-gated (mandatory dry-run, explicit confirm, backup recommended in the plan) and never scheduled.~~ **Shipped in 1.6.0** — scoped to orphaned entities (config entry removed), orphaned devices (all config entries removed), and empty areas; available as a button and a `remove_orphaned` service. | L | high | ~~Later~~ Done |

### 2. Registry health, analytics & linting

Turn the CSV-only stale data into first-class HA state you can graph, alert on, and act on — with no new dependencies. All of this reads from one shared summarizer refactored out of the existing registry walk.

| Capability | What it adds | Effort | Risk | Horizon |
| --- | --- | --- | --- | --- |
| Shared summarizer + debounced coordinator | Refactor the `export.py` registry walk into a reusable summarizer, fed to a `DataUpdateCoordinator` (fits `iot_class: local_polling`) that recomputes on `er`/`dr`/`ar` registry-updated events plus a light interval, debounced against startup churn. The single source behind the sensors, binary sensor, and diagnostics below. | M | low | Now |
| Registry count sensors | A small curated set of `DIAGNOSTIC`, `MEASUREMENT` sensors on the existing service device — total entities, stale, unavailable, orphaned/restored, missing-area, unnamed — with finer breakdowns as attributes to avoid entity sprawl. Long-tail sensors ship `entity_registry_enabled_default=False`. | M | low | Now |
| "Registry has problems" `binary_sensor` | One `BinarySensorDeviceClass.PROBLEM` entity that is `on` when any high-confidence problem count exceeds a threshold, with attributes summarizing which categories tripped. One clean automation hook. (Adds `Platform.BINARY_SENSOR`.) | S | low | Now |
| On-demand diagnostics health report | `diagnostics.py` (`async_get_config_entry_diagnostics`) powering HA's native **Download diagnostics** button: totals, per-domain/per-integration and per-area counts, empty areas, orphaned/stale/unavailable breakdowns, top offenders, current options, HA version. Zero new entities. User-named/free-text fields run through `async_redact_data`. | S | low | Now |
| Registry lint report (new `lint` export type) | One row per detected issue — `object_type`, `object_id`, `rule`, `severity`, `detail`, `suggested_fix` — covering cheap structural rules: missing area, unnamed / name derived only from `entity_id`, duplicate friendly names (globally and within an area), duplicate device identifiers, orphaned config entry, restored-not-provided. A prioritized worklist, reusing the service/HTTP/signed-URL surfaces. | M | low | Now |
| Recorder hygiene for analytics sensors | Keep the numeric sensors from bloating the Recorder DB on large installs: mark them `DIAGNOSTIC`, ship the long tail disabled by default, and document `exclude`/`entity_registry_enabled_default`. Avoids a class of "my database is huge" reports. | S | low | Now |
| Device-class & unit sanity linting | A lint rule set flagging metrological mismatches (a `device_class` that disallows its `unit_of_measurement`, a unit with no `device_class`, a numeric class with a non-numeric state), evaluated against the running core's `DEVICE_CLASS_UNITS` at runtime and degrading gracefully if the import moves. Catches silent long-term-statistics/energy bugs. | M | medium | Next |

### 3. Output formats & delivery

Small, high-satisfaction wins built on the `(columns, rows)` seam `build_export()` already exposes. CSV stays the default, so existing callers are untouched.

| Capability | What it adds | Effort | Risk | Horizon |
| --- | --- | --- | --- | --- |
| Structured output formats (JSON, NDJSON, YAML) | An `output_format` option adding `json`, `ndjson`, `yaml` beside `csv`, dispatched through the services, signed URL, and HTTP view (`Content-Type` + extension). `json` is stdlib; PyYAML already ships in HA core — no manifest requirement. | S | low | Now |
| Sorting & grouping controls | `sort_by` (any exported column), `sort_dir`, and optional `group_by` (area / domain / floor) applied to the rows before serialization, using a stable sort so existing ordering is the tiebreaker. Guarded against unknown columns. Purely presentational. | S | low | Now |
| Return export data inline in the service response | A `write:false` (or `return_data:true`) option so `export_csv` returns `columns` + `rows` in its already-`OPTIONAL` `ServiceResponse` with no file touched — powering template sensors and dashboards directly. Service responses are returned to the caller, not recorded; the real constraint is payload size, so it stays opt-in with a row cap. (M if `limit`/`offset` are added.) | S | low | Now |
| Per-run download filename + format-aware `Content-Disposition` | Let the HTTP endpoint / `get_download_url` accept a caller-supplied download filename (e.g. `entities_{type}_{date}`), sanitized to a bare basename (strip separators, CR/LF, control chars), with the extension derived from `output_format`. Dated names stop overwriting each other. | S | low | Now |
| ~~CSV / spreadsheet formula-injection hardening + optional UTF-8 BOM~~ | ~~Security fix to the *current* feature: registry names/models/aliases are user-controlled free text written verbatim, so a value starting with `=`, `+`, `-`, or `@` becomes a live formula in Excel/LibreOffice/Sheets. Neutralize dangerous leading characters across CSV/Markdown/HTML, and add an opt-in UTF-8 BOM so Excel renders non-ASCII names correctly.~~ **Shipped in 1.6.1** — tab-prefix sanitization always on; opt-in `utf8_bom` option on services and HTTP endpoint. | S | low | ~~Now~~ Done |
| User-selectable & reorderable column sets | A `columns` option (ordered list) plus a few named presets that subset and reorder `COLUMNS_BY_TYPE` per export type, validated against the known columns. Project each row to the selected keys (or `DictWriter(extrasaction='ignore')`). Short, legible exports for non-experts; exact shapes for power users. | M | low | Next |
| Human-readable reports (Markdown + accessible HTML) | `rows_to_markdown` (GitHub-flavored table, paste into an issue or a Markdown card) and `rows_to_html` (self-contained, inline-CSS report with summary counts), dependency-free. Cells escaped (`html.escape` + pipe-escaping). The HTML uses semantic `<table>`/`<th scope>`, a `lang` attribute, and WCAG-AA contrast so a shared audit is usable with assistive tech. | M | low | Next |
| Redaction / anonymization mode | An opt-in mode that hashes or strips user-named/free-text fields (friendly names, `name_by_user`, aliases, pictures, `unique_id`) while keeping structural columns, available to the CSV/JSON/Markdown/HTML paths. Makes the "paste this into a forum/issue" use cases the roadmap sells actually safe. | M | low | Next |
| Deliver the export through a notify service | A per-call option that mints a signed URL (`async_sign_path` + `get_url`) and sends it plus summary counts through a user-named notify target — supporting both legacy `notify.<service>` and modern `notify.send_message` entity targets. Opt-in; documents that the signed URL is a time-limited **bearer token** granting unauthenticated download, and honors the `expires` window. | M | medium | Next |

### 4. Platform integration & native conventions

Be a well-behaved HA citizen: one options flow, robust failure handling, meeting non-experts where they already look, and hardening the surfaces that already ship.

| Capability | What it adds | Effort | Risk | Horizon |
| --- | --- | --- | --- | --- |
| Registry-aware service selectors | Swap the `areas` service field to `selector: area: {multiple: true}` and `domains` to a `select` with `multiple` + `custom_value`, so both are pickable in the service UI instead of hand-typed YAML. **No Python change** — the voluptuous schema is already `[cv.string]` and `area_matches()` already accepts ids or names — and backward compatible with existing YAML. The lowest-effort UX win on the board. | S | low | Now |
| Consolidated options flow | The integration's single `OptionsFlow` (via `async_get_options_flow`, persisted to `entry.options`). One home for **all** knobs — export defaults, analytics toggles/interval/thresholds, retention. Consuming surfaces read `entry.options` at use time (the Button in `async_press()`, which today hardcodes `entities` + defaults), so no reload is needed for it; add an `add_update_listener` reload only for entities that must reconfigure. Enabler for most other configurable items. Implementation note: do **not** assign `self.config_entry` in the flow's `__init__` — HA provides it since 2024.11 and re-adding it breaks the flow. | S | low | Now |
| ~~Export failure handling & self-observability~~ | ~~Today `async_run_export` has no `try/except`, the button only logs on success, and `last_export` only advances on success — a disk-full or permission error surfaces as a raw traceback with no durable signal. Add a `last_export` status/`last_error` attribute (or companion sensor), an `entity_assistant_export_failed` event, and `try/except` + actionable `_LOGGER.error` around every trigger path. Prerequisite for trusting any unattended export.~~ **Shipped in 1.6.2** — every trigger path (services, buttons, HTTP endpoint) wraps the export in try/except; `entity_assistant_export_failed` event carries `path`/`error`/`error_type`/`export_type`/`triggered_by`; the `last_export` sensor records the most recent failure as `last_error*` attributes while keeping its state pinned to the last successful timestamp. | S | low | ~~Now~~ Done |
| In-product onboarding & discoverability | A config-flow "getting started" description and/or a one-time persistent notification (or informational Repair) pointing new users to the export button, the services, and the docs — instead of landing them on a bare device. Directly cuts "how do I use this" support load for the HACS audience. | S | low | Now |
| Bundled blueprint automations | One-click-importable automation blueprints under `blueprints/automation/entity_assistant/`: "export nightly and notify with a download URL" (HA's own time trigger + `get_download_url`), and "alert when a new orphaned/stale entity appears" (change events / count sensors, user picks the notify target). High perceived value, near-zero maintenance — the low-upkeep alternative to a built-in scheduler and a bundled notifier. | S | low | Now |
| Assist / conversation intent exposure | Live up to the name on HA's Assist layer: a registered intent (or documented intent-script/sentence-trigger blueprint) answering "how many stale entities do I have" from the shared summarizer, or "export my entity list." Idiomatic, low-risk, and far cheaper than the mutation track. | S | low | Next |
| Repairs surface for registry problems | One coordinated Repairs strategy (not three): raise deduplicated, self-clearing, threshold-gated issues in **Settings → Repairs** for unambiguous problems (orphaned entities from a removed integration, empty areas). v1 is informational (`is_fixable=False`). Guided `RepairsFlow` fix-flows come **Later** and only over the already-gated safety spine. | M → L | medium | Next → Later |
| HTTP endpoint & signed-URL hardening | Beyond the existing auth: set `Cache-Control: no-store` on the download so registry data isn't cached by browsers/intermediaries; optionally log/audit downloads; allow the HTTP view to be disabled via options for users who don't want it; document the signed URL's bearer-token nature and offer a shorter safe default `expires`. | S | low | Next |
| Event-loop safety & executor offload | `build_export` and the row builders run on the event loop today, and the HTTP handler serializes CSV inline — fine now, but a 10k-entity install plus the coordinator's per-event recompute risks slow-callback warnings. Move heavy build/serialization to the executor, stream large downloads, and set an explicit performance budget for the coordinator. | M | medium | Next |
| Uninstall & teardown | `async_unload_entry` removes only the services today; there is no `async_remove_entry`. Add teardown that offers to clean up integration-authored files (and future snapshots/journals), makes those stores self-pruning, and documents what persists — notably that HA cannot unregister the HTTP view until restart. Land this before the storage-backed features do. | S | low | Next |
| Config-entry & options/storage migration + compat policy | The config entry is `VERSION=1` with no `async_migrate_entry`. Before the options flow and snapshot storage evolve, add a migration stub + versioned options/storage schema, and a feature-detection/min-version policy so version-gated APIs (`RegistryEntryDisabler`, `OptionsFlowWithReload`, `DEVICE_CLASS_UNITS`, floor/label registries) degrade gracefully on the min-supported core (2024.11.0). | S | low | Next |

### 5. Snapshots & change tracking over time

Give the integration a memory: capture baselines, diff against them, and emit change intelligence — all read-only over the integration's own storage, never the registries. Scheduling is delivered via blueprints on HA's native time triggers rather than a built-in timer (see Non-goals).

| Capability | What it adds | Effort | Risk | Horizon |
| --- | --- | --- | --- | --- |
| Snapshot store + `capture_snapshot` service | Versioned JSON baselines in `.storage` via `homeassistant.helpers.storage.Store` (executor-safe, migration hooks), keyed by stable id + `captured_at`, capped to keep the last N. A `capture_snapshot` service (`SupportsResponse.OPTIONAL`) freezes a known-good inventory before a big reconfiguration or upgrade. Foundation for the rest of the track. | M | low | Now |
| Diff service — what changed since a snapshot | `entity_assistant.diff` (`SupportsResponse.ONLY`) returning categorized deltas — added, removed, renamed, moved, newly-stale, recovered — from a dict-keyed comparison of current rows vs a stored snapshot, with documented rename-vs-remove/add and `unique_id`-churn rules. Optionally writes a diff CSV + signed URL. | M | low | Next |
| Granular change events | After a diff, fire categorized `hass.bus` events (entity added / removed / moved / newly-stale) carrying affected ids, following the existing `entity_assistant_export_completed` pattern, so users automate off them in the normal editor. Event names/payloads are a documented public contract. | S | low | Next |
| Change-count analytics sensors | A small fixed set of `RestoreEntity` sensors (like `last_export`) reporting counts from the most recent diff — added/removed/renamed/newly-stale/orphaned — for Recorder history and threshold alerts. Meaningful only once diffs run on a cadence. | M | low | Later |
| Snapshot history & retention management | `list_snapshots` / `get_snapshot` / `prune_snapshots` services (`SupportsResponse.ONLY`), a retention policy (keep N snapshots or N days) in the options flow, and inclusion of recent snapshots + latest diff in the one diagnostics report. Prune is opt-in and only touches the integration's own store, never HA data. | M | low | Later |

### 6. Foundations — testing, quality, docs & distribution

The meta-track that makes everything above responsible to ship. The pytest suite is the hard gate before any registry-mutating feature.

| Capability | What it adds | Effort | Risk | Horizon |
| --- | --- | --- | --- | --- |
| Core pytest suite | `pytest-homeassistant-custom-component` seeding the entity/device/area/floor/label registries and asserting row generation, staleness categorization, and the `ExportOptions` filters — explicitly covering the `resolve_path` traversal guard and the HTTP endpoint's auth. `build_export`/`rows_to_csv` are already near-pure, so coverage is cheap. The hard prerequisite for the entire mutation track. Runs in CI against min + latest HA. | M | low | Now |
| CSV output-contract snapshot tests (syrupy) | Golden-file snapshots of header + rows per export type against a committed fixture registry, so any change to the column set, order, or formatting fails CI and forces a deliberate, versioned decision. The CSV schema is the tool's real public API. | S | low | Now |
| CI quality gate: ruff + mypy + Dependabot | A lint/type job mirroring HA core's ruff config, `mypy` over the package (pragmatic ignores where core helpers are partly typed), and Dependabot scoped to `github-actions`. Cheap on an ~875-LOC, dependency-free codebase, and keeps a future core submission realistic. | S | low | Now |
| Translation-coverage CI guard | A key-parity assertion across `translations/*.json` vs `strings.json`, hard-failing when a new string isn't backfilled to all 13 locales. Complements `hassfest` (format, not cross-locale completeness) and becomes essential once the options flow, repairs, and new services add strings. | S | low | Now |
| `services.yaml` + selectors + translated strings discipline | An explicit, ongoing line item: every new service and option needs a `services.yaml` entry with UI selectors plus matching `strings.json`/translations keys, or it won't render in the service editor and won't localize. Today a single option is a four-place edit (`services.yaml` + `strings.json` × two services) plus 13 translation files — easy to forget; it spans nearly every proposal. | S | low | Now (per feature) |
| Docs & examples cookbook | A per-export-type column data dictionary, an automation/recipe cookbook (nightly export, notify-on-new-stale off the existing event and `last_export` sensor, HTTP-fetch examples), committed sample outputs, and a troubleshooting/FAQ. The sample CSVs double as the syrupy fixtures, keeping docs and tests in lockstep. Directly reduces support load. | S | low | Now |
| HACS default store + `home-assistant/brands` submission | Submit the repo to the HACS default store (already passes `hacs/action`) and open the outstanding brands PR adding `icon.png`/`logo.png`, closing the placeholder-icon gap for pre-2026.3.0 installs. Risk is external (reviewer latency, brand image spec), not code. | M | medium | Next |
| `quality_scale` declaration + core-submission readiness | Declare `quality_scale` in `manifest.json` and align remaining conventions toward an eventual `home-assistant/core` submission. Best done once the feature surface (options flow, diagnostics, sensors) has settled. | M | medium | Later |

## Phased plan

The tables above are thematic; this section sequences the strongest items into a coherent order and makes dependencies explicit.

**The single most important near-term theme is trustworthiness.** Land the automated test suite and CSV output-contract tests, harden the export paths that already ship (formula-injection, failure observability), and consolidate configuration into one options flow — *before* writing a single line of registry-mutating code. The exporter earns trust as a reporter first; only then does it earn the right to act.

### Now — reporter, hardened

Low-risk work with no destructive path, plus the gate that unlocks everything else.

- **Establish the gate:** core pytest suite, CSV snapshot-contract tests, ruff + mypy CI, translation-coverage guard, docs cookbook (shared fixtures with the snapshot tests).
- ~~**Harden the shipped feature:** CSV/spreadsheet formula-injection fix + UTF-8 BOM option; export failure handling & self-observability.~~ *(formula-injection + BOM shipped in 1.6.1; failure handling & observability shipped in 1.6.2)*
- **Quick delivery wins on the existing seam:** structured formats (JSON/NDJSON/YAML), sorting & grouping, per-run filename, inline data return.
- **Native health surfaces:** shared summarizer + coordinator → count sensors + `PROBLEM` binary_sensor + `diagnostics.py` + the `lint` export type, with Recorder hygiene baked in from day one.
- **Configuration & onboarding:** the registry-aware service selectors (a no-Python quick win), the consolidated options flow (so the button and future features honor stored preferences), and in-product onboarding.

### Next — assistant, gated

Build the safety scaffolding, then the low-risk mutations on top of it, plus the memory and delivery layers.

- **Snapshots & change tracking:** snapshot store + `capture_snapshot`, diff service, granular change events. Scheduling and alerting arrive as **blueprints** on HA's native time triggers — not a built-in timer.
- **Richer output & delivery:** column sets, Markdown/accessible-HTML reports, redaction mode, notify delivery; device-class/unit linting.
- **Be a proper HA citizen:** HTTP/signed-URL hardening, executor offload/streaming for large installs, uninstall teardown, and the config-entry/storage migration + compat policy (the options flow and snapshot store make these newly necessary).
- **The safety spine** (preview/commit/undo + registry backup) — gated behind the now-landed pytest suite. Then the **reversible mutations** on it, easiest first: bulk area & floor, bulk labels, bulk set friendly name, bulk enable/disable/hide.
- **Meet users where they look:** the informational Repairs surface, and Assist/intent exposure.
- **Reach:** HACS default store + `home-assistant/brands` submission, presented on a now-mature repo.

### Later — destructive, only when proven

The highest-risk work, deferred until the spine and the reversible mutations are proven in the field.

- ~~**Remove orphaned & empty registry entries**~~ — shipped in 1.6.0 (orphaned entities, orphaned devices, empty areas; button + `remove_orphaned` service).
- **Guided fix-flows in Repairs**, layered over the same gated removal/reassignment.
- **Change-count sensors** and **snapshot retention management**, once diffs run on a regular cadence.
- **`quality_scale` / core-submission readiness**, once the feature surface has settled.

**Dependency summary:** tests → safety spine → reversible bulk edits → destructive removal. Options flow → configurable analytics, retention, and stored export defaults. Shared summarizer → count sensors, `PROBLEM` binary_sensor, diagnostics, health checks. Snapshot store → diff → change events → change-count sensors and alert blueprints.

## Non-goals

Deliberately out of scope, to protect the maintainer's time and the integration's safety posture:

- **Cloud sync, telemetry, or any external service.** Everything stays local. No usage analytics, no remote storage, no phone-home.
- **Auto-mutation without confirmation.** The registries are never modified as a side effect, on a schedule, or without an explicit per-call confirm. Every write is preview-first and reversible or backed up.
- **Bulk `entity_id` renames / pattern-regex rewrites.** HA does not rewrite references, so a bulk id change would silently break automations, scripts, templates, scenes, and dashboards for exactly the non-expert users least able to recover. Only the low-risk friendly-name override is offered; leave `entity_id` renames to HA's one-at-a-time UI.
- **Device merging / entity re-parenting.** HA exposes no supported device-merge API and entity→device links are integration-owned. At most, surface duplicate hints in the lint report and let the orphan-removal path clean up a dead twin.
- **A general spreadsheet / BI tool.** No binary-workbook (XLSX) output and the runtime dependency it would require; CSV plus text formats (JSON/NDJSON/YAML/Markdown/HTML) cover machine and human consumers dependency-free, and a UTF-8 BOM serves Excel.
- **A composite "health score."** A single 0–100 weighted number is opinionated and a support magnet; discrete counts, the `PROBLEM` binary_sensor, and the lint report carry the same signal unambiguously.
- **A custom Lovelace / JS frontend card.** A separate build toolchain, no reuse of the 13-locale Python strings, and constant frontend-API churn — the worst fit for a solo maintainer. Native entities + a built-in Markdown card + blueprints deliver most of the value at near-zero upkeep.
- **A built-in scheduler as the primary path.** A self-managed timer carries DST/timezone/double-run correctness burden. Prefer HA's native time triggers via bundled blueprints; any convenience timer that ever ships stays opt-in, default-off, and thin.
- **A bundled notifier.** The integration never hardcodes a notify target; the user chooses their own in a blueprint or per-call option.
