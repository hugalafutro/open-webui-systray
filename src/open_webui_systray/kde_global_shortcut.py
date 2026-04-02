"""Optional Plasma/KDE global shortcut via KGlobalAccel (PyKDE6)."""

from __future__ import annotations

import os
import re
from collections.abc import Callable

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QApplication


def _likely_kde_plasma_session() -> bool:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if re.search(r"KDE|Plasma", desktop, re.IGNORECASE):
        return True
    if os.environ.get("KDE_FULL_SESSION") == "true":
        return True
    if os.environ.get("KDE_SESSION_VERSION"):
        return True
    return False


def try_register_toggle_shortcut(toggle: Callable[[], None]) -> QAction | None:
    """Register default Ctrl+Alt+O with KGlobalAccel, or return None if skipped/failed."""
    if not _likely_kde_plasma_session():
        return None

    try:
        from PyKDE6.KGlobalAccel import KGlobalAccel
    except ImportError:
        return None

    app = QApplication.instance()
    if app is None:
        return None

    action = QAction(app)
    action.setObjectName("toggle-main-window")
    action.setText("Show/Hide window")

    seq = QKeySequence("Ctrl+Alt+O")
    ok = KGlobalAccel.setGlobalShortcut(action, seq)
    if not ok:
        action.deleteLater()
        return None

    action.triggered.connect(toggle)
    return action


def remove_registered_shortcut(action: QAction) -> None:
    """Unregister global shortcuts for this action (e.g. on application exit)."""
    try:
        from PyKDE6.KGlobalAccel import KGlobalAccel
    except ImportError:
        return
    KGlobalAccel.self().removeAllShortcuts(action)
