@echo off
REM ============================================================
REM VDP Program Monitor Launcher (HackerOne + Intigriti)
REM Double-click this file to start the monitor.
REM Closing this window WILL stop the monitor -- it does not
REM run invisibly in the background.
REM ============================================================

REM --- EDIT THIS LINE WITH YOUR REAL H1 CREDENTIALS ---
REM Intigriti needs no token -- its part of the script works automatically.
set H1_USERNAME=malikdishan
set H1_API_TOKEN=your_real_token_here

REM Change this if the script isn't in the same folder as this .bat
cd /d "%~dp0"

echo Starting VDP Program Monitor (HackerOne + Intigriti)...
echo Do not close this window while you want it running.
echo.

python program_monitor.py

echo.
echo Monitor stopped. Press any key to close this window.
pause >nul
