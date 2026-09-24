# Roadmap

Where Entity Assistant is going: from a hardened exporter to a **true entity assistant** — export the registries in any useful shape, edit them anywhere (a spreadsheet, a text editor, an automation), and apply the result back safely.

> **Export anything → edit anywhere → import safely.**

Milestone versions are indicative and will shift with maintainer time. For what has actually shipped, see [CHANGELOG.md](CHANGELOG.md); for task-driven recipes against shipped features, see [COOKBOOK.md](COOKBOOK.md).

## Reality: what Home Assistant allows

Everything the assistant needs is a supported public API. The user-editable surface per registry object:

| Object | Writable via public helpers | API |
| --- | --- | --- |
| Entity | `entity_id`, `name`, `icon`, `area_id`, `aliases`, `labels`, `categories`, `disabled_by`, `hidden_by` | `er.async_update_entity()` |
| Device | `name_by_user`, `area_id`, `labels`, `disabled_by` — devices have no `hidden_by` | `dr.async_update_device()` |
| Area | `name`, `floor_id`, `icon`, `aliases`, `labels`, `picture` | `ar.async_update()` / `async_create()` |
| Floor | `name`, `level`, `icon`, `aliases` (full CRUD) | `fr.*` |
| Label | `name`, `color`, `icon`, `description` (full CRUD) | `lr.*` |

Two identity facts make spreadsheet round-trips robust: every entity registry entry carries a stable ULID (`RegistryEntry.id`) that survives `entity_id` renames, and device/area/floor/label ids are already stable. Exports must carry these keys — the entity `registry_id` and the writable-but-missing entity/area fields shipped in 1.8.0 (see the 1.8 table); `floors`/`labels` export types are still to come.

The hard limits every item below respects:

1. **No device-merge API.** Entity→device links are integration-owned; there is no supported way to merge two device entries.
2. **Rename reference-rewriting is frontend-only.** `er.async_update_entity(new_entity_id=…)` exists and changes the id, but nothing server-side rewrites automations, scripts, templates, scenes, or dashboards — the "also rename references" magic is frontend code a backend integration cannot call. Id renames therefore require a per-call opt-in (`allow_entity_id_rename: true`) and a preview that greps `/config` for each old id, so the blast radius is visible before commit (see 2.0). Pattern/regex rewrites — where one bad pattern quietly renames the wrong bank — stay out.
3. **Removals cannot be undone.** No public API re-creates a registry entry with its old stable id. Journal-based undo covers *updates* only; a HA backup is the only real undo for removals, and every removal preview says so.
4. **Re-enabling entities reloads config entries.** When `disabled_by` clears, core schedules a reload of the owning config entry (~30 s, `RELOAD_AFTER_UPDATE_DELAY`). A bulk enable spanning 40 integrations is 40 reloads — manageable, but the preview must say how many.
5. **Services cannot accept file uploads.** Import v1 reads a file the user has placed inside `/config` (the existing `resolve_path` traversal guard applies). Native browser upload (`FileSelector` + the `file_upload` component) exists only in config/options/repairs flows, so a guided upload wizard is a later layer over the same engine.
6. **Services are not admin-gated by default.** HA's own registry websocket commands require admin; any authenticated user can call a custom service. Every mutating service here must resolve `call.context.user_id` and require an admin, raising `Unauthorized` otherwise.
7. **No transactional/batch registry API.** Every update fires a `*_registry_updated` event and schedules a store save; a 500-row commit is 500 events. Bulk writes chunk and yield to the loop, and the integration's own future listeners (coordinator) debounce.

## Design spine

Three unifications keep the assistant coherent as it grows:

1. **One change-plan model.** Every mutation — a bulk service, an imported file, a lint fix — compiles to the same plan: a list of `{object_type, key, field, from, to}` entries plus explicit creates/removes. Preview, confirm, journal, events, and undo are implemented once and shared by everything.
2. **One store.** The mutation spine's pre-commit backup and the snapshot feature are the same `helpers.storage.Store`: every commit auto-captures a snapshot, `capture_snapshot` is the manual version, and diff reuses the import comparator.
3. **Lint findings are importable.** The lint report's suggested fixes are emitted in import format — review the worklist in a spreadsheet, delete the rows you disagree with, and feed the rest back through the same gate.

Standing rules for every write: `dry_run: true` by default, explicit non-default `confirm: true` to apply, admin-only, journaled, evented, and undoable when it's an update.

## 1.7 — Trust gate — ✅ shipped

Tests, CI, and safety-gating on the one shipped mutation. Delivered in 1.7.0 (2026-09-09) and hardened in 1.7.1 (2026-09-13). See [CHANGELOG.md](CHANGELOG.md).

