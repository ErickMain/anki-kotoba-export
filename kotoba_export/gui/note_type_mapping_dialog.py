"""Configures one note type's field mapping (Expression/Reading/Meaning)
within a preset. A preset can hold several of these - one per note type it
should pull from - since different note types (e.g. different mining
setups) rarely share field names.
"""
from aqt import mw
from aqt.qt import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout
from aqt.utils import showWarning


class NoteTypeMappingDialog(QDialog):
    def __init__(
        self,
        parent,
        note_type: str = "",
        expression_field: str = "",
        reading_field: str = "",
        meaning_field: str = "",
        exclude_note_types: set = None,
    ):
        super().__init__(parent)
        # Note types already mapped elsewhere in this preset - picking one
        # of these would silently overwrite that other entry, so it's
        # blocked at save time instead (editing an entry excludes itself).
        self.exclude_note_types = exclude_note_types or set()
        self.setWindowTitle("Note Type Field Mapping")
        self.resize(380, 180)
        self._build_ui()
        self._load(note_type, expression_field, reading_field, meaning_field)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

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

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
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

    def _load(self, note_type, expression_field, reading_field, meaning_field):
        if note_type:
            idx = self.note_type_combo.findText(note_type)
            if idx >= 0:
                self.note_type_combo.setCurrentIndex(idx)
        self._refresh_field_combos()

        for combo, value in (
            (self.expression_field_combo, expression_field),
            (self.reading_field_combo, reading_field),
            (self.meaning_field_combo, meaning_field),
        ):
            idx = combo.findText(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _on_accept(self):
        note_type = self.note_type_combo.currentText()
        if not note_type:
            showWarning("Pick a note type.", parent=self)
            return
        if note_type in self.exclude_note_types:
            showWarning(
                f'"{note_type}" is already mapped in this preset - edit that entry instead of adding a new one.',
                parent=self,
            )
            return
        if not self.expression_field_combo.currentText() and not self.reading_field_combo.currentText():
            showWarning("Pick at least an expression or reading field.", parent=self)
            return

        self.result_note_type = note_type
        self.result_expression_field = self.expression_field_combo.currentText()
        self.result_reading_field = self.reading_field_combo.currentText()
        self.result_meaning_field = self.meaning_field_combo.currentText()
        self.accept()
