"""Top-level dialog: manage presets (new/edit/delete/run) and jump to
advanced settings. Also handles the ad-hoc "export this selection" path
invoked from the Anki Browser.
"""
from aqt import mw
from aqt.qt import QDialog, QDialogButtonBox, QHBoxLayout, QListWidget, QMessageBox, QPushButton, QVBoxLayout
from aqt.utils import showInfo, showWarning

from .. import config_store
from ..kotoba import export as export_mod
from ..kotoba.presets import Preset, delete_preset, load_presets, upsert_preset
from .preset_editor import PresetEditorDialog
from .preview_dialog import PreviewDialog
from .settings_dialog import SettingsDialog


class MainDialog(QDialog):
    def __init__(self, parent=None, ad_hoc_note_ids=None):
        super().__init__(parent or mw)
        self.config = config_store.get_config()
        self.ad_hoc_note_ids = ad_hoc_note_ids
        self.setWindowTitle("Kotoba Export")
        self.resize(420, 380)
        self._build_ui()
        self._reload_list()

        if ad_hoc_note_ids:
            self._run_ad_hoc()

    # -- UI ---------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.preset_list = QListWidget()
        self.preset_list.itemDoubleClicked.connect(self._edit_selected)
        layout.addWidget(self.preset_list)

        btn_row = QHBoxLayout()
        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self._run_selected)
        btn_row.addWidget(run_btn)

        new_btn = QPushButton("New...")
        new_btn.clicked.connect(self._new_preset)
        btn_row.addWidget(new_btn)

        edit_btn = QPushButton("Edit...")
        edit_btn.clicked.connect(self._edit_selected)
        btn_row.addWidget(edit_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(delete_btn)
        layout.addLayout(btn_row)

        settings_btn = QPushButton("Advanced settings...")
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)

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
        preset = self._selected_preset()
        if not preset:
            showWarning("Select a preset first.", parent=self)
            return
        self._run_preset(preset, persist_updates=True)

    def _open_settings(self):
        dlg = SettingsDialog(self, self.config)
        if dlg.exec():
            config_store.save_config(self.config)

    def _run_preset(self, preset, persist_updates: bool):
        if not export_mod.build_query_for_preset(preset).strip():
            if (
                QMessageBox.question(
                    self,
                    "No filters set",
                    "This preset has no search filters (no state/tag/advanced query), so it "
                    "matches your entire collection. Continue anyway?",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return

        result = export_mod.build_cards_for_preset(mw.col, preset)
        if not result.cards:
            showInfo("No matching cards found for this preset.", parent=self)
            return

        def on_preset_updated(updated_preset):
            if not persist_updates:
                return
            self.config = upsert_preset(self.config, updated_preset)
            config_store.save_config(self.config)

        dlg = PreviewDialog(self, result, preset, self.config, on_preset_updated=on_preset_updated)
        dlg.exec()

    # -- ad-hoc (invoked from the Browser) -----------------------------------
    def _run_ad_hoc(self):
        note = mw.col.get_note(self.ad_hoc_note_ids[0])
        note_type_name = note.note_type()["name"] if note.note_type() else ""

        preset = Preset.new(f"Selected notes ({len(self.ad_hoc_note_ids)})")
        preset.note_type = note_type_name
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
