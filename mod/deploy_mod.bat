@echo off
rem Thin wrapper: build + deploy the mod DLL with an auto version stamp.
rem (Version bumping lives in tools\build_workshop.py so it can never be
rem  forgotten - the launcher Mods page always shows which build you run.)
cd /d "%~dp0.."
".venv\Scripts\python.exe" tools\build_workshop.py --skip-exe
