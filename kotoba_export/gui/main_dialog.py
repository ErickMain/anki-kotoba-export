"""Top-level dialog: manage presets (new/edit/delete/run) and jump to
advanced settings. Also handles the ad-hoc "export this selection" path
invoked from the Anki Browser.
"""
from aqt import mw
from aqt.qt import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from aqt.utils import showInfo, showWarning, tooltip

from .. import config_store
from ..kotoba import export as export_mod
from ..kotoba import history
from ..kotoba.presets import (
    Preset,
    delete_preset,
    load_presets,
    presets_from_json,
    presets_to_json,
    upsert_preset,
)
from .history_dialog import HistoryDialog
from .preset_editor import PresetEditorDialog
from .preview_dialog import PreviewDialog
from .settings_dialog import SettingsDialog


class MainDialog(QDialog):
    def __init__(self, parent=None, ad_hoc_note_ids=None):
        super().__init__(parent or mw)
        self.config = config_store.get_config()
        self.ad_hoc_note_ids = ad_hoc_note_ids
        self.setWindowTitle("Kotoba Export")
        self.resize(420, 440)
        self._build_ui()
        self._reload_list()

        if ad_hoc_note_ids:
            self._run_ad_hoc()

    # -- UI ---------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.preset_list = QListWidget()
        self.preset_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.preset_list.itemDoubleClicked.connect(self._edit_selected)
        layout.addWidget(self.preset_list)

        btn_row = QHBoxLayout()
        run_btn = QPushButton("Run")
        run_btn.setToolTip(
            "Ctrl+click or Shift+click to select more than one preset - each runs in turn, "
            "with its own preview, so one click covers your whole daily routine."
        )
        run_btn.clicked.connect(self._run_selected)
        btn_row.addWidget(run_btn)

        new_btn = QPushButton("New...")
        new_btn.clicked.connect(self._new_preset)
        btn_row.addWidget(new_btn)

        edit_btn = QPushButton("Edit...")
        edit_btn.clicked.connect(self._edit_selected)
        btn_row.addWidget(edit_btn)

        duplicate_btn = QPushButton("Duplicate...")
        duplicate_btn.setToolTip("Clone this preset - same filters and field mappings, no shared Kotoba deck link.")
        duplicate_btn.clicked.connect(self._duplicate_selected)
        btn_row.addWidget(duplicate_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(delete_btn)
        layout.addLayout(btn_row)

        bottom_row = QHBoxLayout()
        settings_btn = QPushButton("Advanced settings...")
        settings_btn.clicked.connect(self._open_settings)
        bottom_row.addWidget(settings_btn)

        history_btn = QPushButton("History...")
        history_btn.setToolTip("See past export runs, including automatic ones you weren't watching for.")
        history_btn.clicked.connect(self._open_history)
        bottom_row.addWidget(history_btn)
        layout.addLayout(bottom_row)

        io_row = QHBoxLayout()
        export_btn = QPushButton("Export presets...")
        export_btn.setToolTip("Save all your presets to a JSON file - for backup, or to move them to another machine.")
        export_btn.clicked.connect(self._export_presets)
        io_row.addWidget(export_btn)

        import_btn = QPushButton("Import presets...")
        import_btn.setToolTip(
            "Load presets from a JSON file exported here. Existing presets with the same id are "
            "updated, not duplicated. Field/note-type names may need re-checking on a different collection."
        )
        import_btn.clicked.connect(self._import_presets)
        io_row.addWidget(import_btn)
        layout.addLayout(io_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _reload_list(self):
        self.preset_list.clear()
        for preset in load_presets(self.config):
            self.preset_list.addItem(preset.name)

    def _selected_preset(self):
        row = self.preset_list.currentRow()
        presets = load_presets(self.config)
        if row < 0 or row >= len(presets):
            return None
        return presets[row]

    def _selected_presets(self):
        """All presets the user has highlighted (ctrl/shift-click), in list
        order rather than click order - used by Run for batching."""
        presets = load_presets(self.config)
        rows = sorted({idx.row() for idx in self.preset_list.selectedIndexes()})
        return [presets[r] for r in rows if 0 <= r < len(presets)]

    def _advanced_enabled(self) -> bool:
        return bool(self.config.get("advanced", {}).get("direct_api_enabled"))

    # -- actions ------------------------------------------------------------
    def _new_preset(self):
        preset = Preset.new("New preset")
        dlg = PresetEditorDialog(self, preset, self._advanced_enabled())
        if dlg.exec():
            self.config = upsert_preset(self.config, preset)
            config_store.save_config(self.config)
            self._reload_list()

    def _edit_selected(self):
        preset = self._selected_preset()
        if not preset:
            showWarning("Select a preset first.", parent=self)
            return
        dlg = PresetEditorDialog(self, preset, self._advanced_enabled())
        if dlg.exec():
            self.config = upsert_preset(self.config, preset)
            config_store.save_config(self.config)
            self._reload_list()

    def _duplicate_selected(self):
        preset = self._selected_preset()
        if not preset:
            showWarning("Select a preset first.", parent=self)
            return
        clone = preset.duplicate()
        dlg = PresetEditorDialog(self, clone, self._advanced_enabled())
        if dlg.exec():
            self.config = upsert_preset(self.config, clone)
            config_store.save_config(self.config)
            self._reload_list()

    def _delete_selected(self):
        preset = self._selected_preset()
        if not preset:
            showWarning("Select a preset first.", parent=self)
            return
        if (
            QMessageBox.question(self, "Delete preset", f'Delete preset "{preset.name}"?')
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.config = delete_preset(self.config, preset.id)
        config_store.save_config(self.config)
        self._reload_list()

    def _run_selected(self):
        presets = self._selected_presets()
        if not presets:
            showWarning("Select a preset first.", parent=self)
            return
        for i, preset in enumerate(presets, start=1):
            suffix = f" ({i} of {len(presets)})" if len(presets) > 1 else ""
            self._run_preset(preset, persist_updates=True, title_suffix=suffix)

    def _open_settings(self):
        dlg = SettingsDialog(self, self.config)
        if dlg.exec():
            config_store.save_config(self.config)

    def _open_history(self):
        HistoryDialog(self, self.config).exec()

    def _export_presets(self):
        presets = load_presets(self.config)
        if not presets:
            showInfo("No presets to export yet.", parent=self)
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Kotoba Export Presets", "kotoba_export_presets.json", "JSON (*.json)"
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(presets_to_json(presets))
        tooltip(f"Exported {len(presets)} preset(s) to {path}", parent=self)

    def _import_presets(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Kotoba Export Presets", "", "JSON (*.json)")
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                imported = presets_from_json(f.read())
        except (OSError, ValueError) as exc:
            showWarning(f"Could not import presets:\n\n{exc}", parent=self)
            return

        if not imported:
            showInfo("That file has no presets in it.", parent=self)
            return

        existing_ids = {p.id for p in load_presets(self.config)}
        for preset in imported:
            self.config = upsert_preset(self.config, preset)
        config_store.save_config(self.config)
        self._reload_list()

        updated = sum(1 for p in imported if p.id in existing_ids)
        added = len(imported) - updated
        showInfo(
            f"Imported {len(imported)} preset(s): {added} new, {updated} updated.\n\n"
            "Double-check note type and field mappings on each - they won't resolve if this "
            "collection doesn't have the same note type/field names.",
            parent=self,
        )

    def _run_preset(self, preset, persist_updates: bool, title_suffix: str = "", triggered_by: str = history.TRIGGER_MANUAL):
        if not export_mod.build_query_for_preset(preset).strip():
            if (
                QMessageBox.question(
                    self,
                    "No filters set",
                    f'"{preset.name}" has no search filters (no state/tag/advanced query), so '
                    "it matches your entire collection. Continue anyway?",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return

        result = export_mod.build_cards_for_preset(mw.col, preset)
        if not result.cards:
            self.config = history.append_entry(
                self.config,
                history.new_entry(preset.name, result.deck_name, 0, history.OUTCOME_NO_CARDS, triggered_by),
            )
            config_store.save_config(self.config)
            showInfo(f'No matching cards found for "{preset.name}".', parent=self)
            return

        def on_preset_updated(updated_preset):
            if not persist_updates:
                return
            self.config = upsert_preset(self.config, updated_preset)
            config_store.save_config(self.config)

        dlg = PreviewDialog(
            self, result, preset, self.config, on_preset_updated=on_preset_updated, triggered_by=triggered_by
        )
        if title_suffix:
            dlg.setWindowTitle(dlg.windowTitle() + title_suffix)
        dlg.exec()

    # -- ad-hoc (invoked from the Browser) -----------------------------------
    def _run_ad_hoc(self):
        note = mw.col.get_note(self.ad_hoc_note_ids[0])
        note_type_name = note.note_type()["name"] if note.note_type() else ""

        preset = Preset.new(f"Selected notes ({len(self.ad_hoc_note_ids)})")
        if note_type_name:
            preset.set_field_mapping(note_type_name, "", "", "")
        preset.raw_query = "nid:" + ",".join(str(nid) for nid in self.ad_hoc_note_ids)

        dlg = PresetEditorDialog(self, preset, self._advanced_enabled())
        if not dlg.exec():
            self.reject()
            return

        self._run_preset(preset, persist_updates=False)

        if (
            QMessageBox.question(
                self,
                "Save preset",
                "Save this as a preset? It will re-export this exact set of notes each "
                "time you run it - edit its search afterwards if you'd rather it match "
                "by tag/state instead.",
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.config = upsert_preset(self.config, preset)
            config_store.save_config(self.config)
            self._reload_list()
