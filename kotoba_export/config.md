# Kotoba Export

Prefer editing settings through the add-on's own dialogs (**Tools -> Kotoba Export...** for presets, its **Advanced settings...** button for direct-API mode) rather than this raw JSON editor.

- `presets`: your saved export presets.
- `advanced.direct_api_enabled`: turns on direct upload to kotobaweb.com.
- `advanced.session_cookie`: your kotobaweb.com session cookie, only used in advanced mode. Treat it like a password.
- `advanced.auto_export_enabled`: master switch for unattended startup/shutdown export. A preset also needs its own "Automatic export" setting turned on (in the preset editor) - both must be on for anything to run automatically.
- `history`: a capped log of past export runs, viewable/clearable from the main dialog's **History...** button.