## 1.8 — Round-trip-ready export — 🚧 in progress

Everything import will need, shipped as additive export improvements — plus the configuration UX that stores defaults. This milestone *defines the import contract*. First slice (stable keys & writable-column completeness) shipped in 1.8.0.

| Capability | What it adds | Effort | Risk |
| --- | --- | --- | --- |
| Stable keys & writable-column completeness — ✅ 1.8.0 | Add `registry_id` (the stable ULID) to entity rows and export the writable-but-missing fields: entity `icon`, `aliases`, `categories`; area `icon`. Multi-value columns stay `", "`-joined in CSV with the comma-in-name limitation documented; JSON is the lossless round-trip format. | S | low |
| `floors` and `labels` export types | Complete registry coverage: floors (name, level, icon, aliases, area count) and labels (name, color, icon, description, usage counts). Both become importable later. | S | low |
| Structured output formats (JSON, NDJSON, YAML) | `output_format` option beside `csv`, dispatched through services, signed URL, and HTTP view (`Content-Type` + extension). `json` is stdlib; PyYAML ships in core — no manifest requirement. | S | low |
| Sorting & grouping controls | `sort_by` / `sort_dir` / optional `group_by` (area / domain / floor) applied before serialization with a stable sort; guarded against unknown columns. | S | low |
| Inline data return | `return_data: true` so `export_csv` returns `columns` + `rows` in its already-`OPTIONAL` response with no file touched — template sensors and dashboards, direct. Opt-in with a row cap. | S | low |
| Per-run download filename + `Content-Disposition` | Caller-supplied download filename (e.g. `entities_{date}`), sanitized to a bare basename, extension derived from `output_format`. Dated names stop overwriting each other. | S | low |
| User-selectable & reorderable column sets | `columns` option (ordered list) + named presets per export type, validated against known columns. Short exports for non-experts; exact shapes for power users. | M | low |
| Registry-aware service selectors | `areas` → area selector, `domains` → multi-select with custom values. **No Python change**; backward compatible with existing YAML. The cheapest UX win on the board. | S | low |
| Consolidated options flow | One `OptionsFlow` persisted to `entry.options` — export defaults now, spine/retention/threshold knobs later. Button reads options at press time (today it hardcodes defaults). Do **not** assign `self.config_entry` in the flow (HA ≥2024.11 provides it). | S | low |
| Config-entry migration stub + compat policy | `async_migrate_entry` stub + versioned options schema before the options flow and stores evolve; feature-detection for version-gated APIs on the min-supported core (2024.11). | S | low |
| In-product onboarding | Config-flow "getting started" text and/or a one-time notification pointing new users to the button, services, and docs. Cuts "how do I use this" support load. | S | low |

## 1.9 — Safety spine, proven small

The mutation framework, its storage, and the lowest-risk bulk edits to prove it in the field before import rides it.

| Capability | What it adds | Effort | Risk |
| --- | --- | --- | --- |
| Change-plan model + preview/commit | The shared compile → preview → confirm pipeline: `dry_run: true` returns the structured plan via `SupportsResponse`; `confirm: true` applies; `entity_assistant_changes_applied` event. Large plans capped inline with optional write-to-file. Foundational; mutates nothing itself. | L | medium |
| Unified snapshot + journal store | `Store`-backed: pre-commit auto-snapshot + per-commit journal of before-values; `capture_snapshot` service for manual baselines before big changes; keep-last-N. One store powers undo now and diff in 2.0. | M | low |
| `undo_last` / `undo` | Replay journal before-values in reverse. Updates only — previews state plainly that removals are not undoable (limit 3 above). | M | medium |
| Admin enforcement | Shared guard on every mutating service: resolve `call.context.user_id`, require admin, raise `Unauthorized`. Applied to the 1.7-retrofitted `remove_orphaned` too. | S | low |
| Bulk (re)assign area & floor | Assign/move the filtered set of entities/devices to an area, set an area's floor, optional auto-create. The single most common post-install chore; fully reversible. | M | low |
| Bulk label curation | Set-union / set-difference / set-replace of labels across entities, devices, and areas, auto-creating missing labels. Lowest-risk mutation; the confidence-builder. | M | low |
| `remove_orphaned` rides the spine | The retrofitted service gains journal + auto-snapshot + the shared plan format, replacing its bespoke 1.7 gating. | S | low |
| Executor offload & performance budget | Move build/serialize/parse off the event loop, stream large downloads, set a perf budget — ahead of the event storms bulk commits cause (limit 7). | M | medium |
| Uninstall & teardown | `async_remove_entry` cleaning integration-authored files, snapshots, and journals; self-pruning stores; document that the HTTP view persists until restart. Lands with the first storage-backed feature, not after. | S | low |

