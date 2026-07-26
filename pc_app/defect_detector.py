from __future__ import annotations

from dataclasses import dataclass

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
    """第一版传统视觉检测器。

    面向固定光照、固定位置的圆形瓶盖。它先定位最大圆形工件，
    再从亮度异常区域中提取污渍/明显划痕。缺口检测将在采集完
    标准样本后通过轮廓模板参数启用。
    """

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()

    def detect(self, frame: np.ndarray) -> DetectionResult:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (self.config.blur_kernel, self.config.blur_kernel), 0)

        object_mask = self._find_object(gray)
        contours, _ = cv2.findContours(object_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return DetectionResult(False, "NO OBJECT", None, np.zeros_like(gray), 0.0)

        contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(contour)
        if area < self.config.min_object_area:
            return DetectionResult(False, "OBJECT TOO SMALL", contour, np.zeros_like(gray), 0.0)

        defect_mask, defect_area = self._find_surface_anomaly(gray, object_mask)
        ratio = defect_area / area
        passed = ratio < self.config.defect_ratio_limit
        message = "PASS" if passed else f"FAIL anomaly {ratio * 100:.2f}%"
        return DetectionResult(passed, message, contour, defect_mask, defect_area)

    def _find_object(self, gray: np.ndarray) -> np.ndarray:
        _, binary = cv2.threshold(gray, self.config.threshold_value, 255, cv2.THRESH_BINARY)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=1)
        # 工件上的暗污渍不能被视为 ROI 的孔洞；使用外轮廓填满工件区域。
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros_like(binary)
        for contour in contours:
            if cv2.contourArea(contour) >= self.config.min_object_area:
                cv2.drawContours(filled, [contour], -1, 255, thickness=cv2.FILLED)
        return filled

    def _find_surface_anomaly(self, gray: np.ndarray, object_mask: np.ndarray) -> tuple[np.ndarray, float]:
        # 工件轮廓本身会造成很强的亮度跃迁，不能把边缘误判为缺陷。
        # 先向内收缩检测区域；黑帽提取暗污渍，顶帽提取亮斑/划痕。
        inner_mask = cv2.erode(object_mask, np.ones((21, 21), np.uint8), iterations=1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))
        dark_anomaly = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
        bright_anomaly = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
        difference = cv2.max(dark_anomaly, bright_anomaly)
        _, anomaly = cv2.threshold(difference, 18, 255, cv2.THRESH_BINARY)
        anomaly = cv2.bitwise_and(anomaly, inner_mask)
        anomaly = cv2.morphologyEx(anomaly, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

        contours, _ = cv2.findContours(anomaly, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        retained = np.zeros_like(anomaly)
        for contour in contours:
            if cv2.contourArea(contour) >= self.config.min_defect_area:
                cv2.drawContours(retained, [contour], -1, 255, thickness=cv2.FILLED)
        return retained, float(cv2.countNonZero(retained))
