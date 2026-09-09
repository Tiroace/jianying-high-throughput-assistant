@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" call "安装环境.cmd"
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1

".venv\Scripts\pyinstaller.exe" --noconfirm --clean --distpath dist --workpath build packaging\assistant.spec
if errorlevel 1 exit /b 1

copy /y "packaging\使用说明.txt" "dist\剪映高产剪辑助手\使用说明.txt" >nul
copy /y "LICENSE" "dist\剪映高产剪辑助手\LICENSE.txt" >nul
mkdir "dist\剪映高产剪辑助手\素材库" 2>nul
mkdir "dist\剪映高产剪辑助手\文案" 2>nul
mkdir "dist\剪映高产剪辑助手\任务" 2>nul
mkdir "dist\剪映高产剪辑助手\日志" 2>nul

tar.exe -a -c -f "dist\剪映高产剪辑助手_Windows_x64.zip" -C dist "剪映高产剪辑助手"
if errorlevel 1 exit /b 1

echo Release created in dist.
