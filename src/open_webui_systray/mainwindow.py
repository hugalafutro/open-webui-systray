"""Main window: QWebEngineView with same-host navigation and close-to-tray."""

from __future__ import annotations

import logging
import sys
import time
from urllib.parse import urlparse

from PyQt6.QtCore import QTimer, QUrl, Qt
from PyQt6.QtGui import (
    QColor,
    QCloseEvent,
    QCursor,
    QDesktopServices,
    QGuiApplication,
    QHideEvent,
    QIcon,
    QScreen,
    QShowEvent,
)
from PyQt6.QtWebEngineCore import (
    QWebEngineCertificateError,
    QWebEngineLoadingInfo,
    QWebEngineNewWindowRequest,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QSystemTrayIcon

from open_webui_systray.config import data_dir, webview_zoom_factor

_EDGE_MARGIN = 8
_MAX_LOAD_RETRIES = 30
_RELOAD_DELAY_MS = 5000
_LONG_HIDE_RELOAD_SECONDS = 300

log = logging.getLogger(__name__)


def _is_navigation_allowed(uri_string: str, allowed_host: str) -> bool:
    """Match WinForms WebView2 NavigationStarting policy."""
    if not uri_string:
        return False
    if uri_string.startswith("#"):
        return True
    parsed = urlparse(uri_string)
    scheme = parsed.scheme.lower()
    if not scheme:
        return False
    if scheme == "about":
        return uri_string == "about:blank"
    if scheme in ("http", "https"):
        host = parsed.hostname or ""
        return host.lower() == allowed_host.lower()
    return False


def _should_delegate_to_system_browser(uri_string: str, allowed_host: str) -> bool:
    """URLs that are blocked in-webview but should open in the OS default app (browser, mail, …)."""
    if not uri_string or uri_string.startswith("#"):
        return False
    parsed = urlparse(uri_string)
    scheme = parsed.scheme.lower()
    if scheme in ("http", "https"):
        host = parsed.hostname or ""
        return bool(host) and host.lower() != allowed_host.lower()
    if scheme in ("mailto", "tel", "sms"):
        return True
    return False


def _try_open_with_system_handler(url: QUrl) -> bool:
    ok = QDesktopServices.openUrl(url)
    if not ok:
        log.warning("Could not open URL with system handler: %s", url.toString())
    return ok


class RestrictedWebEnginePage(QWebEnginePage):
    def __init__(
        self,
        allowed_host: str,
        profile: QWebEngineProfile,
        failure_callback,
        parent=None,
    ) -> None:
        super().__init__(profile, parent)
        self._allowed_host = allowed_host
        self._failure_callback = failure_callback

    def acceptNavigationRequest(
        self,
        url: QUrl,
        nav_type: QWebEnginePage.NavigationType,
        is_main_frame: bool,
    ) -> bool:
        url_str = url.toString()
        if _is_navigation_allowed(url_str, self._allowed_host):
            return True
        if _should_delegate_to_system_browser(url_str, self._allowed_host):
            if is_main_frame or (
                nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked
            ):
                _try_open_with_system_handler(url)
            return False
        return False

    def certificateError(self, error: QWebEngineCertificateError) -> bool:
        self._failure_callback(
            "certificate",
            (
                "TLS certificate error while loading "
                f"{error.url().toString()}: {error.description()} "
                f"(type={error.type().name}, overridable={error.isOverridable()})"
            ),
        )
        return False


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
        self._allowed_host = ""
        self._page: RestrictedWebEnginePage | None = None
        self._profile: QWebEngineProfile | None = None
        self._web_view: QWebEngineView | None = None
        self._tray = tray
        self._retry_count = 0
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._reload_start_url)
        self._was_hidden_for_tray = False
        self._hidden_since_monotonic: float | None = None
        self._reload_when_shown = False
        self._recreate_when_shown = False
        self._screen_changed_connected = False
        self._screen_changed_connect_attempts = 0

        self.setWindowTitle("Open WebUI Systray")
        self.resize(1280, 800)
        self.setWindowIcon(window_icon)

        self.setStyleSheet("background-color: black;")

        parsed = urlparse(start_url)
        allowed_host = parsed.hostname or ""
        if not allowed_host:
            raise ValueError("Start URL must include a host.")
        self._allowed_host = allowed_host

        self._create_browser(load_start_url=True)

    def _create_profile(self) -> QWebEngineProfile:
        storage_root = data_dir()
        # defaultProfile() is off-the-record with NoPersistentCookies, so logins never persist.
        # A named profile is on-disk; keep a Python reference so the profile is not finalized
        # before the page is torn down (Qt warning about profile released while page exists).
        profile = QWebEngineProfile("open-webui-systray", self)
        profile.setPersistentStoragePath(str(storage_root / "qtwebengine"))
        profile.setCachePath(str(storage_root / "qtwebengine-cache"))
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
        return profile

    def _create_browser(self, load_start_url: bool) -> None:
        profile = self._create_profile()
        web_view = QWebEngineView(self)
        page = RestrictedWebEnginePage(
            self._allowed_host,
            profile,
            self._handle_browser_failure,
            web_view,
        )
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        web_view.setPage(page)
        web_view.setStyleSheet("background-color: black;")
        page.setBackgroundColor(QColor(0, 0, 0))
        web_view.setZoomFactor(webview_zoom_factor())
        page.loadingChanged.connect(self._on_loading_changed)
        page.newWindowRequested.connect(self._on_new_window_requested)
        web_view.renderProcessTerminated.connect(self._on_render_process_terminated)

        self._profile = profile
        self._page = page
        self._web_view = web_view
        self.setCentralWidget(web_view)

        if load_start_url:
            web_view.load(QUrl(self._start_url))

    def _on_new_window_requested(self, request: QWebEngineNewWindowRequest) -> None:
        """Handle target=_blank and window.open; external URLs use the default browser."""
        u = request.requestedUrl()
        s = u.toString()
        if _should_delegate_to_system_browser(s, self._allowed_host):
            _try_open_with_system_handler(u)
            return
        if _is_navigation_allowed(s, self._allowed_host) and self._web_view is not None:
            self._web_view.load(u)

    def _destroy_browser(self) -> None:
        if self._web_view is None:
            return
        self._retry_timer.stop()
        old_web_view = self._web_view
        old_page = self._page
        self._web_view = None
        self._page = None
        self._profile = None
        self.takeCentralWidget()
        if old_page is not None:
            old_web_view.setPage(None)
            old_page.deleteLater()
        old_web_view.deleteLater()

    def _recreate_browser(self, reason: str, load_start_url: bool = True) -> None:
        if self._force_quit:
            return
        log.warning("Recreating embedded browser: %s", reason)
        self._destroy_browser()
        self._create_browser(load_start_url=load_start_url)

    def _schedule_recovery(self, failure_kind: str, reason: str) -> None:
        if self._force_quit:
            return
        log.warning("%s", reason)
        if failure_kind == "renderer":
            if self.isVisible():
                self._recreate_browser(reason)
            else:
                self._recreate_when_shown = True
                self._reload_when_shown = True
            return

        if not self.isVisible():
            self._reload_when_shown = True
            return
        if self._retry_count < _MAX_LOAD_RETRIES:
            self._retry_count += 1
            self._retry_timer.stop()
            self._retry_timer.start(_RELOAD_DELAY_MS)
            return
        self._recreate_browser(reason)

    def _handle_browser_failure(self, failure_kind: str, reason: str) -> None:
        self._schedule_recovery(failure_kind, reason)

    def _reload_start_url(self) -> None:
        if self._force_quit or self._web_view is None:
            return
        if not self.isVisible():
            self._reload_when_shown = True
            return
        log.info("Reloading start URL: %s", self._start_url)
        self._web_view.load(QUrl(self._start_url))

    def _on_loading_changed(self, info: QWebEngineLoadingInfo) -> None:
        st = info.status()
        if st == QWebEngineLoadingInfo.LoadStatus.LoadStartedStatus:
            return
        if st == QWebEngineLoadingInfo.LoadStatus.LoadStoppedStatus:
            return

        http_5xx = (
            info.errorDomain() == QWebEngineLoadingInfo.ErrorDomain.HttpStatusCodeDomain
            and info.errorCode() >= 500
        )
        if st == QWebEngineLoadingInfo.LoadStatus.LoadFailedStatus or http_5xx:
            self._handle_browser_failure(
                "load",
                (
                    "WebEngine load failed for "
                    f"{info.url().toString()}: status={st.name}, "
                    f"domain={info.errorDomain().name}, code={info.errorCode()}, "
                    f"message={info.errorString()!r}"
                ),
            )
            return

        if st == QWebEngineLoadingInfo.LoadStatus.LoadSucceededStatus:
            self._retry_count = 0
            self._reload_when_shown = False
            self._recreate_when_shown = False
            self._retry_timer.stop()
            log.info("WebEngine load succeeded: %s", info.url().toString())

    def _on_render_process_terminated(
        self,
        termination_status: QWebEngineView.RenderProcessTerminationStatus,
        exit_code: int,
    ) -> None:
        self._handle_browser_failure(
            "renderer",
            (
                "WebEngine renderer terminated: "
                f"status={termination_status.name}, exit_code={exit_code}"
            ),
        )

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
            screen = self.screen()
        if screen is None:
            screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QApplication.primaryScreen()
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

    def _ensure_screen_changed_connection(self) -> None:
        if self._screen_changed_connected:
            return
        wh = self.windowHandle()
        if wh is None:
            self._screen_changed_connect_attempts += 1
            if self._screen_changed_connect_attempts <= 10:
                QTimer.singleShot(0, self._ensure_screen_changed_connection)
            return
        wh.screenChanged.connect(self._on_window_screen_changed)
        self._screen_changed_connected = True

    def _on_window_screen_changed(self, _screen: QScreen | None) -> None:
        if self._force_quit or self._web_view is None:
            return
        self._web_view.setZoomFactor(webview_zoom_factor())

    def hideEvent(self, event: QHideEvent) -> None:
        self._retry_timer.stop()
        self._was_hidden_for_tray = True
        self._hidden_since_monotonic = time.monotonic()
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._ensure_screen_changed_connection()
        if self._was_hidden_for_tray:
            self._was_hidden_for_tray = False
            hidden_for = 0.0
            if self._hidden_since_monotonic is not None:
                hidden_for = time.monotonic() - self._hidden_since_monotonic
            need_reload = (
                self._reload_when_shown
                or self._retry_count >= _MAX_LOAD_RETRIES
                or hidden_for >= _LONG_HIDE_RELOAD_SECONDS
            )
            need_recreate = self._recreate_when_shown
            self._retry_count = 0
            self._retry_timer.stop()
            self._reload_when_shown = False
            self._recreate_when_shown = False
            self._hidden_since_monotonic = None
            if need_recreate and not self._force_quit:
                self._recreate_browser(
                    f"Browser was hidden for recovery and must be recreated after {hidden_for:.1f}s",
                )
            elif need_reload and not self._force_quit and self._web_view is not None:
                self._web_view.load(QUrl(self._start_url))
        if self._tray is not None:
            self.position_near_tray(self._tray)
            QTimer.singleShot(0, self._deferred_position_after_show)
            QTimer.singleShot(50, self._deferred_position_after_show)

    def _deferred_position_after_show(self) -> None:
        if self._tray is not None:
            self.position_near_tray(self._tray)

    def prepare_force_quit(self) -> None:
        self._retry_timer.stop()
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