## 2.0 — Import: the assistant milestone

The release that earns the name. Export → edit in any spreadsheet → import back through the full gate.

| Capability | What it adds | Effort | Risk |
| --- | --- | --- | --- |
| `import_changes` service | Path-based (config-dir only, `resolve_path` guard), CSV or JSON. **Patch semantics**: only a whitelisted set of writable columns, only rows present in the file. Keyed by `registry_id` / `device_id` / `area_id` / `floor_id` / `label_id` (fallback to `entity_id` with a warning when the column is absent); unknown keys warned and skipped; opt-in auto-create of areas/floors/labels by name. Compiles to the standard change plan → dry-run preview → confirm. **Import never removes anything.** | L | medium |
| `entity_id` rename via import (opt-in) | Extends `import_changes`: when the input contains an `entity_id` column and the call passes `allow_entity_id_rename: true` (off by default), the id becomes writable. Preview greps `/config` for each old id and lists file:line hits (YAML, dashboards, blueprints, `.storage/lovelace*`) so the blast radius is visible before commit; commit writes `renames.csv` (`old_id,new_id`) beside the input for a follow-up find-and-replace on config the integration can't rewrite. Keyed by `registry_id` so a row keeps pointing at the same entity after its id changes mid-batch. History and long-term statistics migrate with the entity; registry-side links (device, area, labels) are unaffected. **Motivating case**: per-circuit energy monitors (Emporia Vue), where users want breaker-position ids (`sensor.breaker_15_power`) instead of the vendor app's friendly names across 100+ CTs. | M | medium |
| Import parser hardening | The realities of Excel round-trips: strip the formula-sanitization tab prefix, accept `utf-8-sig`, sniff `,`/`;` delimiters, ignore unknown/read-only columns, strict boolean parsing, and a per-row error report in the preview instead of all-or-nothing failure. | M | low |
| Bulk enable / disable / hide / unhide | Flip `disabled_by` / `hidden_by` (USER) across the filtered set; pairs with `stale_only`. Reload-aware preview: names how many config entries core will auto-reload (limit 4) and warns when a target is referenced by automations/scenes. Devices: `disabled_by` only. | M | medium |
| Bulk set friendly name | Bulk-set the friendly-name override (`name`; `None` clears). `entity_id` is not bulk-editable through a filter-and-set service — use the import path with `allow_entity_id_rename: true` (see above) so the reference-scan preview runs. | S | low |
| Diff service | `entity_assistant.diff`: snapshot-vs-current using the same comparator import uses for file-vs-current. Categorized deltas (added, removed, renamed, moved, newly-stale, recovered); optional diff file + signed URL. | M | low |
| Granular change events | After diffs and commits: categorized events (entity added / removed / moved / newly-stale) carrying affected ids. Event names/payloads are a documented public contract. | S | low |

## 2.1+ — Health, lint & the advisor loop

With the actuator built, the advisor: native surfaces that find problems and hand them to import as ready-made fix files.

| Capability | What it adds | Effort | Risk |
| --- | --- | --- | --- |
| Shared summarizer + debounced coordinator | Refactor the registry walk into a reusable summarizer feeding a `DataUpdateCoordinator`, recomputing on registry-updated events + a light interval, debounced against startup churn and bulk-commit event storms. | M | low |
| Registry count sensors + Recorder hygiene | Curated `DIAGNOSTIC`/`MEASUREMENT` sensors (total, stale, unavailable, orphaned, missing-area, unnamed) with breakdowns as attributes; long tail ships `entity_registry_enabled_default=False`; documented `exclude` guidance. | M | low |
| "Registry has problems" binary_sensor | One `PROBLEM`-class entity, `on` when any high-confidence count exceeds its threshold, attributes naming the tripped categories. One clean automation hook. | S | low |
| On-demand diagnostics health report | `diagnostics.py` powering HA's native Download diagnostics: totals, per-domain/area counts, offenders, options, recent snapshots + latest diff. Free-text fields through `async_redact_data`. | S | low |
| Registry lint report → importable fix files | `lint` export type: one row per issue (`rule`, `severity`, `detail`, `suggested_fix`) covering missing area, unnamed, duplicate names, duplicate identifiers, orphaned, restored-not-provided. `emit_fixes` writes the suggestions in import format — review, prune, apply. | M | low |
| Device-class & unit sanity linting | Metrological mismatches (device_class vs unit, unit with no class, numeric class with non-numeric state) against the running core's `DEVICE_CLASS_UNITS`, degrading gracefully if the import moves. | M | medium |
| Human-readable reports (Markdown + accessible HTML) | `rows_to_markdown` / `rows_to_html`, dependency-free, escaped, semantic tables, WCAG-AA. Paste an audit into an issue or a dashboard card. | M | low |
| Redaction / anonymization mode | Opt-in hashing/stripping of user-named fields across all formats. Makes "paste this into a forum" actually safe. | M | low |
| Deliver the export through a notify service | Per-call option minting a signed URL and sending it + summary counts through a user-named notify target (legacy and `notify.send_message` styles). Documents the bearer-token nature. | M | medium |
| Bundled blueprint automations | "Export nightly and notify" and "alert on new stale/orphaned" blueprints over the events and sensors. The low-upkeep alternative to a built-in scheduler. | S | low |
| Snapshot history & retention management | `list_snapshots` / `get_snapshot` / `prune_snapshots`, retention policy in the options flow. Prune touches only the integration's own store. | M | low |
| Repairs surface (informational) | One coordinated strategy raising deduplicated, self-clearing issues in Settings → Repairs for unambiguous problems; `is_fixable=False` in v1. | M | medium |

