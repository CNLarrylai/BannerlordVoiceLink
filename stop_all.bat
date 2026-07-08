@echo off
rem Force-stop every voice-app process, INCLUDING admin-elevated ones.
rem The packaged app runs as administrator (for key injection), so a normal
rem shell can't kill it. This script self-elevates (one UAC prompt) so it can.

rem --- self-elevate: relaunch as admin if not already ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator rights to stop admin-level processes...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Stopping all Bannerlord Voice processes...
taskkill /F /T /IM BannerlordVoice.exe >nul 2>&1
rem Source-version: python/pythonw running app.py (filter by command line).
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | Where-Object { $_.CommandLine -match 'app\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo Done. All voice processes stopped.
timeout /t 3 >nul
