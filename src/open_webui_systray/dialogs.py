"""First-run / invalid-config URL setup dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from open_webui_systray.config import try_validate_https_url


class UrlSetupDialog(QDialog):
    def __init__(self, initial: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open WebUI Systray - server address")
        self.setModal(True)
        self._accepted_url: str | None = None

        label = QLabel("Enter the HTTPS URL to open (e.g. https://example.com):")
        self._url_box = QLineEdit(initial)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(self._url_box)

        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        ok, normalized = try_validate_https_url(self._url_box.text())
        if not ok:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Enter a valid HTTPS URL with a host name (scheme must be https).",
            )
            return
        self._accepted_url = normalized
        self.accept()

    @property
    def accepted_url(self) -> str | None:
        return self._accepted_url
