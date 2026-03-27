#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
VENV="${ROOT}/.venv"
PY="${VENV}/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "Creating virtual environment in .venv ..." >&2
  python3 -m venv "$VENV"
fi

if ! "$PY" -c "import PyQt6.QtWebEngineWidgets" 2>/dev/null; then
  echo "Installing dependencies (pip install -e .) ..." >&2
  "$PY" -m pip install -e "$ROOT"
fi

# Wayland compositors often ignore programmatic window placement; XWayland honors it.
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
  export QT_QPA_PLATFORM=xcb
fi

exec "$PY" -m open_webui_systray "$@"
