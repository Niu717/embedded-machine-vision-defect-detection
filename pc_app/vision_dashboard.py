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
    "Bottle Cap": "瓶盖检测：识别边缘缺口、变形、黑点和划痕等缺陷。",
    "Metal Part": "金属工件对比检测：固定工件和光照后，先保存一张合格工件标准图。",
    "PCB Board": "PCB 对比检测：识别可见的布局与表面差异，不用于微小焊点缺陷检测。",
}

MODE_NAMES = {
    "Bottle Cap": "瓶盖检测",
    "Metal Part": "金属工件检测",
    "PCB Board": "PCB 板检测",
}


def chinese_result(message: str) -> str:
    """Translate detector result text for the human-facing Tkinter dashboard."""
    translated = message
    for english, chinese in (
        ("FAIL ", "不合格："),
        ("PASS", "合格"),
        ("NO CAP", "未检测到工件"),
        ("SCRATCH", "划痕"),
        ("EDGE", "边缘缺口"),
        ("DEFORMATION", "变形"),
        ("DARK SPOT", "黑点"),
        ("REFERENCE DIFFERENCE", "与标准图差异明显"),
    ):
        translated = translated.replace(english, chinese)
    return translated


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
        self.root.title("嵌入式机器视觉缺陷检测系统")
        self.root.geometry("1600x900")
        self.root.minsize(1300, 760)
        self.root.configure(bg="#0b1220")
        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._update_frame()

    def _build_layout(self) -> None:
        header = tk.Frame(self.root, bg="#102a43", height=72)
        header.pack(fill="x")
        tk.Label(header, text="嵌入式机器视觉缺陷检测系统", fg="#f8fafc", bg="#102a43", font=("Microsoft YaHei", 20, "bold")).pack(side="left", padx=24, pady=18)
        self.connection_label = tk.Label(header, fg="#5eead4", bg="#102a43", font=("Microsoft YaHei", 11, "bold"))
        self.connection_label.pack(side="right", padx=24)

        body = tk.Frame(self.root, bg="#0b1220")
        body.pack(fill="both", expand=True, padx=18, pady=16)
        sidebar = tk.Frame(body, bg="#102a43", width=230)
        sidebar.pack(side="left", fill="y", padx=(0, 14))
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="检测模式", fg="#94a3b8", bg="#102a43", font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", padx=18, pady=(22, 10))
        self.mode_buttons: dict[str, tk.Button] = {}
        for mode in MODE_INFO:
            button = tk.Button(sidebar, text=MODE_NAMES[mode], command=lambda value=mode: self.switch_mode(value), relief="flat", anchor="w", padx=18, bd=0, font=("Microsoft YaHei", 11, "bold"))
            button.pack(fill="x", padx=10, pady=4, ipady=9)
            self.mode_buttons[mode] = button
        tk.Frame(sidebar, bg="#1e3a5f", height=1).pack(fill="x", padx=18, pady=18)
        tk.Label(
            sidebar,
            text="系统流程\n摄像头\n↓\nOpenCV 图像检测\n↓\nSTM32 控制\n↓\nOLED / 蜂鸣器 / 舵机",
            justify="left",
            fg="#cbd5e1",
            bg="#102a43",
            font=("Microsoft YaHei", 10),
        ).pack(anchor="w", padx=18)

        center = tk.Frame(body, bg="#111827")
        center.pack(side="left", fill="both", expand=True)
        self.preview = tk.Label(center, bg="#020617")
        self.preview.pack(fill="both", expand=True, padx=12, pady=(12, 4))
        toolbar = tk.Frame(center, bg="#111827")
        toolbar.pack(fill="x", padx=14, pady=12)
        self.detect_button = tk.Button(toolbar, text="开始检测", command=self.toggle_detection, bg="#0f766e", fg="white", relief="flat", font=("Microsoft YaHei", 11, "bold"), padx=16, pady=8)
        self.detect_button.pack(side="left", padx=(0, 8))
        self.reference_button = tk.Button(toolbar, text="保存标准图", command=self.save_reference, bg="#7c3aed", fg="white", relief="flat", font=("Microsoft YaHei", 11, "bold"), padx=14, pady=8)
        self.reference_button.pack(side="left", padx=4)
        tk.Button(toolbar, text="重新检测", command=self.rearm, bg="#334155", fg="white", relief="flat", font=("Microsoft YaHei", 11), padx=14, pady=8).pack(side="left", padx=4)
        tk.Button(toolbar, text="保存当前图像", command=self.save_frame, bg="#334155", fg="white", relief="flat", font=("Microsoft YaHei", 11), padx=14, pady=8).pack(side="left", padx=4)
        tk.Button(toolbar, text="导出检测报告", command=self.export_report, bg="#2563eb", fg="white", relief="flat", font=("Microsoft YaHei", 11, "bold"), padx=14, pady=8).pack(side="right")

        panel = tk.Frame(body, bg="#102a43", width=380)
        panel.pack(side="right", fill="y", padx=(14, 0))
        panel.pack_propagate(False)
        tk.Label(panel, text="最新检测结果", fg="#94a3b8", bg="#102a43", font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", padx=20, pady=(24, 6))
        self.verdict_label = tk.Label(panel, text="等待检测", fg="#fbbf24", bg="#102a43", font=("Microsoft YaHei", 25, "bold"))
        self.verdict_label.pack(anchor="w", padx=20)
        self.detail_label = tk.Label(
            panel,
            text="点击“开始检测”后开始识别",
            justify="left",
            anchor="nw",
            wraplength=330,
            fg="#cbd5e1",
            bg="#102a43",
            font=("Microsoft YaHei", 10),
        )
        self.detail_label.pack(fill="x", padx=20, pady=(8, 22))
        tk.Frame(panel, bg="#1e3a5f", height=1).pack(fill="x", padx=20)
        tk.Label(panel, text="本次检测统计", fg="#94a3b8", bg="#102a43", font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", padx=20, pady=(22, 6))
        self.stats_label = tk.Label(panel, text="检测总数：0\n合格：0\n不合格：0\n合格率：0.0%", justify="left", fg="#f8fafc", bg="#102a43", font=("Microsoft YaHei", 12))
        self.stats_label.pack(anchor="w", padx=20)
        self.mode_label = tk.Label(
            panel,
            text="",
            justify="left",
            anchor="nw",
            wraplength=330,
            fg="#93c5fd",
            bg="#102a43",
            font=("Microsoft YaHei", 9),
        )
        self.mode_label.pack(fill="x", padx=20, pady=(26, 0))
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
        self.detect_button.configure(text="开始检测")
        self.verdict_label.configure(text="准备就绪", fg="#fbbf24")
        self.detail_label.configure(text=MODE_INFO[mode])
        self._refresh_mode_style()

    def toggle_detection(self) -> None:
        if self.mode != "Bottle Cap" and not self.reference_detectors[self.mode].ready:
            messagebox.showinfo("需要标准图", "请将合格工件放在固定检测位置，并点击“保存标准图”。")
            return
        self.detecting = not self.detecting
        self.history.clear()
        self.last_result = None
        self.inspection_armed = True
        self.detect_button.configure(text="暂停检测" if self.detecting else "开始检测")
        self.detail_label.configure(text="正在等待稳定的相机检测结果……" if self.detecting else "检测已暂停")

    def save_reference(self) -> None:
        if self.mode == "Bottle Cap":
            return
        if self.last_frame is None:
            messagebox.showwarning("摄像头", "暂未获取到相机画面。")
            return
        path = self.reference_detectors[self.mode].save_reference(self.last_frame)
        self.detail_label.configure(text=f"标准图已保存：{path.name}")
        self.verdict_label.configure(text="标准图已保存", fg="#4ade80")

    def rearm(self) -> None:
        self.history.clear()
        self.inspection_armed = True
        self.detail_label.configure(text="已重新就绪，请放入下一个工件。")

    def save_frame(self) -> None:
        if self.last_frame is None:
            return
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        target = CAPTURE_DIR / f"dashboard_{self.mode.lower().replace(' ', '_')}_{datetime_now()}.jpg"
        cv2.imwrite(str(target), self.last_frame)
        self.detail_label.configure(text=f"已保存：{target.name}")

    def export_report(self) -> None:
        json_path, html_path = self.logger.export_report()
        pdf_path = self.logger.session_dir / "report.pdf"
        pdf_text = f"\nPDF: {pdf_path.name}" if pdf_path.exists() else ""
        messagebox.showinfo("报告已导出", f"JSON：{json_path.name}\nHTML：{html_path.name}{pdf_text}\n文件夹：{self.logger.session_dir}")

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
        if self.serial.connected:
            serial_state = "STM32：已连接"
        elif self.serial.port:
            serial_state = f"STM32：未连接（{self.serial.port}）"
        else:
            serial_state = "STM32：未配置串口"
        self.connection_label.configure(text=serial_state)
        self.stats_label.configure(
            text=(
                f"检测总数：{self.logger.total_count}\n"
                f"合格：{self.logger.pass_count}\n"
                f"不合格：{self.logger.fail_count}\n"
                f"合格率：{self.logger.yield_rate:.1f}%"
            )
        )
        if self.last_result is None:
            return
        result = self.last_result
        color = (50, 180, 50) if result.passed else (20, 20, 235)
        if result.object_contour is not None:
            cv2.drawContours(frame, [result.object_contour], -1, color, 2)
        if result.defect_area > 0:
            frame[result.defect_mask > 0] = (0, 0, 255)
        cv2.putText(frame, result.message, (25, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
        if result.message in {"NO CAP", "CAP TOO SMALL"}:
            verdict = "等待工件"
            verdict_color = "#fbbf24"
            state = "请将瓶盖放在黑色检测区中央，并保持镜头与光照位置不变。"
        else:
            verdict = "合格" if result.passed else "不合格"
            verdict_color = "#4ade80" if result.passed else "#fb7185"
            state = "检测结果已发送，请移走当前工件后继续。" if not self.inspection_armed else "请放入下一个工件。"
        self.verdict_label.configure(text=verdict, fg=verdict_color)
        self.detail_label.configure(text=f"{chinese_result(result.message)}\n{state}")

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
