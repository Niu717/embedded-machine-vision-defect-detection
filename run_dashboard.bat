@echo off
cd /d "%~dp0pc_app"
"C:\Users\nzr\AppData\Local\Programs\Python\Python313\python.exe" vision_dashboard.py --camera 1 --port COM3
pause
