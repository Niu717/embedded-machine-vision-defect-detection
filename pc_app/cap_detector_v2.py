from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np

from config import DetectorConfig


@dataclass
class DetectionResult:
    passed: bool
    message: str
    object_contour: np.ndarray | None
    defect_mask: np.ndarray
    defect_area: float


class CapDefectDetector:
    """Detect edge damage and dark spots on a bright cap over a dark mat."""

    EDGE_RADIAL_CV_LIMIT = 0.016
    EDGE_CIRCULARITY_LIMIT = 0.75
    DARK_SPOT_AREA_LIMIT = 300.0

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()

    def detect(self, frame: np.ndarray) -> DetectionResult:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        located = self._locate_cap(gray)
        empty = np.zeros_like(gray)
        if located is None:
            return DetectionResult(False, "NO CAP", None, empty, 0.0)

        _, contour, centre, radius = located
        area = cv2.contourArea(contour)
        if area < self.config.min_object_area:
            return DetectionResult(False, "CAP TOO SMALL", contour, empty, 0.0)

        circularity, radial_cv = self._edge_features(contour, centre)
        edge_defect = (
            circularity < self.EDGE_CIRCULARITY_LIMIT
            or radial_cv > self.EDGE_RADIAL_CV_LIMIT
        )
        dark_mask, dark_area = self._find_dark_spot(gray, centre, radius)
        dark_spot = dark_area >= self.DARK_SPOT_AREA_LIMIT

        defect_mask = dark_mask.copy()
        if edge_defect:
            cv2.drawContours(defect_mask, [contour], -1, 255, thickness=6)

        defects: list[str] = []
        if edge_defect:
            defects.append("EDGE")
        if dark_spot:
            defects.append("DARK SPOT")
        passed = not defects
        message = "PASS" if passed else "FAIL " + " + ".join(defects)
        defect_area = dark_area + (cv2.arcLength(contour, True) if edge_defect else 0)
        return DetectionResult(passed, message, contour, defect_mask, float(defect_area))

    def _locate_cap(
        self, gray: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, tuple[float, float], float] | None:
        height, width = gray.shape
        blurred = cv2.medianBlur(gray, 9)
        _, binary = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        binary = cv2.morphologyEx(
            binary, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2
        )
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        candidates: list[np.ndarray] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            x, y, box_width, box_height = cv2.boundingRect(contour)
            aspect = box_width / max(box_height, 1)
            touches_border = (
                x <= 3
                or y <= 3
                or x + box_width >= width - 3
                or y + box_height >= height - 3
            )
            if (
                self.config.min_object_area <= area <= width * height * 0.25
                and 0.65 <= aspect <= 1.35
                and not touches_border
            ):
                candidates.append(contour)
        if not candidates:
            return None

        contour = max(candidates, key=cv2.contourArea)
        (cx, cy), radius = cv2.minEnclosingCircle(contour)
        object_mask = np.zeros_like(gray)
        cv2.drawContours(object_mask, [contour], -1, 255, cv2.FILLED)
        return object_mask, contour, (float(cx), float(cy)), float(radius)

    @staticmethod
    def _edge_features(
        contour: np.ndarray, centre: tuple[float, float]
    ) -> tuple[float, float]:
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = 4 * math.pi * area / max(perimeter * perimeter, 1)
        points = contour[:, 0, :].astype(np.float32)
        distances = np.hypot(
            points[:, 0] - centre[0],
            points[:, 1] - centre[1],
        )
        radial_cv = float(np.std(distances) / max(np.mean(distances), 1))
        return circularity, radial_cv

    @staticmethod
    def _find_dark_spot(
        gray: np.ndarray, centre: tuple[float, float], radius: float
    ) -> tuple[np.ndarray, float]:
        inner = np.zeros_like(gray)
        centre_int = (round(centre[0]), round(centre[1]))
        cv2.circle(inner, centre_int, round(radius * 0.62), 255, cv2.FILLED)
        values = gray[inner > 0]
        median = float(np.median(values))

        dark = np.zeros_like(gray)
        dark[(gray < median - 35) & (inner > 0)] = 255
        dark = cv2.morphologyEx(
            dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)
        )
        contours, _ = cv2.findContours(
            dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        retained = np.zeros_like(gray)
        largest_area = 0.0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= 80:
                cv2.drawContours(retained, [contour], -1, 255, cv2.FILLED)
                largest_area = max(largest_area, area)
        return retained, largest_area
