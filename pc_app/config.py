from dataclasses import dataclass


@dataclass
class DetectorConfig:
    """可在现场调试时修改的基础阈值。"""

    min_object_area: int = 20_000
    min_defect_area: int = 80
    defect_ratio_limit: float = 0.008
    blur_kernel: int = 5
    threshold_value: int = 95


@dataclass
class AppConfig:
    camera_index: int = 0
    width: int = 1920
    height: int = 1080
    serial_port: str = ""
    baudrate: int = 115200
