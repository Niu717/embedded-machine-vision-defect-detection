"""Measure geometric and surface features from the labelled cap images."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "samples" / "captured"
LABELS_FILE = ROOT / "samples" / "labels.csv"


def find_cap(gray: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int]] | None:
    height, width = gray.shape
    blurred = cv2.medianBlur(gray, 9)
    _, global_mask = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    global_mask = cv2.morphologyEx(
        global_mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2
    )
    global_contours, _ = cv2.findContours(
        global_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    cap_candidates: list[np.ndarray] = []
    for contour in global_contours:
        area = cv2.contourArea(contour)
        bx, by, bw, bh = cv2.boundingRect(contour)
        aspect = bw / max(bh, 1)
        touches_border = bx <= 3 or by <= 3 or bx + bw >= width - 3 or by + bh >= height - 3
        if 15_000 <= area <= 250_000 and 0.65 <= aspect <= 1.35 and not touches_border:
            cap_candidates.append(contour)

    if cap_candidates:
        contour = max(cap_candidates, key=cv2.contourArea)
        (cx, cy), enclosing_radius = cv2.minEnclosingCircle(contour)
        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [contour], -1, 255, cv2.FILLED)
        return mask, (round(cx), round(cy), round(enclosing_radius))

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min(height, width) // 4,
        param1=100,
        param2=45,
        minRadius=80,
        maxRadius=320,
    )
    if circles is None:
        return None

    candidates = np.round(circles[0]).astype(int)
    candidates = [
        (x, y, radius)
        for x, y, radius in candidates
        if radius < x < width - radius and radius < y < height - radius
    ]
    if not candidates:
        return None

    cx, cy = width / 2, height / 2
    x, y, radius = min(
        candidates,
        key=lambda item: math.hypot(item[0] - cx, item[1] - cy) - item[2],
    )

    search = np.zeros_like(gray)
    cv2.circle(search, (x, y), int(radius * 1.18), 255, cv2.FILLED)
    pixels = gray[search > 0]
    threshold, _ = cv2.threshold(
        pixels.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    foreground = np.zeros_like(gray)
    foreground[(gray >= threshold) & (search > 0)] = 255
    foreground = cv2.morphologyEx(
        foreground, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2
    )

    contours, _ = cv2.findContours(
        foreground, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    centre = (float(x), float(y))
    contours = [c for c in contours if cv2.pointPolygonTest(c, centre, False) >= 0]
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    mask = np.zeros_like(gray)
    cv2.drawContours(mask, [contour], -1, 255, cv2.FILLED)
    return mask, (x, y, radius)


def measure(image: np.ndarray) -> dict[str, float] | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    located = find_cap(gray)
    if located is None:
        return None

    mask, (x, y, radius) = located
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    circularity = 4 * math.pi * area / max(perimeter * perimeter, 1)

    points = contour[:, 0, :].astype(np.float32)
    distances = np.hypot(points[:, 0] - x, points[:, 1] - y)
    radial_cv = float(np.std(distances) / max(np.mean(distances), 1))
    radial_median = float(np.median(distances))
    radial_peak = float(
        (np.percentile(distances, 99.5) - radial_median) / max(radial_median, 1)
    )

    inner = np.zeros_like(gray)
    cv2.circle(inner, (x, y), int(radius * 0.62), 255, cv2.FILLED)
    values = gray[inner > 0]
    median = float(np.median(values))
    dark = np.zeros_like(gray)
    dark[(gray < median - 35) & (inner > 0)] = 255
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    dark_contours, _ = cv2.findContours(
        dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    largest_dark = max(
        (cv2.contourArea(c) for c in dark_contours),
        default=0.0,
    )

    return {
        "radius": float(radius),
        "circularity": circularity,
        "radial_cv": radial_cv,
        "radial_peak": radial_peak,
        "largest_dark": largest_dark,
    }


def main() -> None:
    with LABELS_FILE.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    print("time   label                  radius circularity radial_cv radial_peak dark_area")
    for row in rows:
        image = cv2.imread(str(CAPTURE_DIR / row["filename"]))
        features = measure(image)
        label = "normal" if row["is_normal"] == "1" else row["notes"]
        time_text = Path(row["filename"]).stem[-6:]
        if features is None:
            print(f"{time_text} {label:<22} NOT FOUND")
            continue
        print(
            f"{time_text} {label:<22} "
            f"{features['radius']:6.1f} {features['circularity']:11.4f} "
            f"{features['radial_cv']:9.4f} {features['radial_peak']:11.4f} "
            f"{features['largest_dark']:9.1f}"
        )


if __name__ == "__main__":
    main()
