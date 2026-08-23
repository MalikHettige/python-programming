@echo off
REM ============================================================
REM H1 Program Monitor Launcher
REM Double-click this file to start the monitor.
REM Closing this window WILL stop the monitor -- it does not
REM run invisibly in the background.
REM ============================================================

REM --- EDIT THESE TWO LINES WITH YOUR REAL CREDENTIALS ---
set H1_USERNAME='Username'
set H1_API_TOKEN='token'

REM Change this if the script isn't in the same folder as this .bat
cd /d "%~dp0"

echo Starting H1 Program Monitor...
echo Do not close this window while you want it running.
echo.

python h1_program_monitor.py

echo.
echo Monitor stopped. Press any key to close this window.
pause >nul