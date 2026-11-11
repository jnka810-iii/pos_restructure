@echo off
REM Browser mode: start local Flask server and open the default web browser
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

REM Stop copies left running from an earlier start, so only this one answers
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_app.ps1"

echo [PosRestructure] Opening http://127.0.0.1:5020  (close this window to stop)
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:5020"
"%PY%" -c "import app, sys; sys.exit(app.serve(port=app.PORT))"
pause
