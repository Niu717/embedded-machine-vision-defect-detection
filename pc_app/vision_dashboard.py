from __future__ import annotations

import argparse
from collections import Counter, deque
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk

from cap_detector_v2 import CapDefectDetector
from config import AppConfig
from result_logger import ResultLogger
from reference_detector import ReferenceComparisonDetector
from serial_controller import SerialController


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results"
CAPTURE_DIR = ROOT / "samples" / "captured"
CALIBRATION_DIR = ROOT / "calibration"

MODE_INFO = {
    "Bottle Cap": "Production mode: edge, deformation, dark spot and scratch inspection.",
    "Metal Part": "Reference-comparison mode: save a standard image after fixing the workpiece and light.",
    "PCB Board": "Reference-comparison mode: detects visible layout and surface differences, not microscopic solder defects.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Machine vision inspection dashboard")
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--port", default="")
    return parser.parse_args()


def stable_result_from(history):
    if len(history) < 8:
        return None
    message, votes = Counter(item.message for item in history).most_common(1)[0]
    required = max(6, (len(history) * 2 + 2) // 3)
    if votes < required:
        return None
    return next(item for item in reversed(history) if item.message == message)


class VisionDashboard:
    def __init__(self, camera_index: int, serial_port: str) -> None:
        self.config = AppConfig(camera_index=camera_index, serial_port=serial_port)
        self.detector = CapDefectDetector()
        self.serial = SerialController(serial_port, self.config.baudrate)
        self.camera = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        if not self.camera.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_index}.")

        self.mode = "Bottle Cap"
        self.logger = ResultLogger(RESULT_DIR, self.mode)
        self.reference_detectors = {
            "Metal Part": ReferenceComparisonDetector(CALIBRATION_DIR, "metal_part"),
            "PCB Board": ReferenceComparisonDetector(CALIBRATION_DIR, "pcb_board"),
        }
        self.detecting = False
        self.inspection_armed = True
        self.history = deque(maxlen=12)
        self.last_frame = None
        self.last_result = None

        self.root = tk.Tk()
        self.root.title("Embedded Machine Vision Defect Detection")
        self.root.geometry("1360x820")
        self.root.minsize(1100, 720)
        self.root.configure(bg="#0b1220")
        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._update_frame()

    def _build_layout(self) -> None:
        header = tk.Frame(self.root, bg="#102a43", height=72)
        header.pack(fill="x")
        tk.Label(header, text="EMBEDDED MACHINE VISION", fg="#f8fafc", bg="#102a43", font=("Arial", 20, "bold")).pack(side="left", padx=24, pady=18)
        self.connection_label = tk.Label(header, fg="#5eead4", bg="#102a43", font=("Arial", 11, "bold"))
        self.connection_label.pack(side="right", padx=24)

        body = tk.Frame(self.root, bg="#0b1220")
        body.pack(fill="both", expand=True, padx=18, pady=16)
        sidebar = tk.Frame(body, bg="#102a43", width=190)
        sidebar.pack(side="left", fill="y", padx=(0, 14))
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="INSPECTION MODE", fg="#94a3b8", bg="#102a43", font=("Arial", 10, "bold")).pack(anchor="w", padx=18, pady=(22, 10))
        self.mode_buttons: dict[str, tk.Button] = {}
        for mode in MODE_INFO:
            button = tk.Button(sidebar, text=mode, command=lambda value=mode: self.switch_mode(value), relief="flat", anchor="w", padx=18, bd=0, font=("Arial", 11, "bold"))
            button.pack(fill="x", padx=10, pady=4, ipady=9)
            self.mode_buttons[mode] = button
        tk.Frame(sidebar, bg="#1e3a5f", height=1).pack(fill="x", padx=18, pady=18)
        tk.Label(sidebar, text="System flow\nCamera → OpenCV → STM32\nOLED / Buzzer / Servo", justify="left", fg="#cbd5e1", bg="#102a43", font=("Arial", 10)).pack(anchor="w", padx=18)

        center = tk.Frame(body, bg="#111827")
        center.pack(side="left", fill="both", expand=True)
        self.preview = tk.Label(center, bg="#020617")
        self.preview.pack(fill="both", expand=True, padx=12, pady=(12, 4))
        toolbar = tk.Frame(center, bg="#111827")
        toolbar.pack(fill="x", padx=14, pady=12)
        self.detect_button = tk.Button(toolbar, text="Start inspection", command=self.toggle_detection, bg="#0f766e", fg="white", relief="flat", font=("Arial", 11, "bold"), padx=16, pady=8)
        self.detect_button.pack(side="left", padx=(0, 8))
        self.reference_button = tk.Button(toolbar, text="Save standard image", command=self.save_reference, bg="#7c3aed", fg="white", relief="flat", font=("Arial", 11, "bold"), padx=14, pady=8)
        self.reference_button.pack(side="left", padx=4)
        tk.Button(toolbar, text="Re-arm", command=self.rearm, bg="#334155", fg="white", relief="flat", font=("Arial", 11), padx=14, pady=8).pack(side="left", padx=4)
        tk.Button(toolbar, text="Save frame", command=self.save_frame, bg="#334155", fg="white", relief="flat", font=("Arial", 11), padx=14, pady=8).pack(side="left", padx=4)
        tk.Button(toolbar, text="Export report", command=self.export_report, bg="#2563eb", fg="white", relief="flat", font=("Arial", 11, "bold"), padx=14, pady=8).pack(side="right")

        panel = tk.Frame(body, bg="#102a43", width=290)
        panel.pack(side="right", fill="y", padx=(14, 0))
        panel.pack_propagate(False)
        tk.Label(panel, text="LATEST RESULT", fg="#94a3b8", bg="#102a43", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(24, 6))
        self.verdict_label = tk.Label(panel, text="WAITING", fg="#fbbf24", bg="#102a43", font=("Arial", 25, "bold"))
        self.verdict_label.pack(anchor="w", padx=20)
        self.detail_label = tk.Label(panel, text="Press Start inspection", justify="left", wraplength=245, fg="#cbd5e1", bg="#102a43", font=("Arial", 10))
        self.detail_label.pack(anchor="w", padx=20, pady=(8, 22))
        tk.Frame(panel, bg="#1e3a5f", height=1).pack(fill="x", padx=20)
        tk.Label(panel, text="SESSION STATISTICS", fg="#94a3b8", bg="#102a43", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(22, 6))
        self.stats_label = tk.Label(panel, text="Count: 0\nPASS: 0\nFAIL: 0\nYield: 0.0%", justify="left", fg="#f8fafc", bg="#102a43", font=("Arial", 12))
        self.stats_label.pack(anchor="w", padx=20)
        self.mode_label = tk.Label(panel, text="", justify="left", wraplength=245, fg="#93c5fd", bg="#102a43", font=("Arial", 9))
        self.mode_label.pack(anchor="w", padx=20, pady=(26, 0))
        self._refresh_mode_style()

    def _refresh_mode_style(self) -> None:
        for name, button in self.mode_buttons.items():
            active = name == self.mode
            button.configure(bg="#0f766e" if active else "#102a43", fg="#ffffff" if active else "#cbd5e1", activebackground="#0f766e" if active else "#1e3a5f")
        self.mode_label.configure(text=MODE_INFO[self.mode])
        reference_needed = self.mode != "Bottle Cap"
        self.reference_button.configure(state="normal" if reference_needed else "disabled")

    def switch_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self.logger = ResultLogger(RESULT_DIR, mode)
        self.detecting = False
        self.history.clear()
        self.last_result = None
        self.inspection_armed = True
        self.detect_button.configure(text="Start inspection")
        self.verdict_label.configure(text="READY", fg="#fbbf24")
        self.detail_label.configure(text=MODE_INFO[mode])
        self._refresh_mode_style()

    def toggle_detection(self) -> None:
        if self.mode != "Bottle Cap" and not self.reference_detectors[self.mode].ready:
            messagebox.showinfo("Reference required", "Please place a qualified standard workpiece in the fixed position, then click Save standard image.")
            return
        self.detecting = not self.detecting
        self.history.clear()
        self.last_result = None
        self.inspection_armed = True
        self.detect_button.configure(text="Pause inspection" if self.detecting else "Start inspection")
        self.detail_label.configure(text="Waiting for stable camera result..." if self.detecting else "Inspection paused")

    def save_reference(self) -> None:
        if self.mode == "Bottle Cap":
            return
        if self.last_frame is None:
            messagebox.showwarning("Camera", "No camera frame is available yet.")
            return
        path = self.reference_detectors[self.mode].save_reference(self.last_frame)
        self.detail_label.configure(text=f"Standard image saved: {path.name}")
        self.verdict_label.configure(text="CALIBRATED", fg="#4ade80")

    def rearm(self) -> None:
        self.history.clear()
        self.inspection_armed = True
        self.detail_label.configure(text="Re-armed. Place the next workpiece.")

    def save_frame(self) -> None:
        if self.last_frame is None:
            return
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        target = CAPTURE_DIR / f"dashboard_{self.mode.lower().replace(' ', '_')}_{datetime_now()}.jpg"
        cv2.imwrite(str(target), self.last_frame)
        self.detail_label.configure(text=f"Saved: {target.name}")

    def export_report(self) -> None:
        json_path, html_path = self.logger.export_report()
        messagebox.showinfo("Report exported", f"JSON: {json_path.name}\nHTML: {html_path.name}\nFolder: {self.logger.session_dir}")

    def _record_result(self, result, frame) -> None:
        self.serial.send_result(result.passed)
        annotated = frame.copy()
        color = (50, 180, 50) if result.passed else (20, 20, 235)
        if result.object_contour is not None:
            cv2.drawContours(annotated, [result.object_contour], -1, color, 2)
        if result.defect_area > 0:
            annotated[result.defect_mask > 0] = (0, 0, 255)
        cv2.putText(annotated, result.message, (25, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
        self.logger.record(result, annotated, self.serial.connected)
        self.inspection_armed = False

    def _update_frame(self) -> None:
        ok, frame = self.camera.read()
        if ok:
            self.last_frame = frame
            display = frame.copy()
            if self.detecting:
                raw_result = self.detector.detect(frame) if self.mode == "Bottle Cap" else self.reference_detectors[self.mode].detect(frame)
                self.history.append(raw_result)
                candidate = stable_result_from(self.history)
                if candidate is not None:
                    self.last_result = candidate
                    if candidate.message == "NO CAP":
                        self.inspection_armed = True
                    elif self.inspection_armed:
                        self._record_result(candidate, frame)
            self._render_overlay(display)
            rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image.thumbnail((850, 670))
            self.tk_image = ImageTk.PhotoImage(image)
            self.preview.configure(image=self.tk_image)
        self.root.after(30, self._update_frame)

    def _render_overlay(self, frame) -> None:
        self.connection_label.configure(text="STM32 CONNECTED" if self.serial.connected else "STM32 OFFLINE")
        self.stats_label.configure(text=self.logger.summary_text().replace("  ", "\n"))
        if self.last_result is None:
            return
        result = self.last_result
        color = (50, 180, 50) if result.passed else (20, 20, 235)
        if result.object_contour is not None:
            cv2.drawContours(frame, [result.object_contour], -1, color, 2)
        if result.defect_area > 0:
            frame[result.defect_mask > 0] = (0, 0, 255)
        cv2.putText(frame, result.message, (25, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
        verdict = "PASS" if result.passed else "FAIL"
        self.verdict_label.configure(text=verdict, fg="#4ade80" if result.passed else "#fb7185")
        state = "Result sent. Remove cap for next test." if not self.inspection_armed else "Place the next workpiece."
        self.detail_label.configure(text=f"{result.message}\n{state}")

    def close(self) -> None:
        self.serial.close()
        self.camera.release()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def datetime_now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def main() -> None:
    args = parse_args()
    app = VisionDashboard(args.camera, args.port)
    app.run()


if __name__ == "__main__":
    main()
