"""Kotoba Export - fast export of Anki cards to kotobaweb.com "Type the
reading!" custom decks, with saved presets for recurring study sessions
(forgotten today, leeches, suspended, by tag, ...).
"""
from aqt import gui_hooks, mw
from aqt.qt import QAction
from aqt.utils import showInfo

from .gui.main_dialog import MainDialog


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


def _setup():
    tools_action = QAction("Kotoba Export...", mw)
    tools_action.triggered.connect(_open_main_dialog)
    mw.form.menuTools.addAction(tools_action)

    gui_hooks.browser_menus_did_init.append(_on_browser_menus_did_init)


_setup()
