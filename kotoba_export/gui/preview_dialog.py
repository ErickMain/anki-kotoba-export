"""Shows the cards an export is about to send, and offers the two delivery
paths: clipboard+browser (always available) or direct API upload (only when
advanced mode is configured with a session cookie).
"""
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
    QPushButton,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from aqt.utils import openLink, showInfo, showWarning, tooltip

from ..kotoba import api as kotoba_api
from ..kotoba import format as kotoba_format

KOTOBA_DASHBOARD_URL = "https://kotobaweb.com/dashboard"


class PreviewDialog(QDialog):
    def __init__(self, parent, result, preset, config: dict, on_preset_updated=None):
        super().__init__(parent)
        self.result = result
        self.preset = preset
        self.config = config
        self.on_preset_updated = on_preset_updated

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

        table = QTableWidget(len(self.result.cards), 3)
        table.setHorizontalHeaderLabels(["Question", "Answer(s)", "Comment"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, card in enumerate(self.result.cards):
            table.setItem(row, 0, QTableWidgetItem(card.question))
            table.setItem(row, 1, QTableWidgetItem(card.answers_joined()))
            table.setItem(row, 2, QTableWidgetItem(card.comment))
        layout.addWidget(table)

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

    def _advanced_ready(self) -> bool:
        adv = self.config.get("advanced", {})
        return bool(adv.get("direct_api_enabled") and adv.get("session_cookie", "").strip())

    def _csv_text(self) -> str:
        return kotoba_format.build_csv(self.result.cards)

    def _copy_and_open(self):
        QApplication.clipboard().setText(self._csv_text())
        openLink(KOTOBA_DASHBOARD_URL)
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
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(self._csv_text())
        tooltip(f"Saved to {path}", parent=self)

    def _upload_direct(self):
        cookie = self.config.get("advanced", {}).get("session_cookie", "")
        deck_name = self.deck_name_edit.text().strip() or self.result.deck_name
        short_name = kotoba_format.make_short_name(deck_name)
        overwrite = self.preset.deck_reuse_mode == "overwrite"
        # Linked by the exact rendered name: reusing the same name overwrites
        # that deck; typing a different name here creates a separate one.
        link = self.preset.get_deck_link(deck_name) if overwrite else None

        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            if link:
                try:
                    resp = kotoba_api.update_deck(
                        cookie,
                        link["id"],
                        link["secret"],
                        deck_name,
                        short_name,
                        self.result.cards,
                        description=self.preset.deck_description,
                    )
                    self.preset.set_deck_link(deck_name, link["id"], resp["readwrite_secret"])
                except kotoba_api.KotobaApiError:
                    # The link is stale (deck deleted / secret rotated on
                    # Kotoba's side) - fall back to creating a fresh deck
                    # under this same name.
                    resp = kotoba_api.create_deck(
                        cookie,
                        deck_name,
                        short_name,
                        self.result.cards,
                        description=self.preset.deck_description,
                    )
                    self.preset.set_deck_link(deck_name, resp["id"], resp["readwrite_secret"])
            else:
                resp = kotoba_api.create_deck(
                    cookie,
                    deck_name,
                    short_name,
                    self.result.cards,
                    description=self.preset.deck_description,
                )
                if overwrite:
                    self.preset.set_deck_link(deck_name, resp["id"], resp["readwrite_secret"])
        except kotoba_api.KotobaApiError as exc:
            showWarning(str(exc), parent=self)
            return
        finally:
            self.unsetCursor()

        if self.on_preset_updated:
            self.on_preset_updated(self.preset)

        showInfo(
            f"Uploaded to Kotoba as \"{deck_name}\".",
            parent=self,
        )
