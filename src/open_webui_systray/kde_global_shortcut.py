"""Optional Plasma global shortcut via org.kde.kglobalaccel (gdbus for register/unregister; QtDBus for key signal)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable

from PyQt6.QtCore import QObject, QCoreApplication, pyqtSlot
from PyQt6.QtDBus import QDBusConnection
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication

KGLOBALACCEL_DEST = "org.kde.kglobalaccel"
KGLOBALACCEL_PATH = "/kglobalaccel"
KGLOBALACCEL_IFACE = "org.kde.KGlobalAccel"
COMPONENT_IFACE = "org.kde.kglobalaccel.Component"

ACTION_OBJECT_NAME = "toggle-main-window"
DEFAULT_SEQUENCE = "Ctrl+Alt+O"
# setShortcut third arg: KGlobalAccelD::SetShortcutFlag (kglobalacceld.h). SetPresent = 2.
# Without it, kglobalacceld never marks the shortcut present / grabs keys; invokeShortcut still works.
_SET_SHORTCUT_FLAGS = 2  # SetPresent


def _likely_kde_plasma_session() -> bool:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if re.search(r"KDE|Plasma", desktop, re.IGNORECASE):
        return True
    if os.environ.get("KDE_FULL_SESSION") == "true":
        return True
    if os.environ.get("KDE_SESSION_VERSION"):
        return True
    return False


def _gdbus_available() -> bool:
    return shutil.which("gdbus") is not None


def _gdbus_call(method: str, *json_args: str) -> subprocess.CompletedProcess[str]:
    """Call org.kde.KGlobalAccel.<method> on /kglobalaccel; further args are gdbus JSON values."""
    cmd = [
        "gdbus",
        "call",
        "--session",
        "--dest",
        KGLOBALACCEL_DEST,
        "--object-path",
        KGLOBALACCEL_PATH,
        "--method",
        f"{KGLOBALACCEL_IFACE}.{method}",
        *json_args,
    ]
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )


def _parse_gdbus_int_list(reply_stdout: str) -> list[int] | None:
    """Parse gdbus reply like '([201326671],)' or '()' for setShortcut."""
    m = re.search(r"\(([\s\S]*)\)\s*$", reply_stdout.strip())
    if not m:
        return None
    inner = m.group(1).strip()
    if inner == "":
        return []
    # ([201326671],) or ([201326671])
    m2 = re.search(r"\[([^\]]*)\]", inner)
    if not m2:
        return []
    nums = m2.group(1).strip()
    if not nums:
        return []
    return [int(x.strip()) for x in nums.split(",") if x.strip()]


def _do_register(action_id: list[str]) -> bool:
    if not _gdbus_available():
        return False
    payload = json.dumps(action_id)
    r = _gdbus_call("doRegister", payload)
    return r.returncode == 0 and "Error" not in (r.stderr or "")


def _set_shortcut(action_id: list[str], key_ints: list[int]) -> list[int] | None:
    """Returns assigned key ints, or None on failure."""
    if not _gdbus_available():
        return None
    keys_json = json.dumps(key_ints)
    r = _gdbus_call("setShortcut", json.dumps(action_id), keys_json, str(_SET_SHORTCUT_FLAGS))
    if r.returncode != 0 or (r.stderr and "Error" in r.stderr):
        return None
    return _parse_gdbus_int_list(r.stdout)


def _get_component_path(component: str) -> str | None:
    if not _gdbus_available():
        return None
    r = _gdbus_call("getComponent", json.dumps(component))
    if r.returncode != 0:
        return None
    m = re.search(r"objectpath\s+'([^']+)'", r.stdout)
    return m.group(1) if m else None


def _unregister(component: str, action: str) -> None:
    if not _gdbus_available():
        return
    subprocess.run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            KGLOBALACCEL_DEST,
            "--object-path",
            KGLOBALACCEL_PATH,
            "--method",
            f"{KGLOBALACCEL_IFACE}.unregister",
            json.dumps(component),
            json.dumps(action),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )


class KdeGlobalShortcutHandle(QObject):
    """Holds D-Bus signal connection; call cleanup() on exit."""

    def __init__(
        self,
        component: str,
        action_name: str,
        component_path: str,
        toggle: Callable[[], None],
    ) -> None:
        super().__init__(QCoreApplication.instance())
        self._component = component
        self._action_name = action_name
        self._component_path = component_path
        self._toggle = toggle
        self._signal_connected = QDBusConnection.sessionBus().connect(
            KGLOBALACCEL_DEST,
            component_path,
            COMPONENT_IFACE,
            "globalShortcutPressed",
            self._on_global_shortcut_pressed,
        )

    @property
    def signal_connected(self) -> bool:
        return self._signal_connected

    @pyqtSlot(str, str, "qlonglong")
    def _on_global_shortcut_pressed(self, component_unique: str, action_unique: str, _ts: int) -> None:
        if component_unique == self._component and action_unique == self._action_name:
            self._toggle()

    def cleanup(self) -> None:
        if self._signal_connected:
            QDBusConnection.sessionBus().disconnect(
                KGLOBALACCEL_DEST,
                self._component_path,
                COMPONENT_IFACE,
                "globalShortcutPressed",
                self._on_global_shortcut_pressed,
            )
            self._signal_connected = False
        _unregister(self._component, self._action_name)


def try_register_toggle_shortcut(toggle: Callable[[], None]) -> KdeGlobalShortcutHandle | None:
    """Register default Ctrl+Alt+O with KGlobalAccel, or return None if skipped/failed."""
    if not _likely_kde_plasma_session():
        return None
    if not _gdbus_available():
        return None

    app = QApplication.instance()
    if app is None:
        return None

    component = app.applicationName() or "open-webui-systray"
    display = app.applicationDisplayName() or "Open WebUI Systray"
    action_id = [
        component,
        ACTION_OBJECT_NAME,
        display,
        "Show/Hide window",
    ]

    seq = QKeySequence(DEFAULT_SEQUENCE)
    if seq.count() < 1:
        return None
    combined = seq[0].toCombined()
    key_ints = [combined]

    if not _do_register(action_id):
        return None

    assigned = _set_shortcut(action_id, key_ints)
    if assigned is None:
        _unregister(component, ACTION_OBJECT_NAME)
        return None
    if len(assigned) == 0:
        _unregister(component, ACTION_OBJECT_NAME)
        return None

    comp_path = _get_component_path(component)
    if not comp_path:
        _unregister(component, ACTION_OBJECT_NAME)
        return None

    handle = KdeGlobalShortcutHandle(component, ACTION_OBJECT_NAME, comp_path, toggle)
    if not handle.signal_connected:
        _unregister(component, ACTION_OBJECT_NAME)
        return None
    return handle


def remove_registered_shortcut(handle: KdeGlobalShortcutHandle | None) -> None:
    """Unregister global shortcuts and disconnect D-Bus signal."""
    if handle is None:
        return
    handle.cleanup()
