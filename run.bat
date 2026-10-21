@echo off
REM Desktop app mode: Flask + pywebview window
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" app.py
if errorlevel 1 pause
