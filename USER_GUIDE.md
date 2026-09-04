# Kotoba Export - User Guide

A step-by-step walkthrough for using the add-on, from a blank install to a
deck live on kotobaweb.com. For the terser reference version and technical
details, see [README.md](README.md).

## 1. Install

1. Download the `.ankiaddon` from the [latest release](https://github.com/ErickMain/anki-kotoba-export/releases/latest).
2. In Anki: **Tools -> Add-ons -> Install from file...**, pick the downloaded file.
3. Restart Anki.
4. You now have a **Tools -> Kotoba Export...** menu item, and an **Export
   selected to Kotoba...** item in the Anki Browser's right-click / Notes menu.

Requires Anki 2.1.50+ on a Qt6 build (the packaged build most people have -
see README if you're on an unusually old install).

## 2. Create your first preset

A **preset** is a saved combination of "which cards to pull" + "how to map
their fields onto a Kotoba deck". You'll normally set one up once per study
routine (e.g. "forgotten today", "leeches") and just re-run it after that.

1. **Tools -> Kotoba Export...** opens the main dialog.
2. Click **New...**.
3. Give it a name, e.g. `Forgotten today`.
4. Click **Add note type...** - pick the Anki note type this preset should
   pull from, then map its fields:
   - **Expression / word field**
   - **Reading (kana) field**
   - **Meaning field**
   You only need an expression or a reading field at minimum. Click OK.
   (A preset can map several note types at once - repeat **Add note
   type...** for each - handy if you study from more than one note type,
   e.g. a mining deck and a regular vocab deck, since their field names
   rarely match.)
5. Under **Which cards to include**, check any combination of:
   - **Forgotten today** (pressed Again today)
   - **Leeches**
   - **Suspended**
   - **Due**
   plus optionally **Tags** to require, a **Deck** to restrict to, and/or a
   raw **Advanced Anki search** string. Everything checked applies together
   (AND, not OR).
6. Under **Kotoba deck ('Type the reading!' style)**, the defaults are
   already right for a reading-practice deck (Question = Expression,
   Answer = Reading, Comment = Meaning, Instructions = "Type the reading!").
   Change these if you want a different layout.
7. Click **Save**.

## 3. Run it and get the cards into Kotoba

1. Select your preset in the list and click **Run** (or, in the Browser,
   select some notes and use **Export selected to Kotoba...** for an
   ad-hoc export with no preset).
2. A preview opens showing exactly what will be sent, plus any warnings
   (e.g. a card whose question is too long). Right-click a row to jump to
   its note in the Browser.
3. Pick a delivery method:

### Option A - Save as .csv (default, no setup needed)

This is the one to use until/unless you set up advanced mode below.

1. In the preview, click **Save as .csv...** and save the file somewhere
   you'll remember (e.g. Downloads).
2. Go to **kotobaweb.com -> Dashboard** (log in with Discord if needed).
3. Click **Create new** (top of your deck list) to open a fresh custom deck.
4. Fill in **Full deck name** and **Short deck name**.
5. Click **IMPORT FROM FILE** - this opens your computer's normal file
   picker (Kotoba's import is file-based; there is no "paste a CSV" box on
   the page, despite what you might expect). Pick the file you saved in
   step 1.
6. The grid fills in with your cards. Click **SAVE TO BOT** to actually
   create the deck.

### Option B - Upload directly to Kotoba (advanced mode, one click)

Requires the one-time setup in section 4 below. Once set up:

1. In the preview, click **Upload directly to Kotoba**.
2. That's it - no browser step. You'll see a confirmation, and the run is
   logged in History.

## 4. Setting up advanced mode (optional, for one-click upload)

Kotoba has no API key - the add-on authenticates the same way your browser
does, with your session cookie. Treat it like a password: anyone who has it
can act as your Kotoba account.

1. **Tools -> Kotoba Export... -> Advanced settings...**
2. Check **Enable advanced mode (direct upload to Kotoba)**.
3. Grab your cookie: open kotobaweb.com in your browser while logged in,
   open DevTools -> **Network**, click any request to kotobaweb.com, open
   its **Headers** tab, and copy the full value next to `Cookie:` under
   Request Headers - a string with an `=` in it, like `connect.sid=...`.
   (Don't copy from a separate "Cookies" table that just shows a bare
   value with no name - the Headers tab is the reliable source.)
4. Paste it into **Session cookie**.
5. Click **Test connection** to confirm it's valid - you should see your
   Kotoba username.
6. Click **Save**.

From here, every preset's preview screen gets a working **Upload directly
to Kotoba** button.

### Overwriting the same deck on repeat runs

By default, every run creates a brand-new Kotoba deck (dated, if your
preset's deck name template includes `{date}`). If you'd rather keep
re-using one deck (e.g. a rolling "forgotten today" deck):

1. Edit the preset, set **Repeated runs** to **Overwrite same deck**
   (only selectable once advanced mode is on).
2. Make sure the **Deck name template** does *not* include `{date}` if you
   want it to stay the same deck every time - overwriting matches by the
   exact rendered deck name.
3. Run it via **Upload directly to Kotoba**. The next run with that same
   name updates (PATCHes) the same deck instead of creating a new one.

## 5. Automatic export (unattended, no clicking)

Runs a preset straight to Kotoba on its own, via direct-API upload -
useful for something like "forgotten today" updating itself every time you
sync.

1. Requires advanced mode (section 4) to already be set up.
2. In **Advanced settings...**, check **Enable automatic export** (a
   global switch, off by default).
3. Edit the preset you want automated, and under **Automatic export on**
   check any combination of **Anki startup**, **Anki shutdown**, or
   **AnkiWeb sync finishes**. "Forgotten today"-style presets belong on
   shutdown or sync, not startup - startup fires before you've reviewed
   anything that day.
4. Both the global switch *and* at least one of the preset's own boxes
   need to be on for anything to actually run.

A sync-triggered run that finds the exact same cards as last time is
skipped automatically (logged as "skipped" in History) rather than
re-uploading identical content - so syncing often doesn't spam Kotoba.

Anything unexpected (network failure, no cards due, misconfiguration) is
logged to History rather than interrupting Anki.

## 6. Managing presets

- **Duplicate...** clones the selected preset (new name, same filters and
  field mappings) - handy for variants like "leeches - N3" from
  "leeches - N4". The clone starts with no Kotoba deck link of its own.
- **Export presets... / Import presets...** back up your presets to a
  JSON file, or move them to another machine. This covers presets only -
  not your advanced-mode session cookie. Re-importing a file updates
  existing presets by id rather than duplicating them. Automatic-export
  triggers and deck-overwrite links are never carried over by import (an
  imported file is untrusted input) - re-enable and re-run an imported
  preset once if you rely on either.

## 7. History

**Tools -> Kotoba Export... -> History...** shows every past run - preset,
deck, card count, outcome, trigger, and how long it took. **Export to
CSV...** saves the whole log to a file if you want to look at it in a
spreadsheet.

## 8. Managing decks on Kotoba's side

**Advanced settings... -> Manage decks...** (requires a working session
cookie) lists decks you own on Kotoba and lets you delete ones you no
longer need - useful for tidying up decks left over from "new deck every
run" presets, since those aren't tracked locally.

## Troubleshooting

- **"Enable advanced mode and paste a session cookie..." tooltip on
  Upload button** - you haven't completed section 4 yet.
- **A preset's "Overwrite same deck" option is grayed out** - it requires
  advanced mode to be enabled first (see section 4).
- **Kotoba rejects your cookie (401)** - it's expired; grab a fresh one
  (step 3 in section 4).
- **A card's question/comment looks truncated or flagged in the
  preview's Warnings list** - Kotoba has hard length limits (e.g. 400
  chars for a text question, 20 for an image question, 600 for a comment);
  the warning tells you which card and limit.
