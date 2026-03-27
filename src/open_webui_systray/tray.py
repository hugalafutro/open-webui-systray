"""System tray icon, context menu, and main window toggle."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from open_webui_systray.mainwindow import MainWindow


def generate_tray_icon() -> QIcon:
    """32x32 'OI' on white rounded rectangle (parity with WinForms app)."""
    size = 32
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    rect_path = QPainterPath()
    rect_path.addRoundedRect(2, 2, size - 4, size - 4, 6, 6)
    painter.fillPath(rect_path, QColor(255, 255, 255))

    font = QFont()
    font.setPixelSize(14)
    font.setBold(True)
    font.setFamilies(["Segoe UI", "Noto Sans", "Sans Serif"])
    painter.setFont(font)
    painter.setPen(QColor(30, 30, 30))
    painter.drawText(
        2,
        2,
        size - 4,
        size - 4,
        Qt.AlignmentFlag.AlignCenter,
        "OI",
    )
    painter.end()
    return QIcon(pm)


class TrayManager:
    def __init__(self, start_url: str) -> None:
        self._start_url = start_url
        self._main: MainWindow | None = None
        self._main_window_loading = False

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
