# AnkiWeb listing draft

Not part of the add-on itself - text to paste into the submission form at
https://ankiweb.net/shared/addons/ (Upload button, requires an AnkiWeb
login). AnkiWeb's exact field names/limits aren't visible without being
logged in, so treat section breaks below as a guide to adapt, not a rigid
template. Update the [Repo link](#) placeholders below with the actual
repo URL if this file is ever copied elsewhere.

## Title

Kotoba Export

## Short description / tagline

Export Anki cards to kotobaweb.com "Type the reading!" custom decks, with
saved presets for recurring study sessions (forgotten today, leeches, by
tag...) and optional one-click upload.

## Full description

Fast export from Anki to [kotobaweb.com](https://kotobaweb.com)'s "Type
the reading!" custom quiz decks - built for people who use Kotoba's
Discord bot for reading-practice reviews alongside Anki.

**What it does:**
- Save a search as a reusable preset (forgotten today, leeches, suspended,
  due, tags, deck, or a raw Anki search - any combination), with per-note-type
  field mapping to Kotoba's Question/Answer/Comment columns.
- Preview matched cards before anything is sent anywhere.
- Deliver via a CSV file (the default - save it, then use Kotoba's own
  "Import from File" on their New Custom Deck page) or, if you opt in to
  Advanced settings with your Kotoba session cookie, upload directly with
  one click, including overwriting the same deck on repeat runs.
- Optional unattended export on Anki startup/shutdown/AnkiWeb sync, with
  every run (success or failure) logged to a local history you can export
  to CSV.

**No API key needed** - Kotoba doesn't have one. The default delivery path
needs no setup at all; direct upload is fully opt-in and clearly labeled
as using an internal, undocumented API.

Full step-by-step guide: https://github.com/ErickMain/anki-kotoba-export/blob/main/USER_GUIDE.md

## Privacy / what this touches

- Reads your Anki collection's note fields for whichever notes match a
  preset's search - nothing is sent anywhere unless you explicitly Save or
  Upload from the preview screen (or enable automatic export, which is off
  by default and requires its own explicit opt-in).
- The default delivery path (save as CSV) sends nothing over the network
  itself; you choose when to hand that file to Kotoba's own site.
- Advanced mode (opt-in) sends card content to kotobaweb.com's API,
  authenticated with a session cookie you paste in yourself. That cookie
  is a real credential - see the add-on's own warning text before
  enabling it.
- No telemetry, no analytics, no third-party service other than
  kotobaweb.com (and only when you use advanced mode).

## Known limitations (worth stating up front)

- Depends on an undocumented, unversioned Kotoba API for the optional
  direct-upload path; it could change or break without warning. The
  default CSV path doesn't depend on it.
- Requires Anki 25.02+ (Qt6) - Anki itself will refuse to load it on
  anything older rather than crashing on open.

## Suggested tags

anki, japanese, language-learning, export, kotoba, discord, srs

## Support

Issues/bugs: https://github.com/ErickMain/anki-kotoba-export/issues
