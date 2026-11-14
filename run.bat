@echo off
cd /d "%~dp0"
title Geopolitics AI
python -c "import openai" >nul 2>&1
if errorlevel 1 (
  echo First run: installing required packages, please wait...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Could not install packages. Check your internet connection and that Python 3.9+ is installed.
    pause
    exit /b 1
  )
)
echo Starting Geopolitics AI... Close this window to stop the game. Press F11 in the browser for full screen.
python server.py
if errorlevel 1 (
  echo.
  echo Failed to start. Check that Python 3.9 or newer is installed.
  pause
)
