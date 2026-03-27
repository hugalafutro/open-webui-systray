"""Entry: single-instance lock, QApplication, URL resolution, tray."""

from __future__ import annotations

import fcntl
import os
import sys
import tempfile
from pathlib import Path
from typing import IO

# Ensure Qt WebEngine is loaded before QApplication (Qt recommendation).
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

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
    ok, url, initial = try_load()
    if ok:
        return url

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


def main() -> int:
    lock_fp = acquire_single_instance_lock()
    if lock_fp is None:
        return 0

    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setApplicationName("Open WebUI Systray")

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
