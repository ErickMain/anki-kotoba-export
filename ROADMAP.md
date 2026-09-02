# Roadmap

Ideas for kotoba_export, not yet built. Pick from here next session.

## Strong candidates

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
export/import presets (JSON, upserts by id), multiple note types per preset
(each with its own field mapping, with automatic migration of pre-0.3.0
single-note-type presets), `.ankiaddon` packaging, GitHub repo with tagged
releases carrying the packaged addon
([ErickMain/anki-kotoba-export](https://github.com/ErickMain/anki-kotoba-export),
first release: [v0.1.0](https://github.com/ErickMain/anki-kotoba-export/releases/tag/v0.1.0)).

### Release process (for next time)

1. Bump `human_version` in `kotoba_export/manifest.json`.
2. Rebuild the zip: from `anki-kotoba-export/`, clear `__pycache__` under
   `kotoba_export/`, then `Compress-Archive -Path .\kotoba_export\* -DestinationPath .\kotoba_export-<version>.ankiaddon`.
3. Commit, `git tag -a v<version> -m "v<version>"`, `git push origin main --tags`.
4. `gh release create v<version> .\kotoba_export-<version>.ankiaddon --title "..." --notes "..."`.
