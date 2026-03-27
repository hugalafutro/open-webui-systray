"""Main window: QWebEngineView with same-host navigation and close-to-tray."""

from __future__ import annotations

import sys
from urllib.parse import urlparse

from PyQt6.QtCore import QTimer, QUrl, Qt
from PyQt6.QtGui import QColor, QCloseEvent, QGuiApplication, QIcon, QShowEvent
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QSystemTrayIcon

from open_webui_systray.config import data_dir

_EDGE_MARGIN = 8


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
    def __init__(
        self,
        start_url: str,
        window_icon: QIcon,
        tray: QSystemTrayIcon | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._start_url = start_url
        self._force_quit = False
        self._page: RestrictedWebEnginePage | None = None
        self._profile: QWebEngineProfile | None = None
        self._tray = tray

        self.setWindowTitle("Open WebUI Systray")
        self.resize(1280, 800)
        self.setWindowIcon(window_icon)

        self.setStyleSheet("background-color: black;")

        parsed = urlparse(start_url)
        allowed_host = parsed.hostname or ""
        if not allowed_host:
            raise ValueError("Start URL must include a host.")

        storage_root = data_dir()
        # defaultProfile() is off-the-record with NoPersistentCookies, so logins never persist.
        # A named profile is on-disk; keep a Python reference so the profile is not finalized
        # before the page is torn down (Qt warning about profile released while page exists).
        profile = QWebEngineProfile("open-webui-systray")
        profile.setPersistentStoragePath(str(storage_root / "qtwebengine"))
        profile.setCachePath(str(storage_root / "qtwebengine-cache"))
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
        self._profile = profile

        self._web_view = QWebEngineView(self)
        self._page = RestrictedWebEnginePage(allowed_host, profile, self._web_view)
        settings = self._page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        self._web_view.setPage(self._page)
        self._web_view.setStyleSheet("background-color: black;")
        self._page.setBackgroundColor(QColor(0, 0, 0))
        self._web_view.setZoomFactor(0.9)
        self.setCentralWidget(self._web_view)

        self._web_view.load(QUrl(start_url))

    def position_near_tray(self, tray: QSystemTrayIcon) -> None:
        """Place top-right or bottom-right of the work area from tray geometry, else platform fallback."""
        w, h = self.width(), self.height()
        g = tray.geometry()
        screen = None

        if g.width() > 0 and g.height() > 0:
            screen = QGuiApplication.screenAt(g.center())
        if screen is None:
            wh = self.windowHandle()
            if wh is not None:
                screen = wh.screen()
        if screen is None:
            screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        wa = screen.availableGeometry()

        if g.width() > 0 and g.height() > 0:
            tray_top = g.center().y() < wa.center().y()
            x = wa.right() - w - _EDGE_MARGIN
            if tray_top:
                y = wa.top() + _EDGE_MARGIN
            else:
                y = wa.bottom() - h - _EDGE_MARGIN
        else:
            x = wa.right() - w - _EDGE_MARGIN
            if sys.platform == "win32":
                y = wa.bottom() - h - _EDGE_MARGIN
            else:
                y = wa.top() + _EDGE_MARGIN

        x = max(wa.left(), min(x, wa.right() - w))
        y = max(wa.top(), min(y, wa.bottom() - h))
        self.move(x, y)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._tray is not None:
            self.position_near_tray(self._tray)
            QTimer.singleShot(0, self._deferred_position_after_show)
            QTimer.singleShot(50, self._deferred_position_after_show)

    def _deferred_position_after_show(self) -> None:
        if self._tray is not None:
            self.position_near_tray(self._tray)

    def prepare_force_quit(self) -> None:
        self._force_quit = True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._force_quit:
            # Drop the page before the window is destroyed so the profile is not torn down first.
            if self._web_view is not None:
                self._web_view.setPage(None)
            self._page = None
            event.accept()
            return
        event.ignore()
        self.hide()
