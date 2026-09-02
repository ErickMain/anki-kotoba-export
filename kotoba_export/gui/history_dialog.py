"""Shows the export history log - what got exported, when, and how it went,
including automatic (unattended) runs the user might not have been
watching for.
"""
from aqt.qt import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from aqt.utils import showInfo, tooltip

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

        btn_row = QHBoxLayout()
        export_btn = QPushButton("Export to CSV...")
        export_btn.setToolTip("Save the full history log to a CSV file - e.g. to track it in a spreadsheet.")
        export_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(export_btn)

        clear_btn = QPushButton("Clear history")
        clear_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

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

    def _export_csv(self):
        entries = history.load_history(self.config)  # chronological (oldest first)
        if not entries:
            showInfo("No history to export yet.", parent=self)
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Kotoba Export History", "kotoba_export_history.csv", "CSV (*.csv)"
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(history.history_to_csv(entries))
        tooltip(f"Exported {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} to {path}", parent=self)

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
