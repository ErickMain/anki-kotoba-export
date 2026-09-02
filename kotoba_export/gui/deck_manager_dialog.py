"""Lists the user's decks on kotobaweb.com (via the direct API) and lets
them delete old ones - mainly for tidying up decks that piled up from a
"new deck every run" preset, which the addon has no local record of at all.
"""
from aqt.qt import (
    QAbstractItemView,
    QCursor,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    Qt,
    QVBoxLayout,
)
from aqt.utils import showInfo, showWarning

from ..kotoba import api as kotoba_api


class DeckManagerDialog(QDialog):
    def __init__(self, parent, cookie: str):
        super().__init__(parent)
        self.cookie = cookie
        self.setWindowTitle("Manage Kotoba Decks")
        self.resize(480, 420)
        self._build_ui()
        self._reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Decks you own on kotobaweb.com. Select any to permanently delete."))

        self.deck_list = QListWidget()
        self.deck_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.deck_list)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._reload)
        layout.addWidget(refresh_btn)

        delete_btn = QPushButton("Delete selected")
        delete_btn.clicked.connect(self._delete_selected)
        layout.addWidget(delete_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _reload(self):
        self.deck_list.clear()
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            decks = kotoba_api.list_my_decks(self.cookie)
        except kotoba_api.KotobaApiError as exc:
            showWarning(str(exc), parent=self)
            return
        finally:
            self.unsetCursor()

        for deck in decks:
            deck_id = deck.get("_id") or deck.get("id")
            if not deck_id:
                continue
            name = deck.get("name") or "(unnamed)"
            short_name = deck.get("shortName", "")
            item = QListWidgetItem(f"{name}  [{short_name}]")
            item.setData(Qt.ItemDataRole.UserRole, deck_id)
            self.deck_list.addItem(item)

    def _delete_selected(self):
        items = self.deck_list.selectedItems()
        if not items:
            showWarning("Select at least one deck first.", parent=self)
            return

        names = "\n".join(item.text() for item in items)
        if (
            QMessageBox.question(
                self,
                "Delete decks",
                f"Permanently delete {len(items)} deck(s) on Kotoba? This cannot be undone.\n\n{names}",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        errors = []
        try:
            for item in items:
                deck_id = item.data(Qt.ItemDataRole.UserRole)
                try:
                    kotoba_api.delete_deck(self.cookie, deck_id)
                except kotoba_api.KotobaApiError as exc:
                    errors.append(f"{item.text()}: {exc}")
        finally:
            self.unsetCursor()

        self._reload()
        if errors:
            showWarning("Some decks could not be deleted:\n\n" + "\n".join(errors), parent=self)
        else:
            showInfo(f"Deleted {len(items)} deck(s).", parent=self)
