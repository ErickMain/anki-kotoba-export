# Kotoba Export (Anki add-on)

Fast export of Anki cards to [kotobaweb.com](https://kotobaweb.com) "Type the reading!" custom decks, with saved presets for recurring study sessions (forgotten today, leeches, suspended, by tag...).

Repo: [github.com/ErickMain/anki-kotoba-export](https://github.com/ErickMain/anki-kotoba-export) · [Releases](https://github.com/ErickMain/anki-kotoba-export/releases) (grab the `.ankiaddon` from the latest one to install)

## Why there's no "just click connect"

Kotoba's backend only supports login via Discord OAuth2 + a browser session cookie - there's no API key. So this add-on has two delivery modes:

- **Clipboard export (default, no setup):** builds the exact CSV Kotoba's own custom-deck importer expects, copies it to your clipboard, and opens kotobaweb.com. You paste it into "New Custom Deck -> Import". Nothing here can be broken by a Kotoba login change.
- **Advanced / direct API (opt-in):** paste your kotobaweb.com session cookie into *Kotoba Export -> Advanced settings* and the add-on will upload decks for you with one click, including overwriting the same deck on repeat runs. This uses an internal, undocumented API and your session cookie is a bearer secret - treat it like a password. See the warning text in that dialog for how to grab the cookie from DevTools.

## Install

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
2. **Run** a preset (or select notes in the Browser and use **Export selected to Kotoba...**) to preview the matched cards, then either copy the CSV + open Kotoba, save it as a file, or (advanced mode) upload directly. Ctrl+click or Shift+click to select several presets first - Run then fires each one's preview in turn, so your whole daily routine (forgotten today + due + leeches, say) is one action instead of repeating it per preset. Right-click a row in a preview to jump straight to its note (or notes, if a duplicate question merged more than one) in Anki's Browser. For mined notes whose Meaning field concatenates several dictionaries with no separator, the Comment gets a line break inserted before each recognized dictionary marker (e.g. "(大辞林 第四版)", "(JMdict)") so it reads as distinct entries in Discord instead of one wall of text - genuine parenthetical asides mid-definition are left alone.
3. Presets set to "Overwrite same deck" only work in advanced mode, since re-using a deck requires remembering its Kotoba deck id and edit secret between runs.
4. **Duplicate...** clones the selected preset (new name, everything else copied) and opens it in the editor to tweak before saving - handy for variants like "leeches - N3" from "leeches - N4". The clone starts with no Kotoba deck link of its own, even in Overwrite mode, so it won't touch the original's deck until it's run.
5. **Export presets... / Import presets...** back up your presets to a JSON file or move them to another machine. This only covers presets - not your advanced-mode session cookie, and not the `.ankiaddon` package itself (that's the code; see Install above). Importing upserts by id, so re-importing the same file updates existing presets rather than duplicating them; note type and field mappings should be double-checked after importing onto a different collection, since they're matched by name.

## Development

Pure logic (query building, field cleanup, CSV formatting, the Kotoba API client) lives under `kotoba_export/kotoba/` and has no dependency on `aqt`/Anki, so it's covered by plain pytest:

```bash
pip install pytest
pytest tests/
```

GUI code (`kotoba_export/gui/`) needs a real Anki install to exercise.
