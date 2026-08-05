from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class ReferenceDetectionResult:
    passed: bool
    message: str
    object_contour: np.ndarray | None
    defect_mask: np.ndarray
    defect_area: float


class ReferenceComparisonDetector:
    """Detect visible changes against a saved standard image.

    This detector is intentionally designed for a fixed camera, fixed light and
    fixed workpiece location. It is suitable for coarse metal/PCB appearance
    checks, not microscopic solder-joint inspection.
    """

    def __init__(self, calibration_dir: Path, mode_key: str) -> None:
        self.path = calibration_dir / f"{mode_key}_reference.png"
        self.reference: np.ndarray | None = None
        self.diff_threshold = 35
        self.area_limit = 600.0
        self._load_reference()

    @property
    def ready(self) -> bool:
        return self.reference is not None

    def save_reference(self, frame: np.ndarray) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.reference = frame.copy()
        cv2.imwrite(str(self.path), self.reference)
        return self.path

    def detect(self, frame: np.ndarray) -> ReferenceDetectionResult:
        if self.reference is None:
            return ReferenceDetectionResult(
                False,
                "REFERENCE REQUIRED",
                None,
                np.zeros(frame.shape[:2], dtype=np.uint8),
                0.0,
            )
        reference = cv2.resize(self.reference, (frame.shape[1], frame.shape[0]))
        current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        current_gray = cv2.GaussianBlur(current_gray, (5, 5), 0)
        reference_gray = cv2.GaussianBlur(reference_gray, (5, 5), 0)
        current_gray = cv2.normalize(current_gray, None, 0, 255, cv2.NORM_MINMAX)
        reference_gray = cv2.normalize(reference_gray, None, 0, 255, cv2.NORM_MINMAX)
        difference = cv2.absdiff(current_gray, reference_gray)
        _, mask = cv2.threshold(difference, self.diff_threshold, 255, cv2.THRESH_BINARY)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        retained = np.zeros_like(mask)
        total_area = 0.0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= self.area_limit:
                total_area += area
                cv2.drawContours(retained, [contour], -1, 255, cv2.FILLED)
        passed = total_area == 0
        message = "PASS" if passed else "FAIL TEMPLATE DIFFERENCE"
        return ReferenceDetectionResult(passed, message, None, retained, total_area)

    def _load_reference(self) -> None:
        if self.path.exists():
            image = cv2.imread(str(self.path))
            if image is not None:
                self.reference = image
