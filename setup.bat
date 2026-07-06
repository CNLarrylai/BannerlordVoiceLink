@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Creating virtual environment ===
py -3 -m venv .venv
echo === Upgrading pip ===
".venv\Scripts\python.exe" -m pip install --upgrade pip
echo === Installing dependencies (incl. CUDA libs, large, please wait) ===
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo === Done! Use run.bat to start ===
pause
