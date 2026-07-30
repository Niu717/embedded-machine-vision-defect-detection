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
    EDGE_CIRCULARITY_HIGH_LIMIT = 0.85
    DEFORMATION_RADIAL_PEAK_LIMIT = 0.08
    DARK_SPOT_AREA_LIMIT = 300.0
    SCRATCH_LENGTH_LIMIT = 500.0

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

        circularity, radial_cv, radial_peak = self._edge_features(contour, centre)
        deformation = radial_peak > self.DEFORMATION_RADIAL_PEAK_LIMIT
        scratch_mask, scratch_length = self._find_scratch(gray, centre, radius)
        scratch = scratch_length >= self.SCRATCH_LENGTH_LIMIT
        edge_defect = not deformation and (
            circularity < self.EDGE_CIRCULARITY_LIMIT
            or (
                circularity > self.EDGE_CIRCULARITY_HIGH_LIMIT
                and not scratch
            )
            or radial_cv > self.EDGE_RADIAL_CV_LIMIT
        )
        dark_mask, dark_area = self._find_dark_spot(gray, centre, radius)
        dark_spot = dark_area >= self.DARK_SPOT_AREA_LIMIT

        defect_mask = cv2.bitwise_or(dark_mask, scratch_mask)
        if edge_defect or deformation:
            cv2.drawContours(defect_mask, [contour], -1, 255, thickness=6)

        defects: list[str] = []
        if deformation:
            defects.append("DEFORMATION")
        if edge_defect:
            defects.append("EDGE")
        if dark_spot:
            defects.append("DARK SPOT")
        if scratch:
            defects.append("SCRATCH")
        passed = not defects
        message = "PASS" if passed else "FAIL " + " + ".join(defects)
        defect_area = dark_area + scratch_length
        if edge_defect or deformation:
            defect_area += cv2.arcLength(contour, True)
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
    ) -> tuple[float, float, float]:
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = 4 * math.pi * area / max(perimeter * perimeter, 1)
        points = contour[:, 0, :].astype(np.float32)
        distances = np.hypot(
            points[:, 0] - centre[0],
            points[:, 1] - centre[1],
        )
        radial_cv = float(np.std(distances) / max(np.mean(distances), 1))
        radial_median = float(np.median(distances))
        radial_peak = float(
            (np.percentile(distances, 99.5) - radial_median)
            / max(radial_median, 1)
        )
        return circularity, radial_cv, radial_peak

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

    @staticmethod
    def _find_scratch(
        gray: np.ndarray, centre: tuple[float, float], radius: float
    ) -> tuple[np.ndarray, float]:
        inner = np.zeros_like(gray)
        centre_int = (round(centre[0]), round(centre[1]))
        cv2.circle(inner, centre_int, round(radius * 0.62), 255, cv2.FILLED)
        edges = cv2.Canny(gray, 70, 150)
        edges = cv2.bitwise_and(edges, inner)
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=28,
            minLineLength=max(35, int(radius * 0.28)),
            maxLineGap=10,
        )

        mask = np.zeros_like(gray)
        total_length = 0.0
        if lines is not None:
            for x1, y1, x2, y2 in lines.reshape(-1, 4):
                length = math.hypot(x2 - x1, y2 - y1)
                total_length += length
                cv2.line(mask, (x1, y1), (x2, y2), 255, thickness=3)
        return mask, total_length
