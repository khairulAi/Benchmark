@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  call START-BENCHMARK.cmd
  exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve.ps1"
pause
