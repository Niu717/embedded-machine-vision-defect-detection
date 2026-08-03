from __future__ import annotations

import argparse
import os
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2

from config import AppConfig
from cap_detector_v2 import CapDefectDetector
from result_logger import ResultLogger
from serial_controller import SerialController


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "samples" / "captured"
RESULT_DIR = ROOT / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="工件缺陷检测上位机 - 第一版")
    parser.add_argument("--camera", type=int, default=1, help="摄像头编号，默认 1（外接工业摄像头）")
    parser.add_argument("--port", default="", help="STM32 串口，例如 COM3")
    return parser.parse_args()


def open_camera(config: AppConfig) -> cv2.VideoCapture:
    camera = cv2.VideoCapture(config.camera_index, cv2.CAP_MSMF)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
    camera.set(cv2.CAP_PROP_FPS, 30)
    if not camera.isOpened():
        raise RuntimeError("无法打开摄像头，请尝试 --camera 1 或检查 USB 连接。")
    return camera


def draw_overlay(frame, result, serial_connected: bool, statistics: str = "") -> None:
    color = (40, 190, 40) if result.passed else (20, 20, 235)
    if result.object_contour is not None:
        cv2.drawContours(frame, [result.object_contour], -1, color, 2)
    if result.defect_area > 0:
        frame[result.defect_mask > 0] = (0, 0, 255)
    cv2.putText(frame, result.message, (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
    state = "STM32: connected" if serial_connected else "STM32: offline"
    cv2.putText(frame, state, (30, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)
    if statistics:
        cv2.putText(frame, statistics, (30, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    cv2.putText(frame, "[Space] detect  [R] rearm  [S] save  [Q] quit", (30, frame.shape[0] - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)


def stable_result_from(history):
    """Return a result only after at least 2/3 of recent frames agree."""
    if len(history) < 8:
        return None
    message, votes = Counter(item.message for item in history).most_common(1)[0]
    required_votes = max(6, (len(history) * 2 + 2) // 3)
    if votes < required_votes:
        return None
    return next(item for item in reversed(history) if item.message == message)


def main() -> None:
    args = parse_args()
    config = AppConfig(camera_index=args.camera, serial_port=args.port)
    detector = CapDefectDetector()
    serial = SerialController(config.serial_port, config.baudrate)
    camera = open_camera(config)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    logger = ResultLogger(RESULT_DIR)
    auto_detect = False
    result_history = deque(maxlen=12)
    stable_result = None
    # One command is sent per workpiece.  A stable NO CAP result rearms the
    # system, so two consecutive defective caps both generate an alarm.
    inspection_armed = True

    print("窗口已打开：空格执行检测，S 保存图片，Q 退出。")
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("摄像头读取失败。")
            display = frame.copy()
            if auto_detect:
                raw_result = detector.detect(frame)
                result_history.append(raw_result)
                candidate = stable_result_from(result_history)
                if candidate is not None:
                    stable_result = candidate
                    if stable_result.message == "NO CAP":
                        inspection_armed = True
                    elif inspection_armed:
                        serial.send_result(stable_result.passed)
                        annotated = frame.copy()
                        draw_overlay(annotated, stable_result, serial.connected)
                        saved_path = logger.record(stable_result, annotated, serial.connected)
                        print(f"Recorded #{logger.total_count}: {stable_result.message} -> {saved_path}")
                        inspection_armed = False

            if auto_detect and stable_result is not None:
                draw_overlay(display, stable_result, serial.connected, logger.summary_text())
                cv2.putText(
                    display,
                    f"Stable vote: {len(result_history)}/12",
                    (30, 160),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 0),
                    2,
                )
                if stable_result.message != "NO CAP" and not inspection_armed:
                    cv2.putText(
                        display,
                        "Result sent: remove cap for next test",
                        (30, 190),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (255, 255, 0),
                        2,
                    )
            elif auto_detect:
                cv2.putText(display, "STABILIZING...", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 215, 255), 3)
                cv2.putText(display, logger.summary_text(), (30, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
            else:
                cv2.putText(display, "Press Space to detect", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)
                cv2.putText(display, logger.summary_text(), (30, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)

            cv2.imshow("Workpiece Defect Detection", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" "):
                auto_detect = not auto_detect
                result_history.clear()
                stable_result = None
                inspection_armed = True
            if key == ord("r"):
                # Manual fallback when two workpieces are changed with no
                # visible gap between them.
                result_history.clear()
                stable_result = None
                inspection_armed = True
            if key == ord("s"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                target = CAPTURE_DIR / f"sample_{timestamp}.jpg"
                cv2.imwrite(str(target), frame)
                print(f"已保存: {target}")
    finally:
        serial.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
