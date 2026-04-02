"""Entry: single-instance lock, QApplication, URL resolution, tray."""

from __future__ import annotations

import os


def _disable_mangohud_for_app() -> None:
    # MangoHud's Vulkan implicit layer enables when MANGOHUD=1; DISABLE_MANGOHUD=1 turns it off
    # (see /usr/share/vulkan/implicit_layer.d/MangoHud*.json). Also drop the shim from LD_PRELOAD
    # when a gaming profile preloads it.
    os.environ["DISABLE_MANGOHUD"] = "1"
    preload = os.environ.get("LD_PRELOAD", "")
    if not preload:
        return
    orig = [p for p in preload.split(":") if p]
    kept = [p for p in orig if "mangohud" not in p.lower()]
    if len(kept) == len(orig):
        return
    if kept:
        os.environ["LD_PRELOAD"] = ":".join(kept)
    else:
        del os.environ["LD_PRELOAD"]


_disable_mangohud_for_app()

import fcntl
import sys
import tempfile
from pathlib import Path
from typing import IO

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox, QSystemTrayIcon

from open_webui_systray.config import save, try_load
from open_webui_systray.dialogs import UrlSetupDialog
from open_webui_systray.tray import TrayManager


def acquire_single_instance_lock() -> IO[str] | None:
    """Exclusive flock on XDG_RUNTIME_DIR; return open file or None if another instance holds it."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        runtime = str(Path(tempfile.gettempdir()) / "open-webui-systray-runtime")
    Path(runtime).mkdir(parents=True, exist_ok=True)
    lock_path = Path(runtime) / "open-webui-systray.lock"
    fp = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fp.close()
        return None
    return fp


def try_resolve_start_url() -> str | None:
    ok, url, initial, load_error = try_load()
    if ok:
        return url

    if load_error:
        QMessageBox.warning(
            None,
            "Open WebUI Systray",
            f"{load_error}\n\nPlease review the config file or enter a new URL.",
        )

    dlg = UrlSetupDialog(initial or "")
    if dlg.exec() != QDialog.DialogCode.Accepted or dlg.accepted_url is None:
        return None

    try:
        save(dlg.accepted_url)
    except OSError as ex:
        QMessageBox.critical(
            None,
            "Open WebUI Systray",
            f"Could not save configuration file:\n{ex}",
        )
        return None

    return dlg.accepted_url


def _prefer_xcb_on_wayland() -> None:
    # Match run.sh: Wayland often ignores window.move(); XWayland honors tray-adjacent placement.
    if os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def _try_import_qt_webengine() -> str | None:
    """Load Qt WebEngine before QApplication; return an error string if unavailable."""
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    except ImportError as ex:
        return str(ex)
    return None


def main() -> int:
    lock_fp = acquire_single_instance_lock()
    if lock_fp is None:
        return 0

    try:
        _prefer_xcb_on_wayland()
        webengine_import_error = _try_import_qt_webengine()
        if webengine_import_error is not None:
            app = QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Open WebUI Systray",
                "Qt WebEngine is not available.\n\n"
                "Install the `PyQt6-WebEngine` Python package or your distribution's "
                "PyQt6 WebEngine package, then start the app again.\n\n"
                f"Import error: {webengine_import_error}",
            )
            return 1
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        # WM_CLASS follows applicationName; *.desktop StartupWMClass must match (case-sensitive) for Plasma.
        app.setApplicationName("open-webui-systray")
        app.setApplicationDisplayName("Open WebUI Systray")
        app.setDesktopFileName("io.github.openwebui.systray")

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(
                None,
                "Open WebUI Systray",
                "System tray is not available on this system.",
            )
            return 1

        start_url = try_resolve_start_url()
        if start_url is None:
            return 1

        # Keep reference so tray/C++ objects are not garbage-collected.
        _tray = TrayManager(start_url)
        return app.exec()
    finally:
        lock_fp.close()


if __name__ == "__main__":
    raise SystemExit(main())
