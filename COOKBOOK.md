# Cookbook

Task-driven recipes for Entity Assistant. Each one is a real problem, the exact
service call or automation that solves it, and what you get back. For the full
option reference, see [README.md](README.md); for version history, see
[CHANGELOG.md](CHANGELOG.md); for where the integration is going, see
[roadmap.md](roadmap.md).

Every recipe uses only what ships today (1.7.x). Forward-looking recipes —
bulk edits, imports, `entity_id` renames — will land here as those features do.

## Slicing your export

### Just the lights in the living room

Filter by domain and area in one call.

```yaml
action: entity_assistant.export_csv
data:
  filename: living_room_lights.csv
  domains: [light]
  areas: [Living Room]
```

Areas accept either the `area_id` (`living_room`) or the display name
(`Living Room`). `domains` only applies when `export_type` is `entities`
(the default).

### Every unavailable, orphaned, or restored entity

Cleanup starts with a list. `stale_only` returns just the rows flagged by
the stale detector.

```yaml
action: entity_assistant.export_csv
data:
  filename: stale.csv
  stale_only: true
  stale_days: 30
```

The `stale_reason` column tells you *why* — `unavailable`, `orphaned`,
`restored`, `not_changed_30d`, or a comma-separated combination.

### A dated weekly snapshot

Run the export on a schedule and stamp the filename so weekly files don't
overwrite each other.

```yaml
alias: Entity Assistant — weekly snapshot
triggers:
  - trigger: time
    at: "03:00:00"
conditions:
  - condition: time
    weekday:
      - sun
actions:
  - action: entity_assistant.export_csv
    data:
      filename: "exports/entities_{{ now().strftime('%Y-%m-%d') }}.csv"
```

The `exports/` subfolder is created automatically inside `/config`.

### A CSV that opens cleanly in Excel

Accented characters (`é`, `ü`, `ø`) render as mojibake in Excel on Windows
unless the file starts with a UTF-8 BOM.

```yaml
action: entity_assistant.export_csv
data:
  filename: entity_export.csv
  utf8_bom: true
```

LibreOffice, Numbers, Google Sheets, and every text-processing tool are fine
without it — flip this on only when Excel is your destination.

## Getting the file out of Home Assistant

### A one-click download link on a dashboard

Mint a signed URL and hand it to a button / markdown card. No auth header
needed, works from a phone.

```yaml
action: entity_assistant.get_download_url
data:
  export_type: entities
  expires: 600
response_variable: dl
```

`dl.url` is a `https://<your-ha>/api/entity_assistant/export.csv?...&authSig=…`
URL valid for the number of seconds you pass (default 120). Use it as the
`link` of a button card, or open it directly in a script.

### Pull today's export from a shell script

The HTTP endpoint is authenticated. Use a
[long-lived access token](https://www.home-assistant.io/docs/authentication/#your-account-profile)
to fetch from cron, a NAS, or any other script.

```bash
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  "http://homeassistant.local:8123/api/entity_assistant/export.csv?export_type=devices&only_enabled=true" \
  -o devices.csv
```

Query flags mirror the service options exactly: `export_type`,
`include_disabled`, `include_hidden`, `only_enabled`, `stale_only`,
`stale_days`, `utf8_bom`, `domains`, `areas` (the last two comma-separated).

### Email the export after every write

Fire on the `entity_assistant_export_completed` event so you don't have to
guess when the file appeared.

```yaml
alias: Email entity export
triggers:
  - trigger: event
    event_type: entity_assistant_export_completed
actions:
  - action: notify.email_me
    data:
      title: "Entity export ({{ trigger.event.data.row_count }} rows)"
      message: "Written to {{ trigger.event.data.path }}"
      data:
        attachment:
          file: "{{ trigger.event.data.path }}"
```

`triggered_by` on the event tells you whether the export came from the
button, a service call, or the HTTP endpoint — useful if you only want to
attach automated exports and not ad-hoc button presses.

## Cleaning up orphans

### Preview first, then remove

`remove_orphaned` defaults to `dry_run: true` — it returns the would-remove
lists without touching anything.

```yaml
action: entity_assistant.remove_orphaned
response_variable: preview
```

`preview` contains `entities_removed`, `devices_removed`, `areas_removed`
(counts) and `entity_ids`, `device_ids`, `area_ids`. On a dry run, those
counts describe what *would* be removed. If the list looks right, run it
again with `confirm: true` to apply.

```yaml
action: entity_assistant.remove_orphaned
data:
  confirm: true
```

Both calls require the calling user to be an admin — a non-admin call
raises `Unauthorized`.

### Take a backup before the removal

Removals aren't undoable — the only complete undo is a Home Assistant
backup. Wire one into the same automation.

```yaml
alias: Snapshot then remove orphans
actions:
  - action: backup.create
  - delay: "00:00:30"
  - action: entity_assistant.remove_orphaned
    data:
      confirm: true
```

Use whichever backup service your instance has set up (`backup.create` on
recent core versions). The 30-second delay gives the backup task room to
actually write before the mutation runs.

### Ping my phone when orphans were removed

Listen for `entity_assistant_orphaned_removed` and send yourself the
counts.

```yaml
alias: Orphan cleanup notification
triggers:
  - trigger: event
    event_type: entity_assistant_orphaned_removed
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: Registry cleanup
      message: >-
        Removed {{ trigger.event.data.entities_removed }} entities,
        {{ trigger.event.data.devices_removed }} devices,
        {{ trigger.event.data.areas_removed }} areas.
```

The event fires whether the call came from a service, an automation, or a
future UI trigger — one automation covers all of them.

## Watching the assistant

### Alert me when an export fails

The `last_export` sensor's state stays pinned to the last *successful*
export, so a failure is silent unless you watch the failure event.

```yaml
alias: Entity export failed
triggers:
  - trigger: event
    event_type: entity_assistant_export_failed
actions:
  - action: persistent_notification.create
    data:
      title: Entity export failed
      message: >-
        {{ trigger.event.data.error_type }}: {{ trigger.event.data.error }}
        (path: {{ trigger.event.data.path }})
```

Same pattern works for a mobile push (`notify.mobile_app_*`) or any other
notify service. `error_type` is the exception class name so you can branch
on it — `FileNotFoundError`, `PermissionError`, `OSError` (disk full), etc.
