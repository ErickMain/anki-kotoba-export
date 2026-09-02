"""Shows the export history log - what got exported, when, and how it went,
including automatic (unattended) runs the user might not have been
watching for.
"""
from aqt.qt import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .. import config_store
from ..kotoba import history

_COLUMNS = ["When", "Preset", "Deck", "Cards", "Outcome", "Trigger"]


class HistoryDialog(QDialog):
    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Kotoba Export History")
        self.resize(720, 420)
        self._build_ui()
        self._reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        clear_btn = QPushButton("Clear history")
        clear_btn.clicked.connect(self._clear_history)
        layout.addWidget(clear_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _reload(self):
        entries = list(reversed(history.load_history(self.config)))  # newest first
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            outcome = entry.outcome
            if entry.detail:
                outcome += f" - {entry.detail}"
            values = [
                entry.timestamp,
                entry.preset_name,
                entry.deck_name,
                str(entry.card_count),
                outcome,
                entry.triggered_by,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _clear_history(self):
        if not history.load_history(self.config):
            return
        if (
            QMessageBox.question(self, "Clear history", "Delete all export history? This cannot be undone.")
            != QMessageBox.StandardButton.Yes
        ):
            return
        history.clear_history(self.config)
        config_store.save_config(self.config)
        self._reload()
