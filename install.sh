#!/usr/bin/env bash
set -euo pipefail

LAUNCH=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --launch)
      LAUNCH=1
      shift
      ;;
    -h | --help)
      echo "Usage: $(basename "$0") [--launch]"
      echo "  git pull, refresh .venv + editable install, install ~/.local/bin/open-webui-systray"
      echo "  --launch  also start the app in the background"
      exit 0
      ;;
    *)
      echo "Unknown option: $1 (try --help)" >&2
      exit 1
      ;;
  esac
done

cd "$(dirname "$0")"
ROOT="$(pwd -P)"
VENV="${ROOT}/.venv"
PY="${VENV}/bin/python"
LOCAL_BIN="${HOME}/.local/bin"
WRAPPER="${LOCAL_BIN}/open-webui-systray"
VENV_CMD="${VENV}/bin/open-webui-systray"

echo "git pull ..." >&2
git pull

if [[ ! -x "$PY" ]]; then
  echo "Creating virtual environment in .venv ..." >&2
  python3 -m venv "$VENV"
fi

echo "pip install -e . ..." >&2
"$PY" -m pip install -e "$ROOT"

mkdir -p "$LOCAL_BIN"
cat >"$WRAPPER" <<EOF
#!/usr/bin/env bash
# Installed by ${ROOT}/install.sh — do not edit by hand; re-run install.sh to refresh.
set -euo pipefail
# Wayland compositors often ignore programmatic window placement; XWayland honors it.
if [[ -n "\${WAYLAND_DISPLAY:-}" ]]; then
  export QT_QPA_PLATFORM=xcb
fi
exec "${VENV_CMD}" "\$@"
EOF
chmod +x "$WRAPPER"

case ":${PATH:-}:" in
*":${HOME}/.local/bin:"*|*":${HOME}/.local/bin/:"*) ;;
*)
  echo "Note: add ~/.local/bin to PATH, e.g. export PATH=\"\$HOME/.local/bin:\$PATH\"" >&2
  ;;
esac

echo "Installed: $WRAPPER" >&2

if [[ "$LAUNCH" -eq 1 ]]; then
  case ":${PATH:-}:" in
  *":${HOME}/.local/bin:"*|*":${HOME}/.local/bin/:"*)
    open-webui-systray &
    ;;
  *)
    "$VENV_CMD" &
    ;;
  esac
  echo "Launched in background." >&2
fi
