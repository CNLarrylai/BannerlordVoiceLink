@echo off
rem Build the VoiceLink companion mod and install it into the game Modules folder.
rem Pure ASCII on purpose (cmd mangles UTF-8 batch files).
setlocal
set "GAME=C:\SteamLibraryforstream\steamapps\common\Mount & Blade II Bannerlord"
set "SRC=%~dp0BannerlordVoiceLink"
set "DST=%GAME%\Modules\BannerlordVoiceLink"

echo [1/3] Building mod...
dotnet build -c Release "%SRC%" || goto :fail

echo [2/3] Installing to game Modules...
if not exist "%DST%\bin\Win64_Shipping_Client" mkdir "%DST%\bin\Win64_Shipping_Client"
copy /Y "%SRC%\SubModule.xml" "%DST%\" >nul || goto :fail
copy /Y "%SRC%\bin\Release\BannerlordVoiceLink.dll" "%DST%\bin\Win64_Shipping_Client\" >nul || goto :fail

echo [3/3] Done. Enable "Bannerlord Voice Link" in the game launcher Mods tab.
exit /b 0

:fail
echo BUILD OR COPY FAILED.
exit /b 1
