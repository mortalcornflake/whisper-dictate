@echo off
rem Launch Whisper Dictate from this repo's virtual environment, logging to the
rem user profile. Called by start-dictate.vbs so it runs without a console window.
cd /d "%~dp0"
set PYTHONUTF8=1
"%~dp0venv\Scripts\python.exe" dictate.py >> "%USERPROFILE%\whisper-dictate.log" 2>&1
