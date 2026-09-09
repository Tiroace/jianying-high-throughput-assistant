@echo off
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0app\cli.py" diagnose
pause
