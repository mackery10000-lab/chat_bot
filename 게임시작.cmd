@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 13-Fri
if not exist "runtime\python.exe" (
  echo The runtime folder is missing.
  echo Extract the entire distribution ZIP before running this file.
  pause
  exit /b 1
)
"runtime\python.exe" -I -B -X utf8 "launch_game.py" %*
if errorlevel 1 pause
