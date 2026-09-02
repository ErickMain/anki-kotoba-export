# Roadmap

Ideas for kotoba_export, not yet built. Pick from here next session.

## Requested 2026-09-02 (during "let it run for real for a few days")

- **Export History to CSV.** A "Export to CSV..." button in the History
  dialog (alongside "Clear history"), dumping the current log to a file -
  same shape as the existing preset export/import, just for history
  instead of presets. Lets the real-use test period leave a record outside
  Anki's own config store.
- **Automatic export on AnkiWeb sync**, as a third trigger alongside
  startup/shutdown - `Preset.auto_run` gets a `"sync"` option (and syncs
  into the "both" story: probably becomes a proper set of trigger flags
  rather than a single off/startup/shutdown/both enum once there are three
  triggers instead of two). Likely hook: `gui_hooks.sync_did_finish`. Worth
  noting this is actually a *better* fit than shutdown for "forgotten
  today"-style presets on a routine of review-then-sync, and doesn't carry
  the same "delays Anki closing" risk shutdown does - though it could still
  add a pause right after sync finishes if the upload is slow.
- **Export duration.** Track and show how long each run took (probably a
  `duration_seconds` field on `HistoryEntry`, shown as a column in the
  History dialog). Best guess at intent: a lightweight way to keep an eye
  on the "shutdown-triggered auto-export can hang Anki's close for ~15s if
  Kotoba is slow" risk that came up when discussing what's least tested -
  if that reading is wrong, correct it when this gets picked up.

## Bigger / optional

- **Retry/backoff for the direct API.** Kotoba rate-limits POST/PATCH
  (`postPatchLimiter`). No longer hypothetical now that "run all" and
  automatic startup/shutdown export both exist and can fire several uploads
  back to back - worth picking up next if a run ever hits a 429.

## Low priority - only if it turns out to matter

- Combine multiple Anki fields into one Answers list (e.g. separate
  "Reading" + "Reading Alt" fields, not just comma-separated within one
  field).
- Remember the last-selected preset when reopening the main dialog.

## Already shipped (for reference, not roadmap)

Clipboard/CSV export, advanced direct-API mode with cookie auth, preset
query builder (state chips + tags + deck + raw search), field mapping with
Image/Text render choice, duplicate-question auto-merge, comment length
capping, citation-pattern sanity warning, ruby-tag (`<ruby><rt>`) furigana
resolution, name-keyed deck overwrite linking, deck manager (list/delete),
export/import presets (JSON, upserts by id), multiple note types per preset
(each with its own field mapping, with automatic migration of pre-0.3.0
single-note-type presets), "open in Browser" from a right-clicked preview
row (tracks source note id(s) through duplicate-question merging),
duplicate/clone a preset (fresh id, no shared deck_links, opens the editor
for tweaking before it's saved), smarter comment formatting (line break
before a recognized dictionary-source marker like "(大辞林 第四版)" or
"(JMdict)", verified against real mined data with no false positives on
incidental parens like "(cannot)" - confirmed rendering as real line breaks
in Discord), "run all" (multi-select the preset list, ctrl/shift-click, and
Run fires each one's preview in turn - e.g. forgotten today + due + leeches
in one action), export history log (main dialog -> History..., a capped
log of every export - manual and automatic - with preset/deck/card
count/outcome/trigger), scheduled/automatic export (per-preset "Automatic
export: startup/shutdown/both", gated by a global switch in Advanced
settings so nothing runs unless both are explicitly on; unattended runs
always go through direct-API upload and log to history even when skipped,
so a misconfiguration is visible instead of silent; verified end-to-end
against a real Anki restart, both triggers), `.ankiaddon` packaging, GitHub
repo with tagged releases carrying the packaged addon
([ErickMain/anki-kotoba-export](https://github.com/ErickMain/anki-kotoba-export),
first release: [v0.1.0](https://github.com/ErickMain/anki-kotoba-export/releases/tag/v0.1.0)).

### Release process (for next time)

1. Bump `human_version` in `kotoba_export/manifest.json`.
2. Rebuild the zip: from `anki-kotoba-export/`, clear `__pycache__` under
   `kotoba_export/`, then `Compress-Archive -Path .\kotoba_export\* -DestinationPath .\kotoba_export-<version>.ankiaddon`.
3. Commit, `git tag -a v<version> -m "v<version>"`, `git push origin main --tags`.
4. `gh release create v<version> .\kotoba_export-<version>.ankiaddon --title "..." --notes "..."`.

### Development note

`preset_editor.py` and `settings_dialog.py` both eventually grew past a
fixed `resize()` height on a smaller screen, cutting off Save/Cancel (or a
checkbox right above them) with no obvious sign anything was missing - hit
twice, cost a debugging session the second time. Both now wrap their
content in a `QScrollArea`, with Save/Cancel outside it so they're always
reachable. Any dialog that keeps gaining fields over time (rather than
staying fixed-purpose, like `note_type_mapping_dialog.py`) should get the
same treatment before it becomes a problem, not after.
