@echo off
setlocal
title ZNAK ORIENT

cd /d "%~dp0"

where python.exe >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer was not found on PATH.
  echo Install Python, reopen this folder, and run this file again.
  pause
  exit /b 1
)

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Milliseconds 1200; Start-Process 'http://127.0.0.1:8765/'"

echo Starting ZNAK ORIENT at http://127.0.0.1:8765/
echo Keep this window open. Press Ctrl+C to stop the local server.
echo.
python.exe -m znak_orient serve --host 127.0.0.1 --port 8765

echo.
echo The server stopped or could not start.
pause
