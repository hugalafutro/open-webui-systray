#!/usr/bin/env python3
"""Write Freedesktop hicolor PNGs from icon_brand.brand_pixmap (run after changing the art)."""

from __future__ import annotations

import sys
from pathlib import Path

# Repo root: scripts/ -> parent
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from open_webui_systray.icon_brand import brand_pixmap  # noqa: E402

ICON_BASENAME = "io.github.openwebui.systray.png"
SIZES = (32, 128)


def main() -> int:
    _app = QApplication(sys.argv)
    out_root = ROOT / "data" / "icons" / "hicolor"
    for size in SIZES:
        dest = out_root / f"{size}x{size}" / "apps" / ICON_BASENAME
        dest.parent.mkdir(parents=True, exist_ok=True)
        pm = brand_pixmap(size)
        if not pm.save(str(dest), "PNG"):
            print(f"Failed to save {dest}", file=sys.stderr)
            return 1
        print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
