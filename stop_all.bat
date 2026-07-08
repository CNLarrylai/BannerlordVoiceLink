@echo off
rem Force-stop every voice-app process (packaged exe + source python running app.py).
rem Use when you suspect a background instance lingered after closing a window.
echo Stopping all Bannerlord Voice processes...
taskkill /F /T /IM BannerlordVoice.exe >nul 2>&1
rem Source-version: python/pythonw running app.py (filter by command line so we
rem don't kill unrelated python).
for /f "tokens=2 delims==" %%P in ('wmic process where "name='pythonw.exe' or name='python.exe'" get ProcessId^,CommandLine /format:list 2^>nul ^| find "app.py"') do echo.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | Where-Object { $_.CommandLine -match 'app\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo Done. All voice processes stopped.
timeout /t 2 >nul
