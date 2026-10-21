@echo off
REM Browser mode: start local Flask server and open the default web browser
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [PosRestructure] Opening http://127.0.0.1:5050  (close this window to stop)
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:5050"
"%PY%" -c "import app; app.init_db(); app.app.run(host='127.0.0.1', port=app.PORT, debug=False)"
pause
