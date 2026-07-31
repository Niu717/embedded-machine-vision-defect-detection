@echo off
setlocal
set "PYTHON_EXE=C:\Users\nzr\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Python not found: %PYTHON_EXE%
  pause
  exit /b 1
)

set /p "STM32_PORT=Enter USB-TTL COM port (for example COM3): "
if "%STM32_PORT%"=="" (
  echo No COM port entered.
  pause
  exit /b 1
)

cd /d "%~dp0pc_app"
"%PYTHON_EXE%" main.py --camera 1 --port %STM32_PORT%
pause