## Later — guided fixes & reach

- **Guided import upload** — `FileSelector` + `file_upload` in an options/repairs flow so users upload from the browser instead of dropping a file into `/config`; the same import engine and gate underneath (limit 5).
- **Guided fix-flows in Repairs** — `RepairsFlow` wizards layered over the spine for the lint/repairs findings.
- **Assist / conversation intents** — "how many stale entities do I have", "export my entity list", answered from the shared summarizer.
- **Change-count analytics sensors** — added/removed/renamed/newly-stale counts from the latest diff, once diffs run on a cadence.
- **HACS default store + `home-assistant/brands` submission** — external-latency-bound and independent of the milestones; can go whenever bandwidth allows. The brands PR is already outstanding and closes the placeholder-icon gap for pre-2026.3.0 installs.
- **`quality_scale` + core-submission readiness** — once the feature surface has settled.

## Dependency summary

Tests (1.7) → spine (1.9) → reversible bulk edits (1.9–2.0) → import (2.0) → guided fix-flows (Later). Export contract (1.8: stable keys, formats, column completeness) → import parser (2.0). Unified store (1.9) → undo (1.9) → diff + change events (2.0) → retention + cadence sensors (2.1+). Summarizer (2.1) → sensors, binary_sensor, diagnostics, lint → fix files → back into import. Options flow (1.8) → stored defaults, thresholds, retention.

## Non-goals

Deliberately out of scope, to protect the maintainer's time and the integration's safety posture:

- **Cloud sync, telemetry, or any external service.** Everything stays local. No usage analytics, no remote storage, no phone-home.
- **Auto-mutation without confirmation.** The registries are never modified as a side effect, on a schedule, or without an explicit per-call confirm. Every write is preview-first and reversible or backed up.
- **Mutations over bearer links.** Signed URLs remain export-only; no import, removal, or bulk endpoint is ever reachable via a time-limited unauthenticated link.
- **Full-sync import / import-driven deletion.** Import is patch-only: it changes writable fields on rows it can key and never removes registry entries. Removal lives exclusively in the separately gated remove path.
- **Pattern/regex `entity_id` rewrites and `new_unique_id` changes.** Explicit per-row `entity_id` renames are supported through import with `allow_entity_id_rename: true` (see 2.0), because the reference-scan preview makes the blast radius visible before commit. Pattern-regex rewrites don't — one bad pattern quietly renames the wrong bank of entities — so they stay out. `new_unique_id` stays out entirely: it can collide with what the provider integration will re-emit on next reload.
- **Device merging / entity re-parenting.** No supported API (limit 1). At most, surface duplicate hints in the lint report and let the orphan-removal path clean up a dead twin.
- **A general spreadsheet / BI tool.** No binary XLSX output and the runtime dependency it would require; CSV + JSON/NDJSON/YAML/Markdown/HTML cover machine and human consumers dependency-free, and the UTF-8 BOM serves Excel.
- **A composite "health score."** Discrete counts, the `PROBLEM` binary_sensor, and the lint report carry the same signal unambiguously.
- **A custom Lovelace / JS frontend card.** A separate build toolchain, no reuse of the 13-locale strings, constant frontend-API churn — and unnecessary: with round-trip import, *the user's spreadsheet is the bulk-edit UI*.
- **A built-in scheduler as the primary path.** HA's native time triggers via bundled blueprints; any convenience timer stays opt-in, default-off, and thin.
- **A bundled notifier.** The user picks their own notify target in a blueprint or per-call option.
