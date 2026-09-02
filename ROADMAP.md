# Roadmap

Ideas for kotoba_export, not yet built. Pick from here next session.

## Project infra (requested 2026-09-01, night before)

- **Create a GitHub repo and start tagging releases**, attaching the
  packaged `.ankiaddon` (like `kotoba_export-0.1.0.ankiaddon`) to each
  GitHub release. Not a git repo yet - needs `git init`, a remote, and
  probably a `.gitignore` (exclude `__pycache__`, the venv, built
  `.ankiaddon` files themselves if releases are the intended distribution
  point rather than committing binaries).

## Committed (requested 2026-09-01)

- **Export/import presets.** Right now presets live only in Anki's profile
  config store - the `.ankiaddon` package backs up the *code*, not your
  presets or advanced settings. Add a "Export presets to file" / "Import
  presets from file" pair (JSON) in the main dialog so presets can be backed
  up or moved to another machine on their own.

## Strong candidates

- **Multiple note types per preset.** A preset currently matches exactly one
  note type; anything else gets silently counted as "skipped." Your mining
  setup already spans at least two note types (whatever your main vocab
  note type is, plus the "Mining" note type behind 反撃 and friends), so
  "forgotten today" can't currently pull from both in one preset. Letting a
  preset select several note types (each with its own field mapping) would
  fix that.
- **"Open in Browser" from a preview row.** Right-click a row in the export
  preview -> jump straight to that note in Anki's Browser. Would have turned
  diagnosing the 反撃 citation bug into one click instead of a manual
  Browse search.
- **Duplicate/clone a preset.** Spin up a variant (e.g. "leeches - tag A"
  from "leeches - tag B") without rebuilding the field mapping from scratch.
- **Smarter comment formatting.** Instead of just truncating, insert a
  separator before recognized "(DictionaryName)" citation patterns so a long
  mined comment reads as distinct dictionary entries rather than one
  run-on wall of text. Lower-risk than trying to fully parse and keep only
  one dictionary (rejected earlier - too fragile, dictionary entries contain
  parentheses mid-definition too).

## Bigger / optional

- **"Run all" / one-click daily routine.** Fire off several presets (e.g.
  forgotten today + due + leeches) in one action instead of one at a time.
- **Scheduled/automatic export.** Run a preset automatically on Anki
  startup/shutdown or on a timer, no manual Tools-menu trip.
- **Export history log.** A small local record of past runs (deck name,
  card count, timestamp, success/fail) to track the habit over time and
  spot a run that silently produced 0 cards.
- **Retry/backoff for the direct API.** Kotoba rate-limits POST/PATCH
  (`postPatchLimiter`); matters more once "run all" exists and fires several
  uploads back to back.

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
`.ankiaddon` packaging.
