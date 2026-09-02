"""Create/edit a preset: what to search for, which note types and fields it
comes from, how those map onto Kotoba's Question/Answers/Comment, and how
the resulting deck should be named and reused.
"""
from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    Qt,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import showWarning

from ..kotoba import format as kotoba_format
from ..kotoba.presets import (
    AUTO_RUN_BOTH,
    AUTO_RUN_OFF,
    AUTO_RUN_SHUTDOWN,
    AUTO_RUN_STARTUP,
    REUSE_NEW_EACH_TIME,
    REUSE_OVERWRITE,
    Preset,
)
from .note_type_mapping_dialog import NoteTypeMappingDialog

_SOURCE_OPTIONS = [
    ("Expression / word", "expression"),
    ("Reading (kana)", "reading"),
    ("Meaning", "meaning"),
]
_COMMENT_SOURCE_OPTIONS = _SOURCE_OPTIONS + [("(leave blank)", "none")]


def _fill_combo(combo: QComboBox, options, current_value: str):
    combo.clear()
    for label, value in options:
        combo.addItem(label, value)
    idx = combo.findData(current_value)
    combo.setCurrentIndex(idx if idx >= 0 else 0)


def _mapping_label(note_type: str, mapping: dict) -> str:
    parts = [mapping.get("expression_field", ""), mapping.get("reading_field", ""), mapping.get("meaning_field", "")]
    return f"{note_type}  ->  " + " / ".join(p or "(none)" for p in parts)


