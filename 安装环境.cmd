@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_BOOTSTRAP="
where py.exe >nul 2>nul && set "PYTHON_BOOTSTRAP=py -3.12"
if not defined PYTHON_BOOTSTRAP where python.exe >nul 2>nul && set "PYTHON_BOOTSTRAP=python"
if not defined PYTHON_BOOTSTRAP goto :no_python
if not exist "%~dp0.venv\Scripts\python.exe" %PYTHON_BOOTSTRAP% -m venv "%~dp0.venv"
if errorlevel 1 goto :failed
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :failed
echo Installation completed.
pause
exit /b 0

:no_python
echo Python 3.11 or 3.12 was not found. Download the portable Release instead.
pause
exit /b 1

:failed
echo Installation failed. Check the messages above.
pause
exit /b 1
