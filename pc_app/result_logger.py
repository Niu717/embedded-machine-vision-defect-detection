from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from cap_detector_v2 import DetectionResult


class ResultLogger:
    """Save one annotated image and one CSV row for each inspected workpiece."""

    def __init__(self, root: Path) -> None:
        session_name = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.session_dir = root / session_name
        self.image_dir = self.session_dir / "annotated"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.session_dir / "detections.csv"
        self.total_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.failure_types: Counter[str] = Counter()
        with self.csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            csv.writer(file).writerow([
                "sequence", "timestamp", "verdict", "detection_message",
                "serial_connected", "annotated_image",
            ])

    def record(
        self,
        result: "DetectionResult",
        annotated_frame: np.ndarray,
        serial_connected: bool,
    ) -> Path:
        self.total_count += 1
        timestamp = datetime.now()
        verdict = "PASS" if result.passed else "FAIL"
        if result.passed:
            self.pass_count += 1
        else:
            self.fail_count += 1
            self.failure_types[result.message.removeprefix("FAIL ")] += 1

        image_name = f"{self.total_count:04d}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{verdict}.jpg"
        image_path = self.image_dir / image_name
        cv2.imwrite(str(image_path), annotated_frame)
        with self.csv_path.open("a", newline="", encoding="utf-8-sig") as file:
            csv.writer(file).writerow([
                self.total_count,
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                verdict,
                result.message,
                "yes" if serial_connected else "no",
                str(image_path.relative_to(self.session_dir)),
            ])
        return image_path

    @property
    def yield_rate(self) -> float:
        return 0.0 if self.total_count == 0 else self.pass_count * 100 / self.total_count

    def summary_text(self) -> str:
        return (
            f"Count: {self.total_count}  PASS: {self.pass_count}  "
            f"FAIL: {self.fail_count}  Yield: {self.yield_rate:.1f}%"
        )
