@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run SETUP-BACKEND.cmd first.
  pause
  exit /b 1
)
echo The launcher prints the actual address. Keep the server window open.
".venv\Scripts\python.exe" scripts\serve_backend.py
pause
