@echo off
REM Server mode: Flask only, reachable from other machines on the LAN (port 5050)
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [PosRestructure] Server running at http://0.0.0.0:5050  (Ctrl+C to stop)
"%PY%" -c "import app; app.init_db(); app.app.run(host='0.0.0.0', port=app.PORT, debug=False)"
pause
