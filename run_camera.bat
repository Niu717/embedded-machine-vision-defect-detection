@echo off
set "PYTHON_EXE=C:\Users\nzr\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Python not found: %PYTHON_EXE%
  pause
  exit /b 1
)
cd /d "%~dp0pc_app"
"%PYTHON_EXE%" main.py --camera 1
pause