class PresetEditorDialog(QDialog):
    def __init__(self, parent, preset: Preset, advanced_enabled: bool):
        super().__init__(parent)
        self.preset = preset
        self.advanced_enabled = advanced_enabled
        self._note_type_mappings = {}  # working copy, written back to the preset on Save
        self.setWindowTitle("Kotoba Export Preset")
        self.resize(520, 620)
        self._build_ui()
        self._load_preset()

    # -- UI construction -----------------------------------------------
    def _build_ui(self):
        # This dialog has grown a lot of fields over time - a plain fixed
        # layout stopped fitting on smaller/laptop screens, cutting off the
        # Save button. Everything except Save/Cancel scrolls; those two stay
        # pinned at the bottom so they're always reachable.
        outer = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        layout = QVBoxLayout(content)

        name_form = QFormLayout()
        layout.addLayout(name_form)
        self.name_edit = QLineEdit()
        name_form.addRow("Preset name:", self.name_edit)

        layout.addWidget(
            QLabel(
                "Note types this preset pulls from - each needs its own Expression/Reading/"
                "Meaning field mapping, since field names rarely match across note types:"
            )
        )
        self.note_type_list = QListWidget()
        self.note_type_list.setMaximumHeight(90)
        self.note_type_list.itemDoubleClicked.connect(self._edit_note_type_mapping)
        layout.addWidget(self.note_type_list)

        nt_btn_row = QHBoxLayout()
        add_nt_btn = QPushButton("Add note type...")
        add_nt_btn.clicked.connect(self._add_note_type_mapping)
        nt_btn_row.addWidget(add_nt_btn)
        edit_nt_btn = QPushButton("Edit...")
        edit_nt_btn.clicked.connect(self._edit_note_type_mapping)
        nt_btn_row.addWidget(edit_nt_btn)
        remove_nt_btn = QPushButton("Remove")
        remove_nt_btn.clicked.connect(self._remove_note_type_mapping)
        nt_btn_row.addWidget(remove_nt_btn)
        layout.addLayout(nt_btn_row)

        layout.addWidget(QLabel("Which cards to include (all checked filters apply together):"))
        self.forgotten_today_check = QCheckBox("Forgotten today (pressed Again today)")
        self.leech_check = QCheckBox("Leeches")
        self.suspended_check = QCheckBox("Suspended")
        self.due_check = QCheckBox("Due")
        for cb in (self.forgotten_today_check, self.leech_check, self.suspended_check, self.due_check):
            layout.addWidget(cb)

        layout.addWidget(QLabel("Tags (optional, check any to require):"))
        self.tags_list = QListWidget()
        self.tags_list.setMaximumHeight(110)
        for tag in sorted(mw.col.tags.all()):
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.tags_list.addItem(item)
        layout.addWidget(self.tags_list)

        query_form = QFormLayout()
        layout.addLayout(query_form)

        self.deck_combo = QComboBox()
        self.deck_combo.addItem("(any deck)", "")
        for deck in sorted(mw.col.decks.all_names_and_ids(), key=lambda d: d.name.lower()):
            self.deck_combo.addItem(deck.name, deck.name)
        query_form.addRow("Deck (optional, includes subdecks):", self.deck_combo)

        self.raw_query_edit = QLineEdit()
        self.raw_query_edit.setPlaceholderText("e.g. deck:Japanese::Vocab -is:new")
        query_form.addRow("Advanced Anki search (optional):", self.raw_query_edit)

        kotoba_form = QFormLayout()
        layout.addLayout(kotoba_form)

        kotoba_form.addRow(QLabel("<b>Kotoba deck ('Type the reading!' style)</b>"))

        self.question_source_combo = QComboBox()
        kotoba_form.addRow("Question column shows:", self.question_source_combo)
        self.answer_source_combo = QComboBox()
        kotoba_form.addRow("Answer column shows:", self.answer_source_combo)
        self.comment_source_combo = QComboBox()
        kotoba_form.addRow("Comment column shows:", self.comment_source_combo)

        self.comment_max_length_spin = QSpinBox()
        self.comment_max_length_spin.setRange(50, kotoba_format.COMMENT_MAX_LENGTH)
        self.comment_max_length_spin.setSuffix(" chars")
        self.comment_max_length_spin.setToolTip(
            "Mined notes often stuff several dictionaries' worth of glosses into one "
            f"field - this trims it, since Kotoba rejects comments over "
            f"{kotoba_format.COMMENT_MAX_LENGTH} chars anyway."
        )
        kotoba_form.addRow("Comment max length:", self.comment_max_length_spin)

        self.strip_furigana_check = QCheckBox("Strip Anki furigana brackets, e.g. 漢字[かんじ]")
        self.strip_furigana_check.setChecked(True)
        kotoba_form.addRow(self.strip_furigana_check)

        self.render_as_combo = QComboBox()
        self.render_as_combo.addItem("Image (hides the text from copy/paste - recommended)", "IMAGE")
        self.render_as_combo.addItem("Plain text", "TEXT")
        kotoba_form.addRow("Question shown as:", self.render_as_combo)

        self.instructions_edit = QLineEdit()
        kotoba_form.addRow("Instructions shown in Kotoba:", self.instructions_edit)

        self.deck_name_template_edit = QLineEdit()
        self.deck_name_template_edit.setToolTip(
            "In Overwrite mode, running with the same rendered name re-uses (PATCHes) that "
            "same Kotoba deck; a different name creates a separate one. Include {date} for a "
            "fresh deck every day (rarely what you want with Overwrite); drop it for one deck "
            "that keeps getting replaced. You can always type a one-off name in the export "
            "preview to save a snapshot without touching the usual deck."
        )
        kotoba_form.addRow("Deck name template:", self.deck_name_template_edit)

        self.deck_description_edit = QLineEdit()
        kotoba_form.addRow("Deck description (optional):", self.deck_description_edit)

        self.reuse_mode_combo = QComboBox()
        self.reuse_mode_combo.addItem("New deck every run", REUSE_NEW_EACH_TIME)
        overwrite_label = "Overwrite same deck (requires advanced/direct-API mode)"
        self.reuse_mode_combo.addItem(overwrite_label, REUSE_OVERWRITE)
        self.reuse_mode_combo.setToolTip(
            "Overwrite links to a Kotoba deck by its exact rendered name - see the Deck name "
            "template tooltip. New deck every run always creates a fresh deck, so it's safe "
            "for names that include {date} (Kotoba caps accounts at 100 decks, so this isn't "
            "a great fit for a preset you run daily forever)."
        )
        if not self.advanced_enabled:
            self.reuse_mode_combo.model().item(1).setEnabled(False)
        kotoba_form.addRow("Repeated runs:", self.reuse_mode_combo)

        self.auto_run_combo = QComboBox()
        self.auto_run_combo.addItem("Off - run manually only", AUTO_RUN_OFF)
        self.auto_run_combo.addItem("On Anki startup", AUTO_RUN_STARTUP)
        self.auto_run_combo.addItem("On Anki shutdown (may briefly delay closing)", AUTO_RUN_SHUTDOWN)
        self.auto_run_combo.addItem("Both startup and shutdown", AUTO_RUN_BOTH)
        self.auto_run_combo.setToolTip(
            "Uploads this preset to Kotoba unattended, with no preview - only sensible for "
            "advanced/direct-API mode, since there's no one there to click Copy/Upload. Also "
            "needs \"Enable automatic export\" turned on in Advanced settings; this dropdown "
            "alone does not start anything. \"Forgotten today\"-style presets belong on "
            "shutdown, not startup - startup runs before you've reviewed anything that day."
        )
        if not self.advanced_enabled:
            for i in range(1, self.auto_run_combo.count()):
                self.auto_run_combo.model().item(i).setEnabled(False)
        kotoba_form.addRow("Automatic export:", self.auto_run_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)  # outside the scroll area - always visible, regardless of scroll position

    # -- note type mapping list ------------------------------------------
    def _refresh_note_type_list(self):
        self.note_type_list.clear()
        for note_type, mapping in self._note_type_mappings.items():
            self.note_type_list.addItem(_mapping_label(note_type, mapping))

    def _selected_note_type(self):
        row = self.note_type_list.currentRow()
        keys = list(self._note_type_mappings.keys())
        if row < 0 or row >= len(keys):
            return None
        return keys[row]

    def _add_note_type_mapping(self):
        dlg = NoteTypeMappingDialog(self, exclude_note_types=set(self._note_type_mappings.keys()))
        if dlg.exec():
            self._note_type_mappings[dlg.result_note_type] = {
                "expression_field": dlg.result_expression_field,
                "reading_field": dlg.result_reading_field,
                "meaning_field": dlg.result_meaning_field,
            }
            self._refresh_note_type_list()

    def _edit_note_type_mapping(self):
        note_type = self._selected_note_type()
        if not note_type:
            showWarning("Select a note type mapping first.", parent=self)
            return
        mapping = self._note_type_mappings[note_type]
        dlg = NoteTypeMappingDialog(
            self,
            note_type=note_type,
            expression_field=mapping.get("expression_field", ""),
            reading_field=mapping.get("reading_field", ""),
            meaning_field=mapping.get("meaning_field", ""),
            exclude_note_types=set(self._note_type_mappings.keys()) - {note_type},
        )
        if dlg.exec():
            if dlg.result_note_type != note_type:
                del self._note_type_mappings[note_type]
            self._note_type_mappings[dlg.result_note_type] = {
                "expression_field": dlg.result_expression_field,
                "reading_field": dlg.result_reading_field,
                "meaning_field": dlg.result_meaning_field,
            }
            self._refresh_note_type_list()

    def _remove_note_type_mapping(self):
        note_type = self._selected_note_type()
        if not note_type:
            showWarning("Select a note type mapping first.", parent=self)
            return
        del self._note_type_mappings[note_type]
        self._refresh_note_type_list()

    # -- load / save -----------------------------------------------------
    def _load_preset(self):
        p = self.preset
        self.name_edit.setText(p.name)

        self._note_type_mappings = {k: dict(v) for k, v in p.note_type_mappings.items()}
        self._refresh_note_type_list()

        self.forgotten_today_check.setChecked(p.forgotten_today)
        self.leech_check.setChecked(p.leech)
        self.suspended_check.setChecked(p.suspended)
        self.due_check.setChecked(p.due)

        for i in range(self.tags_list.count()):
            item = self.tags_list.item(i)
            if item.text() in p.tags:
                item.setCheckState(Qt.CheckState.Checked)

        deck_idx = self.deck_combo.findData(p.deck)
        self.deck_combo.setCurrentIndex(deck_idx if deck_idx >= 0 else 0)

        self.raw_query_edit.setText(p.raw_query)

        _fill_combo(self.question_source_combo, _SOURCE_OPTIONS, p.question_source)
        _fill_combo(self.answer_source_combo, _SOURCE_OPTIONS, p.answer_source)
        _fill_combo(self.comment_source_combo, _COMMENT_SOURCE_OPTIONS, p.comment_source)
        self.comment_max_length_spin.setValue(
            min(max(p.comment_max_length, self.comment_max_length_spin.minimum()), kotoba_format.COMMENT_MAX_LENGTH)
        )

        self.strip_furigana_check.setChecked(p.strip_furigana_brackets)
        idx = self.render_as_combo.findData(p.render_as)
        self.render_as_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.instructions_edit.setText(p.instructions)
        self.deck_name_template_edit.setText(p.deck_name_template)
        self.deck_description_edit.setText(p.deck_description)

        idx = self.reuse_mode_combo.findData(p.deck_reuse_mode)
        if idx >= 0 and (p.deck_reuse_mode != REUSE_OVERWRITE or self.advanced_enabled):
            self.reuse_mode_combo.setCurrentIndex(idx)

        idx = self.auto_run_combo.findData(p.auto_run)
        if idx >= 0 and (p.auto_run == AUTO_RUN_OFF or self.advanced_enabled):
            self.auto_run_combo.setCurrentIndex(idx)

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            showWarning("Give this preset a name.", parent=self)
            return
        if not self._note_type_mappings:
            showWarning("Add at least one note type mapping.", parent=self)
            return

        p = self.preset
        p.name = name
        p.note_type_mappings = {k: dict(v) for k, v in self._note_type_mappings.items()}

        p.forgotten_today = self.forgotten_today_check.isChecked()
        p.leech = self.leech_check.isChecked()
        p.suspended = self.suspended_check.isChecked()
        p.due = self.due_check.isChecked()
        p.tags = [
            self.tags_list.item(i).text()
            for i in range(self.tags_list.count())
            if self.tags_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        p.deck = self.deck_combo.currentData()
        p.raw_query = self.raw_query_edit.text().strip()

        p.question_source = self.question_source_combo.currentData()
        p.answer_source = self.answer_source_combo.currentData()
        p.comment_source = self.comment_source_combo.currentData()
        p.comment_max_length = self.comment_max_length_spin.value()
        p.strip_furigana_brackets = self.strip_furigana_check.isChecked()
        p.render_as = self.render_as_combo.currentData()
        p.instructions = self.instructions_edit.text().strip() or "Type the reading!"
        p.deck_name_template = self.deck_name_template_edit.text().strip() or "{preset_name} - {date}"
        p.deck_description = self.deck_description_edit.text().strip()
        p.deck_reuse_mode = self.reuse_mode_combo.currentData()
        p.auto_run = self.auto_run_combo.currentData()

        self.accept()
