from __future__ import annotations

from typing import Optional


class SerialController:
    """向 STM32 发送简单的 OK/NG 命令；未配置串口时自动降级为空操作。"""

    def __init__(self, port: str = "", baudrate: int = 115200) -> None:
        self._serial: Optional[object] = None
        self.port = port
        self.last_error = ""
        if port:
            self.connect(port, baudrate)

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """Connect without blocking the vision interface if COM is unavailable."""
        self.close()
        self.port = port
        self.last_error = ""
        try:
            import serial

            self._serial = serial.Serial(port, baudrate=baudrate, timeout=0.3)
        except Exception as error:  # Port may be absent, occupied, or changing.
            self._serial = None
            self.last_error = str(error)
            return False
        return True

    @property
    def connected(self) -> bool:
        return self._serial is not None and bool(getattr(self._serial, "is_open", False))

    def send_result(self, passed: bool) -> None:
        if not self.connected:
            return
        message = b"OK\n" if passed else b"NG\n"
        self._serial.write(message)

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None
