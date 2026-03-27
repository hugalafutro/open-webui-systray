"""Load/save HTTPS URL from open-webui-systray.cfg (XDG config dir)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

CONFIG_FILENAME = "open-webui-systray.cfg"
APP_CONFIG_DIRNAME = "open-webui-systray"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    d = Path(base) / APP_CONFIG_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    d = Path(base) / APP_CONFIG_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def try_validate_https_url(input_text: str) -> tuple[bool, str]:
    """Return (ok, normalized_url). Normalized is empty if invalid."""
    trimmed = input_text.strip()
    if not trimmed:
        return False, ""

    parsed = urlparse(trimmed)
    if parsed.scheme.lower() != "https":
        return False, ""

    if not parsed.netloc:
        return False, ""

    # Rebuild absolute URI string similar to Uri.AbsoluteUri
    normalized = parsed.geturl()
    return True, normalized


def try_load() -> tuple[bool, str, str | None]:
    """
    Returns (success, url, initial_for_dialog_if_invalid).
    If file missing or no valid line: success False, initial None unless invalid line.
    """
    path = config_path()
    if not path.is_file():
        return False, "", None

    initial_for_dialog: str | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        ok, normalized = try_validate_https_url(line)
        if ok:
            return True, normalized, None
        initial_for_dialog = line
        return False, "", initial_for_dialog

    return False, "", None


def save(url: str) -> None:
    ok, normalized = try_validate_https_url(url)
    if not ok:
        raise ValueError("URL must be a valid https address with a host.")
    path = config_path()
    path.write_text(normalized + os.linesep, encoding="utf-8")
