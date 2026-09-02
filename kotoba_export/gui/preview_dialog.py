"""Shows the cards an export is about to send, and offers the two delivery
paths: clipboard+browser (always available) or direct API upload (only when
advanced mode is configured with a session cookie).
"""
import time

from aqt import dialogs, mw
from aqt.qt import (
    QAbstractItemView,
    QApplication,
    QCursor,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from aqt.utils import openLink, showInfo, showWarning, tooltip

from .. import config_store
from ..kotoba import api as kotoba_api
from ..kotoba import format as kotoba_format
from ..kotoba import history
from ..kotoba import upload as upload_mod

KOTOBA_DASHBOARD_URL = "https://kotobaweb.com/dashboard"


class PreviewDialog(QDialog):
    def __init__(self, parent, result, preset, config: dict, on_preset_updated=None, triggered_by=history.TRIGGER_MANUAL):
        super().__init__(parent)
        self.result = result
        self.preset = preset
        self.config = config
        self.on_preset_updated = on_preset_updated
        self.triggered_by = triggered_by

        self.setWindowTitle(f"Kotoba Export - {preset.name}")
        self.resize(760, 520)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        summary_bits = [f"{len(self.result.cards)} card(s) will be exported"]
        if self.result.merged_duplicate_count:
            summary_bits.append(
                f"{self.result.merged_duplicate_count} merged (shared the same question with another card)"
            )
        if self.result.skipped_wrong_note_type:
            summary_bits.append(f"{self.result.skipped_wrong_note_type} skipped (different note type)")
        layout.addWidget(QLabel(" - ".join(summary_bits)))

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Kotoba deck name:"))
        self.deck_name_edit = QLineEdit(self.result.deck_name)
        name_row.addWidget(self.deck_name_edit)
        layout.addLayout(name_row)

        if self.result.warnings:
            warn_list = QListWidget()
            warn_list.addItems(self.result.warnings)
            warn_list.setMaximumHeight(90)
            layout.addWidget(QLabel("Warnings:"))
            layout.addWidget(warn_list)

        self.table = QTableWidget(len(self.result.cards), 3)
        self.table.setHorizontalHeaderLabels(["Question", "Answer(s)", "Comment"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_row_context_menu)
        self.table.setToolTip("Right-click a row to open its note(s) in the Anki Browser.")
        for row, card in enumerate(self.result.cards):
            self.table.setItem(row, 0, QTableWidgetItem(card.question))
            self.table.setItem(row, 1, QTableWidgetItem(card.answers_joined()))
            self.table.setItem(row, 2, QTableWidgetItem(card.comment))
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy CSV + Open Kotoba")
        copy_btn.clicked.connect(self._copy_and_open)
        btn_row.addWidget(copy_btn)

        save_btn = QPushButton("Save as .csv...")
        save_btn.clicked.connect(self._save_csv)
        btn_row.addWidget(save_btn)

        self.upload_btn = QPushButton("Upload directly to Kotoba")
        self.upload_btn.clicked.connect(self._upload_direct)
        self.upload_btn.setEnabled(self._advanced_ready())
        if not self._advanced_ready():
            self.upload_btn.setToolTip(
                "Enable advanced mode and paste a session cookie in Kotoba Export Settings first."
            )
        btn_row.addWidget(self.upload_btn)
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _show_row_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self.result.cards):
            return
        note_ids = self.result.cards[row].source_note_ids
        if not note_ids:
            return

        menu = QMenu(self)
        label = "Open in Browser" if len(note_ids) == 1 else f"Open {len(note_ids)} notes in Browser"
        action = menu.addAction(label)
        action.triggered.connect(lambda: self._open_notes_in_browser(note_ids))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _open_notes_in_browser(self, note_ids):
        browser = dialogs.open("Browser", mw)
        browser.search_for("nid:" + ",".join(str(nid) for nid in note_ids))

    def _advanced_ready(self) -> bool:
        adv = self.config.get("advanced", {})
        return bool(adv.get("direct_api_enabled") and adv.get("session_cookie", "").strip())

    def _csv_text(self) -> str:
        return kotoba_format.build_csv(self.result.cards)

    def _log_history(self, outcome: str, deck_name: str, detail: str = "", duration_seconds: float = 0.0):
        entry = history.new_entry(
            preset_name=self.preset.name,
            deck_name=deck_name,
            card_count=len(self.result.cards),
            outcome=outcome,
            triggered_by=self.triggered_by,
            detail=detail,
            duration_seconds=duration_seconds,
        )
        history.append_entry(self.config, entry)
        config_store.save_config(self.config)

    def _copy_and_open(self):
        start = time.perf_counter()
        QApplication.clipboard().setText(self._csv_text())
        openLink(KOTOBA_DASHBOARD_URL)
        elapsed = time.perf_counter() - start
        self._log_history(
            history.OUTCOME_COPIED, self.deck_name_edit.text().strip() or self.result.deck_name, duration_seconds=elapsed
        )
        showInfo(
            "CSV copied to your clipboard and kotobaweb.com opened in your browser.\n\n"
            f"In Kotoba: New Custom Deck -> name it \"{self.deck_name_edit.text()}\" -> "
            "Import -> paste.",
            parent=self,
        )

    def _save_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Kotoba CSV", f"{self.deck_name_edit.text() or 'kotoba_export'}.csv", "CSV (*.csv)"
        )
        if not path:
            return
        start = time.perf_counter()
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(self._csv_text())
        elapsed = time.perf_counter() - start
        self._log_history(
            history.OUTCOME_SAVED,
            self.deck_name_edit.text().strip() or self.result.deck_name,
            detail=path,
            duration_seconds=elapsed,
        )
        tooltip(f"Saved to {path}", parent=self)

    def _upload_direct(self):
        cookie = self.config.get("advanced", {}).get("session_cookie", "")
        deck_name = self.deck_name_edit.text().strip() or self.result.deck_name

        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        start = time.perf_counter()
        try:
            upload_mod.upload_deck(cookie, self.preset, self.result.cards, deck_name)
            # So a later automatic sync-triggered run correctly recognizes
            # this content as already up to date, even though this upload
            # was manual (see __init__.py's _run_auto_presets).
            self.preset.set_last_upload_hash(deck_name, kotoba_format.cards_fingerprint(self.result.cards))
        except kotoba_api.KotobaApiError as exc:
            elapsed = time.perf_counter() - start
            self._log_history(history.OUTCOME_ERROR, deck_name, detail=str(exc), duration_seconds=elapsed)
            showWarning(str(exc), parent=self)
            return
        finally:
            self.unsetCursor()
        elapsed = time.perf_counter() - start

        if self.on_preset_updated:
            self.on_preset_updated(self.preset)
        self._log_history(history.OUTCOME_UPLOADED, deck_name, duration_seconds=elapsed)

        showInfo(
            f"Uploaded to Kotoba as \"{deck_name}\".",
            parent=self,
        )
