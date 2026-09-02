"""Kotoba Export - fast export of Anki cards to kotobaweb.com "Type the
reading!" custom decks, with saved presets for recurring study sessions
(forgotten today, leeches, suspended, by tag, ...).
"""
import time

from aqt import gui_hooks, mw
from aqt.qt import QAction
from aqt.utils import showInfo, tooltip

from . import config_store
from .gui.main_dialog import MainDialog
from .kotoba import export as export_mod
from .kotoba import format as kotoba_format
from .kotoba import history
from .kotoba import upload as upload_mod
from .kotoba.presets import load_presets_safe, upsert_preset

# Tighter than api.MAX_RETRIES (the interactive default): retries add
# bounded but real delay, and this runs during Anki's own
# startup/shutdown/sync - one retry still recovers from a single rate-limit
# hit without multiplying the worst-case block much further.
AUTO_EXPORT_MAX_RETRIES = 1


def _open_main_dialog():
    MainDialog(mw).exec()


def _export_selected_from_browser(browser):
    note_ids = browser.selected_notes()
    if not note_ids:
        showInfo("Select one or more notes first.", parent=browser)
        return
    MainDialog(browser, ad_hoc_note_ids=list(note_ids)).exec()


def _on_browser_menus_did_init(browser):
    action = QAction("Export selected to Kotoba...", browser)
    action.triggered.connect(lambda: _export_selected_from_browser(browser))
    browser.form.menu_Notes.addAction(action)


def _run_auto_presets(trigger: str):
    """Unattended export for presets whose auto_run_triggers includes
    `trigger`. Runs on Anki startup/shutdown or right after an AnkiWeb sync
    finishes, so this must never show a dialog or raise - anything
    unexpected gets logged to history instead and the loop moves on, so one
    bad preset can't hang or crash Anki's own startup/shutdown/sync
    sequence.
    """
    run_start = time.perf_counter()
    config = config_store.get_config()
    adv = config.get("advanced", {})
    cookie = adv.get("session_cookie", "")
    ready = bool(adv.get("auto_export_enabled") and adv.get("direct_api_enabled") and cookie.strip())

    all_presets, load_error = load_presets_safe(config)
    if load_error:
        config = history.append_entry(
            config,
            history.new_entry(
                "",
                "",
                0,
                history.OUTCOME_ERROR,
                trigger,
                detail=f"Could not load presets (config may be corrupted): {load_error}",
            ),
        )
        config_store.save_config(config)
        return

    presets = [p for p in all_presets if p.matches_auto_trigger(trigger)]
    if not presets:
        return

    uploaded = 0
    for preset in presets:
        if not ready:
            config = history.append_entry(
                config,
                history.new_entry(
                    preset.name,
                    "",
                    0,
                    history.OUTCOME_SKIPPED,
                    trigger,
                    detail="Automatic export is off, or advanced mode/session cookie isn't configured.",
                ),
            )
            continue

        start = time.perf_counter()
        try:
            query = export_mod.build_query_for_preset(preset)
            if not query.strip():
                config = history.append_entry(
                    config,
                    history.new_entry(
                        preset.name,
                        "",
                        0,
                        history.OUTCOME_SKIPPED,
                        trigger,
                        detail="No search filters set - would match the whole collection, skipped for safety.",
                        duration_seconds=time.perf_counter() - start,
                    ),
                )
                continue

            result = export_mod.build_cards_for_preset(mw.col, preset)
            if not result.cards:
                config = history.append_entry(
                    config,
                    history.new_entry(
                        preset.name,
                        result.deck_name,
                        0,
                        history.OUTCOME_NO_CARDS,
                        trigger,
                        duration_seconds=time.perf_counter() - start,
                    ),
                )
                continue

            # A sync-triggered run fires on every completed AnkiWeb sync -
            # syncing several times in a row with nothing reviewed in
            # between would otherwise re-upload byte-identical content each
            # time, wasting time and pressuring Kotoba's own rate-limited
            # deck endpoints for no reason. Startup/shutdown/manual runs are
            # deliberate enough (at most a few times a day) that this check
            # isn't needed there.
            fingerprint = kotoba_format.cards_fingerprint(result.cards)
            if trigger == history.TRIGGER_AUTO_SYNC and preset.get_last_upload_hash(result.deck_name) == fingerprint:
                config = history.append_entry(
                    config,
                    history.new_entry(
                        preset.name,
                        result.deck_name,
                        len(result.cards),
                        history.OUTCOME_SKIPPED,
                        trigger,
                        detail="No changes since the last successful upload - skipped to avoid a redundant Kotoba API call.",
                        duration_seconds=time.perf_counter() - start,
                    ),
                )
                continue

            upload_mod.upload_deck(
                cookie, preset, result.cards, result.deck_name, max_retries=AUTO_EXPORT_MAX_RETRIES
            )
            preset.set_last_upload_hash(result.deck_name, fingerprint)
            config = upsert_preset(config, preset)  # persists the updated deck_links/last_upload_hashes
            # Uploaded successfully, but validate_cards may still have flagged
            # things Kotoba silently truncates/skips rather than rejects
            # outright (e.g. an oversized comment). The preview dialog shows
            # these for a manual run; there's no dialog here, so they'd
            # otherwise go unseen - fold a summary into the history detail
            # instead.
            detail = kotoba_format.summarize_warnings(result.warnings)
            config = history.append_entry(
                config,
                history.new_entry(
                    preset.name,
                    result.deck_name,
                    len(result.cards),
                    history.OUTCOME_UPLOADED,
                    trigger,
                    detail=detail,
                    duration_seconds=time.perf_counter() - start,
                ),
            )
            uploaded += 1
        except Exception as exc:  # noqa: BLE001 - see docstring
            config = history.append_entry(
                config,
                history.new_entry(
                    preset.name,
                    "",
                    0,
                    history.OUTCOME_ERROR,
                    trigger,
                    detail=str(exc),
                    duration_seconds=time.perf_counter() - start,
                ),
            )

    config_store.save_config(config)
    if uploaded:
        total_elapsed = time.perf_counter() - run_start
        tooltip(f"Kotoba Export: automatically uploaded {uploaded} deck(s) on {trigger} ({total_elapsed:.1f}s).")


def _setup():
    tools_action = QAction("Kotoba Export...", mw)
    tools_action.triggered.connect(_open_main_dialog)
    mw.form.menuTools.addAction(tools_action)

    gui_hooks.browser_menus_did_init.append(_on_browser_menus_did_init)
    gui_hooks.profile_did_open.append(lambda: _run_auto_presets(history.TRIGGER_AUTO_STARTUP))
    gui_hooks.profile_will_close.append(lambda: _run_auto_presets(history.TRIGGER_AUTO_SHUTDOWN))
    gui_hooks.sync_did_finish.append(lambda: _run_auto_presets(history.TRIGGER_AUTO_SYNC))


_setup()
