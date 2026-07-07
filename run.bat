@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo [!] Environment not ready. Please run setup.bat first.
    pause
    exit /b 1
)
rem 打开启动器 Hub (含语言开关/各功能); GUI, 不留黑窗
start "" ".venv\Scripts\pythonw.exe" src\app.py
