"""System tray icon, context menu, and main window toggle."""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from open_webui_systray.icon_brand import brand_pixmap
from open_webui_systray.kde_global_shortcut import (
    remove_registered_shortcut,
    try_register_toggle_shortcut,
)
from open_webui_systray.mainwindow import MainWindow


def generate_tray_icon() -> QIcon:
    """32x32 'OI' on white rounded rectangle (parity with WinForms app)."""
    return QIcon(brand_pixmap(32))


class TrayManager:
    def __init__(self, start_url: str) -> None:
        self._start_url = start_url
        self._main: MainWindow | None = None
        self._main_window_loading = False
        self._kde_toggle_action: QAction | None = None

        self._icon = generate_tray_icon()
        self._tray = QSystemTrayIcon(self._icon)
        self._tray.setToolTip("Open WebUI Systray")

        menu = QMenu()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)

        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        self._kde_toggle_action = try_register_toggle_shortcut(self.toggle_main_window)
        if self._kde_toggle_action is not None:
            QApplication.instance().aboutToQuit.connect(self._cleanup_kde_global_shortcut)

    def _cleanup_kde_global_shortcut(self) -> None:
        if self._kde_toggle_action is None:
            return
        remove_registered_shortcut(self._kde_toggle_action)
        self._kde_toggle_action = None

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason != QSystemTrayIcon.ActivationReason.Trigger:
            return
        self.toggle_main_window()

    def toggle_main_window(self) -> None:
        if self._main is None:
            self._show_main_window()
            return
        if self._main.isMinimized() or not self._main.isVisible():
            self._show_main_window()
            return
        self._main.hide()

    def _show_main_window(self) -> None:
        if self._main is None:
            if self._main_window_loading:
                return
            self._main_window_loading = True
            try:
                self._main = MainWindow(self._start_url, self._icon, self._tray)
            except Exception as ex:
                QMessageBox.critical(
                    None,
                    "Open WebUI Systray",
                    f"Could not start the embedded browser (Qt WebEngine).\n\n{ex}",
                )
                QApplication.quit()
                return
            finally:
                self._main_window_loading = False

        self._main.position_near_tray(self._tray)
        self._main.showNormal()
        self._main.raise_()
        self._main.activateWindow()

    def _quit(self) -> None:
        self._tray.hide()
        if self._main is not None:
            self._main.prepare_force_quit()
            self._main.close()
            # Defer dropping the window so WebEngine teardown is not synchronous with the menu slot
            # (reduces native crashes on exit with Qt WebEngine / GPU stacks).
            QTimer.singleShot(0, self._finish_quit_after_close)
            return
        QApplication.quit()

    def _finish_quit_after_close(self) -> None:
        self._main = None
        QApplication.quit()
