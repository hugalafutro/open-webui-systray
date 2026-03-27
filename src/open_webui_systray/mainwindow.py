"""Main window: QWebEngineView with same-host navigation and close-to-tray."""

from __future__ import annotations

from urllib.parse import urlparse

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QColor, QCloseEvent, QIcon
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

from open_webui_systray.config import data_dir


def _is_navigation_allowed(uri_string: str, allowed_host: str) -> bool:
    """Match WinForms WebView2 NavigationStarting policy."""
    if not uri_string:
        return True
    if uri_string.startswith("#"):
        return True
    parsed = urlparse(uri_string)
    scheme = parsed.scheme.lower()
    if not scheme:
        return False
    if scheme == "about":
        return True
    if scheme == "data":
        return True
    if scheme == "blob":
        return True
    if scheme in ("http", "https"):
        host = parsed.hostname or ""
        return host.lower() == allowed_host.lower()
    return False


class RestrictedWebEnginePage(QWebEnginePage):
    def __init__(self, allowed_host: str, profile: QWebEngineProfile, parent=None) -> None:
        super().__init__(profile, parent)
        self._allowed_host = allowed_host

    def acceptNavigationRequest(
        self,
        url: QUrl,
        _nav_type: QWebEnginePage.NavigationType,
        _is_main_frame: bool,
    ) -> bool:
        return _is_navigation_allowed(url.toString(), self._allowed_host)


class MainWindow(QMainWindow):
    def __init__(self, start_url: str, window_icon: QIcon, parent=None) -> None:
        super().__init__(parent)
        self._start_url = start_url
        self._force_quit = False

        self.setWindowTitle("Open WebUI Systray")
        self.resize(1280, 800)
        self.setWindowIcon(window_icon)

        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            wa = screen.availableGeometry()
            self.move(wa.right() - self.width(), wa.bottom() - self.height())

        self.setStyleSheet("background-color: black;")

        parsed = urlparse(start_url)
        allowed_host = parsed.hostname or ""
        if not allowed_host:
            raise ValueError("Start URL must include a host.")

        storage_root = data_dir()
        profile = QWebEngineProfile("OpenWebUiSystray")
        profile.setPersistentStoragePath(str(storage_root / "qtwebengine"))
        profile.setCachePath(str(storage_root / "qtwebengine-cache"))

        page = RestrictedWebEnginePage(allowed_host, profile, self)
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        self._web_view = QWebEngineView(self)
        self._web_view.setPage(page)
        self._web_view.setStyleSheet("background-color: black;")
        page.setBackgroundColor(QColor(0, 0, 0))
        self._web_view.setZoomFactor(0.9)
        self.setCentralWidget(self._web_view)

        self._web_view.load(QUrl(start_url))

    def prepare_force_quit(self) -> None:
        self._force_quit = True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._force_quit:
            event.accept()
            return
        event.ignore()
        self.hide()
