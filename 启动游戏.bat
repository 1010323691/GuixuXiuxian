@echo off
rem One-click start for GuixuXiuxian: starts the local server and opens the browser.
rem Extra arguments are passed through, e.g.  --port 8010
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3.11+ was not found. Install it from https://www.python.org/downloads/ and retry.
  pause
  exit /b 1
)
%PY% scripts\launch.py %*
if errorlevel 1 pause
