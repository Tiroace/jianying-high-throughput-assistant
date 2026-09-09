@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Runtime is missing. Run install.cmd first.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app\gui.py"
