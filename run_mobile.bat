@echo off
REM Starts GeoLab so a phone on the SAME Wi-Fi can open it.
REM Double-click this file, then type the address it prints
REM ("On your phone (same Wi-Fi) open: http://192.168.x.x:5000/") into the phone's browser.
REM If Windows asks whether to allow Python through the firewall, allow it on "Private networks".
cd /d "%~dp0"
set FLASK_HOST=0.0.0.0
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
) else (
  python app.py
)
pause
