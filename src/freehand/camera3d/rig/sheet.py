"""The printable sheet: US letter with the four corner markers and a 100 mm scale bar (check it with a ruler: if
it is not 100 mm, the printer scaled the page and the marker positions are wrong)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from freehand.camera3d.rig.vision import DICT, LETTER_H, LETTER_W, MARKER_MM, marker_positions

DPI = 300


def _px(mm: float) -> int:
    return int(round(mm * DPI / 25.4))


def sheet_image() -> np.ndarray:
    img = np.full((_px(LETTER_H), _px(LETTER_W)), 255, np.uint8)
    d = cv2.aruco.getPredefinedDictionary(DICT)
    for mid, corners in marker_positions().items():
        side = _px(MARKER_MM)
        m = cv2.aruco.generateImageMarker(d, mid, side)
        x, y = _px(corners[0][0]), _px(corners[0][1])
        img[y : y + side, x : x + side] = m
    # 100 mm scale bar with end ticks, low on the page between the bottom markers (outside the camera crop)
    y = _px(LETTER_H - 14)
    x0 = _px((LETTER_W - 100) / 2)
    cv2.line(img, (x0, y), (x0 + _px(100), y), 0, 3)
    for x in (x0, x0 + _px(100)):
        cv2.line(img, (x, y - _px(2)), (x, y + _px(2)), 0, 3)
    cv2.putText(img, "100 mm: print at 100% (actual size)", (x0, y - _px(3)), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 2)
    return img


def write_pdf(path: Path) -> Path:
    from PIL import Image

    Image.fromarray(sheet_image()).save(path, "PDF", resolution=DPI)
    return path
