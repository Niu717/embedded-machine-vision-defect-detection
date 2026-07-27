from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2

from config import AppConfig
from defect_detector import CapDefectDetector
from serial_controller import SerialController


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "samples" / "captured"


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


def draw_overlay(frame, result, serial_connected: bool) -> None:
    color = (40, 190, 40) if result.passed else (20, 20, 235)
    if result.object_contour is not None:
        cv2.drawContours(frame, [result.object_contour], -1, color, 2)
    if result.defect_area > 0:
        frame[result.defect_mask > 0] = (0, 0, 255)
    cv2.putText(frame, result.message, (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
    state = "STM32: connected" if serial_connected else "STM32: offline"
    cv2.putText(frame, state, (30, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)
    cv2.putText(frame, "[Space] detect  [S] save  [Q] quit", (30, frame.shape[0] - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)


def main() -> None:
    args = parse_args()
    config = AppConfig(camera_index=args.camera, serial_port=args.port)
    detector = CapDefectDetector()
    serial = SerialController(config.serial_port, config.baudrate)
    camera = open_camera(config)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    auto_detect = False

    print("窗口已打开：空格执行检测，S 保存图片，Q 退出。")
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("摄像头读取失败。")
            display = frame.copy()
            result = detector.detect(frame) if auto_detect else None
            if result:
                draw_overlay(display, result, serial.connected)
            else:
                cv2.putText(display, "Press Space to detect", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)

            cv2.imshow("Workpiece Defect Detection", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" "):
                auto_detect = not auto_detect
                if auto_detect:
                    result = detector.detect(frame)
                    serial.send_result(result.passed)
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
