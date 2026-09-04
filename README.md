# Kotoba Export (Anki add-on)

Fast export of Anki cards to [kotobaweb.com](https://kotobaweb.com) "Type the reading!" custom decks, with saved presets for recurring study sessions (forgotten today, leeches, suspended, by tag...).

Repo: [github.com/ErickMain/anki-kotoba-export](https://github.com/ErickMain/anki-kotoba-export) · [Releases](https://github.com/ErickMain/anki-kotoba-export/releases) (grab the `.ankiaddon` from the latest one to install) · [User Guide](USER_GUIDE.md) (step-by-step walkthrough)

## Why there's no "just click connect"

Kotoba's backend only supports login via Discord OAuth2 + a browser session cookie - there's no API key. So this add-on has two delivery modes:

- **CSV file export (default, no setup):** builds the exact CSV Kotoba's own custom-deck importer expects and saves it to a file. On kotobaweb.com: New Custom Deck -> Import from File -> pick that file (Kotoba's import is file-based - there's no "paste a CSV" option on their end). Nothing here can be broken by a Kotoba login change.
- **Advanced / direct API (opt-in):** paste your kotobaweb.com session cookie into *Kotoba Export -> Advanced settings* and the add-on will upload decks for you with one click, including overwriting the same deck on repeat runs. This uses an internal, undocumented API and your session cookie is a bearer secret - treat it like a password. See the warning text in that dialog for how to grab the cookie from DevTools. A rate-limited (429) or transiently-down (502/503/504) response is retried automatically with backoff - no setting to configure - before it surfaces as an error; automatic/unattended exports use a smaller retry budget than an interactive upload, since a retry adds real (if bounded) delay during Anki's own startup/shutdown/sync.

## Install

Requires Anki 2.1.50+ on a **Qt6** build. Anki 2.1.50 shipped separate Qt5
and Qt6 packaged builds side by side, and this add-on uses Qt6-only enum
syntax throughout its dialogs (e.g. `Qt.ItemFlag.ItemIsUserCheckable`) -
Anki's PyQt5-compatibility shims don't cover that direction, so it will
fail to open any dialog on a Qt5 build even though its version number
qualifies. If in doubt, install a recent Anki release (Qt6 has been the
default packaged build for a long time).

**From a release (recommended for a second machine):** download the `.ankiaddon` from the [latest release](https://github.com/ErickMain/anki-kotoba-export/releases/latest), then in Anki: Tools -> Add-ons -> Install from file.

**From source (development):**

1. Close Anki if it's running.
2. Copy the `kotoba_export` folder into your Anki add-ons folder:
   - Windows: `%APPDATA%\Anki2\addons21\kotoba_export`
   - macOS: `~/Library/Application Support/Anki2/addons21/kotoba_export`
   - Linux: `~/.local/share/Anki2/addons21/kotoba_export`
3. Start Anki. You'll get a **Tools -> Kotoba Export...** menu item, and an **Export selected to Kotoba...** item in the Browser's right-click / Notes menu.

To package it for sharing/AnkiWeb instead, zip the *contents* of `kotoba_export/` (not the folder itself) into a `.ankiaddon` file.

## Using it

1. **Tools -> Kotoba Export... -> New...** to create a preset: **Add note type...** for each note type it should pull from, mapping each one's fields to Expression / Reading (kana) / Meaning (a preset can span several note types at once - e.g. a mining note type and a regular vocab note type - each gets its own mapping since field names rarely match across them). Then choose which state/tag/deck filters to match (Forgotten today, Leech, Suspended, Due, tags, deck, or a raw Anki search), and set the instructions text (defaults to "Type the reading!").
2. **Run** a preset (or select notes in the Browser and use **Export selected to Kotoba...**) to preview the matched cards, then either save it as a file or (advanced mode) upload directly. Ctrl+click or Shift+click to select several presets first - Run then fires each one's preview in turn, so your whole daily routine (forgotten today + due + leeches, say) is one action instead of repeating it per preset. Right-click a row in a preview to jump straight to its note (or notes, if a duplicate question merged more than one) in Anki's Browser. For mined notes whose Meaning field concatenates several dictionaries with no separator, the Comment gets a line break inserted before each recognized dictionary marker (e.g. "(大辞林 第四版)", "(JMdict)") so it reads as distinct entries in Discord instead of one wall of text - genuine parenthetical asides mid-definition are left alone.
3. Presets set to "Overwrite same deck" only work in advanced mode, since re-using a deck requires remembering its Kotoba deck id and edit secret between runs.
4. **Duplicate...** clones the selected preset (new name, everything else copied) and opens it in the editor to tweak before saving - handy for variants like "leeches - N3" from "leeches - N4". The clone starts with no Kotoba deck link of its own, even in Overwrite mode, so it won't touch the original's deck until it's run.
5. **Export presets... / Import presets...** back up your presets to a JSON file or move them to another machine. This only covers presets - not your advanced-mode session cookie, and not the `.ankiaddon` package itself (that's the code; see Install above). Importing upserts by id, so re-importing the same file updates existing presets rather than duplicating them; note type and field mappings should be double-checked after importing onto a different collection, since they're matched by name.
6. **History...** shows a log of past runs - preset, deck, card count, outcome, trigger, and how long it took - so you can tell at a glance whether a run actually did anything. **Export to CSV...** there saves the full log to a file (chronological order) if you want to track it outside Anki, e.g. in a spreadsheet. Duration is the delivery action's own time for a manual run, or the full search+build+upload for an automatic one - the number worth watching if you're wondering whether a shutdown-triggered preset is adding a noticeable pause when you close Anki.
7. **Automatic export**: a preset's editor has three "Automatic export on" checkboxes - Anki startup, Anki shutdown, and AnkiWeb sync finishing - check any combination, for running it unattended straight to Kotoba via direct-API upload, no preview, since there's no one there to click Upload. This needs two things to actually be on: at least one of the preset's own checkboxes, *and* "Enable automatic export" in Advanced settings (a global switch, off by default). "Forgotten today"-style presets belong on shutdown or sync, not startup - startup fires before you've reviewed anything that day. Shutdown- or sync-triggered runs can add a brief pause (they wait on the network request) - shutdown delays Anki closing, sync delays returning control right after the sync finishes. Anything unexpected - network failure, no cards, the switch not actually being on - gets logged to History instead of interrupting Anki.

## Development

Pure logic (query building, field cleanup, CSV formatting, the Kotoba API client) lives under `kotoba_export/kotoba/` and has no dependency on `aqt`/Anki, so it's covered by plain pytest:

```bash
pip install pytest
pytest tests/
```

GUI code (`kotoba_export/gui/`) needs a real Anki install to exercise.
