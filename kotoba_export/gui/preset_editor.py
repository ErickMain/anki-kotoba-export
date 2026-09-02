"""Create/edit a preset: what to search for, which note type and fields it
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
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    Qt,
    QSpinBox,
    QVBoxLayout,
)
from aqt.utils import showWarning

from ..kotoba import format as kotoba_format
from ..kotoba.presets import REUSE_NEW_EACH_TIME, REUSE_OVERWRITE, Preset

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


class PresetEditorDialog(QDialog):
    def __init__(self, parent, preset: Preset, advanced_enabled: bool):
        super().__init__(parent)
        self.preset = preset
        self.advanced_enabled = advanced_enabled
        self.setWindowTitle("Kotoba Export Preset")
        self.resize(480, 640)
        self._build_ui()
        self._load_preset()

    # -- UI construction -----------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.name_edit = QLineEdit()
        form.addRow("Preset name:", self.name_edit)

        self.note_type_combo = QComboBox()
        for nt in mw.col.models.all_names_and_ids():
            self.note_type_combo.addItem(nt.name, nt.id)
        self.note_type_combo.currentIndexChanged.connect(self._refresh_field_combos)
        form.addRow("Note type:", self.note_type_combo)

        self.expression_field_combo = QComboBox()
        form.addRow("Expression / word field:", self.expression_field_combo)
        self.reading_field_combo = QComboBox()
        form.addRow("Reading (kana) field:", self.reading_field_combo)
        self.meaning_field_combo = QComboBox()
        form.addRow("Meaning field:", self.meaning_field_combo)

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

        self.deck_combo = QComboBox()
        self.deck_combo.addItem("(any deck)", "")
        for deck in sorted(mw.col.decks.all_names_and_ids(), key=lambda d: d.name.lower()):
            self.deck_combo.addItem(deck.name, deck.name)
        form.addRow("Deck (optional, includes subdecks):", self.deck_combo)

        self.raw_query_edit = QLineEdit()
        self.raw_query_edit.setPlaceholderText("e.g. deck:Japanese::Vocab -is:new")
        form.addRow("Advanced Anki search (optional):", self.raw_query_edit)

        form.addRow(QLabel("<b>Kotoba deck ('Type the reading!' style)</b>"))

        self.question_source_combo = QComboBox()
        form.addRow("Question column shows:", self.question_source_combo)
        self.answer_source_combo = QComboBox()
        form.addRow("Answer column shows:", self.answer_source_combo)
        self.comment_source_combo = QComboBox()
        form.addRow("Comment column shows:", self.comment_source_combo)

        self.comment_max_length_spin = QSpinBox()
        self.comment_max_length_spin.setRange(50, kotoba_format.COMMENT_MAX_LENGTH)
        self.comment_max_length_spin.setSuffix(" chars")
        self.comment_max_length_spin.setToolTip(
            "Mined notes often stuff several dictionaries' worth of glosses into one "
            f"field - this trims it, since Kotoba rejects comments over "
            f"{kotoba_format.COMMENT_MAX_LENGTH} chars anyway."
        )
        form.addRow("Comment max length:", self.comment_max_length_spin)

        self.strip_furigana_check = QCheckBox("Strip Anki furigana brackets, e.g. 漢字[かんじ]")
        self.strip_furigana_check.setChecked(True)
        layout.addWidget(self.strip_furigana_check)

        self.render_as_combo = QComboBox()
        self.render_as_combo.addItem("Image (hides the text from copy/paste - recommended)", "IMAGE")
        self.render_as_combo.addItem("Plain text", "TEXT")
        form.addRow("Question shown as:", self.render_as_combo)

        self.instructions_edit = QLineEdit()
        form.addRow("Instructions shown in Kotoba:", self.instructions_edit)

        self.deck_name_template_edit = QLineEdit()
        self.deck_name_template_edit.setToolTip(
            "In Overwrite mode, running with the same rendered name re-uses (PATCHes) that "
            "same Kotoba deck; a different name creates a separate one. Include {date} for a "
            "fresh deck every day (rarely what you want with Overwrite); drop it for one deck "
            "that keeps getting replaced. You can always type a one-off name in the export "
            "preview to save a snapshot without touching the usual deck."
        )
        form.addRow("Deck name template:", self.deck_name_template_edit)

        self.deck_description_edit = QLineEdit()
        form.addRow("Deck description (optional):", self.deck_description_edit)

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
        form.addRow("Repeated runs:", self.reuse_mode_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_field_combos(self):
        model_id = self.note_type_combo.currentData()
        field_names = []
        if model_id is not None:
            model = mw.col.models.get(model_id)
            if model:
                field_names = mw.col.models.field_names(model)
        for combo in (self.expression_field_combo, self.reading_field_combo, self.meaning_field_combo):
            current = combo.currentText()
            combo.clear()
            combo.addItems(field_names)
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    # -- load / save -----------------------------------------------------
    def _load_preset(self):
        p = self.preset
        self.name_edit.setText(p.name)

        if p.note_type:
            idx = self.note_type_combo.findText(p.note_type)
            if idx >= 0:
                self.note_type_combo.setCurrentIndex(idx)
        self._refresh_field_combos()

        for combo, value in (
            (self.expression_field_combo, p.expression_field),
            (self.reading_field_combo, p.reading_field),
            (self.meaning_field_combo, p.meaning_field),
        ):
            idx = combo.findText(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)

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

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            showWarning("Give this preset a name.", parent=self)
            return
        if not self.expression_field_combo.currentText() and not self.reading_field_combo.currentText():
            showWarning("Pick at least an expression or reading field.", parent=self)
            return

        p = self.preset
        p.name = name
        p.note_type = self.note_type_combo.currentText()
        p.expression_field = self.expression_field_combo.currentText()
        p.reading_field = self.reading_field_combo.currentText()
        p.meaning_field = self.meaning_field_combo.currentText()

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

        self.accept()
