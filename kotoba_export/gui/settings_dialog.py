"""Advanced-mode settings: enabling direct API upload and pasting a session
cookie. Kept separate from the main dialog since most users won't need it.
"""
from aqt.qt import (
    QCheckBox,
    QCursor,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPushButton,
    Qt,
    QVBoxLayout,
)
from aqt.utils import showInfo, showWarning

from ..kotoba import api as kotoba_api
from .deck_manager_dialog import DeckManagerDialog

WARNING_TEXT = (
    "Advanced mode uploads decks straight to kotobaweb.com using an internal, "
    "undocumented API and your own browser session cookie - not a real API key, "
    "because Kotoba doesn't have one. Treat the cookie like a password: anyone "
    "who has it can act as your Kotoba account. It can also stop working any "
    "time Kotoba changes their site. The clipboard export (default) needs none "
    "of this.\n\n"
    "To get the cookie: open kotobaweb.com in your browser while logged in, "
    "open DevTools -> Network, click any request to kotobaweb.com, open its "
    "Headers tab, and copy the full value next to 'Cookie:' under Request "
    "Headers - a string with an '=' in it, like 'connect.sid=...'.\n\n"
    "Don't copy from a separate 'Cookies' table/tab that just shows a bare "
    "value with no name - if you paste one of those by mistake we'll assume "
    "it's connect.sid, but the Headers tab is the safe source."
)


class SettingsDialog(QDialog):
    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Kotoba Export Settings")
        self.resize(480, 320)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        warning = QLabel(WARNING_TEXT)
        warning.setWordWrap(True)
        layout.addWidget(warning)

        self.enabled_check = QCheckBox("Enable advanced mode (direct upload to Kotoba)")
        layout.addWidget(self.enabled_check)

        layout.addWidget(QLabel("Session cookie:"))
        self.cookie_edit = QLineEdit()
        self.cookie_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.cookie_edit)

        test_row = QPushButton("Test connection")
        test_row.clicked.connect(self._test_connection)
        layout.addWidget(test_row)

        manage_decks_btn = QPushButton("Manage decks...")
        manage_decks_btn.setToolTip(
            "List and delete decks you own on Kotoba - useful for tidying up ones left over "
            "from a \"new deck every run\" preset, since those aren't tracked locally."
        )
        manage_decks_btn.clicked.connect(self._open_deck_manager)
        layout.addWidget(manage_decks_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self):
        adv = self.config.get("advanced", {})
        self.enabled_check.setChecked(bool(adv.get("direct_api_enabled")))
        self.cookie_edit.setText(adv.get("session_cookie", ""))

    def _test_connection(self):
        cookie = self.cookie_edit.text().strip()
        if not cookie:
            showWarning("Paste a session cookie first.", parent=self)
            return
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            data = kotoba_api.test_connection(cookie)
        except kotoba_api.KotobaApiError as exc:
            showWarning(str(exc), parent=self)
            return
        finally:
            self.unsetCursor()
        username = data.get("username") or data.get("discordUsername") or "your account"
        showInfo(f"Connected to Kotoba as {username}.", parent=self)

    def _open_deck_manager(self):
        cookie = self.cookie_edit.text().strip()
        if not cookie:
            showWarning("Paste a session cookie first.", parent=self)
            return
        DeckManagerDialog(self, cookie).exec()

    def _on_save(self):
        self.config.setdefault("advanced", {})
        self.config["advanced"]["direct_api_enabled"] = self.enabled_check.isChecked()
        self.config["advanced"]["session_cookie"] = self.cookie_edit.text().strip()
        self.accept()
