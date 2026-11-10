@echo off
REM Desktop app mode: Flask + pywebview window
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

REM Stop copies left running from an earlier start, so only this one answers
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_app.ps1"

"%PY%" app.py
if errorlevel 1 pause
