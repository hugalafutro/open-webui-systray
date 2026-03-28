"""Programmatic app icon: black \"OI\" on white rounded rectangle (matches legacy WinForms look)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap


def brand_pixmap(size: int) -> QPixmap:
    """Render the brand mark at the given square size (e.g. 32 tray, 128 desktop theme)."""
    if size < 4:
        raise ValueError("size must be at least 4")

    scale = size / 32.0
    margin = max(1, int(round(2 * scale)))
    radius = max(1, int(round(6 * scale)))
    inner = size - 2 * margin
    font_px = max(6, int(round(14 * scale)))

    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    rect_path = QPainterPath()
    rect_path.addRoundedRect(margin, margin, inner, inner, radius, radius)
    painter.fillPath(rect_path, QColor(255, 255, 255))

    font = QFont()
    font.setPixelSize(font_px)
    font.setBold(True)
    font.setFamilies(["Segoe UI", "Noto Sans", "Sans Serif"])
    painter.setFont(font)
    painter.setPen(QColor(30, 30, 30))
    painter.drawText(
        margin,
        margin,
        inner,
        inner,
        Qt.AlignmentFlag.AlignCenter,
        "OI",
    )
    painter.end()
    return pm
