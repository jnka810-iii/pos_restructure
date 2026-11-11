@echo off
REM Server mode: Flask only, reachable from other machines on the LAN
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "PORT=5020"
set "RULE=PosRestructure-%PORT%"

REM Stop copies left running from an earlier start, so only this one answers
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_app.ps1" -Port %PORT%

REM Windows Firewall blocks other machines by default. Allow this port once, but
REM only from machines on the same subnet, since the app has no login. This also
REM works when Windows treats the network as Public. Adding the rule needs
REM administrator rights, so Windows asks for permission.
netsh advfirewall firewall show rule name=%RULE% >nul 2>&1
if not errorlevel 1 goto firewall_ok
echo [PosRestructure] Allowing port %PORT% through Windows Firewall - please approve the administrator prompt
powershell -NoProfile -Command "Start-Process netsh -Verb RunAs -Wait -ArgumentList 'advfirewall firewall add rule name=%RULE% dir=in action=allow protocol=TCP localport=%PORT% profile=any remoteip=localsubnet'"
netsh advfirewall firewall show rule name=%RULE% >nul 2>&1
if not errorlevel 1 goto firewall_ok
echo [PosRestructure] WARNING: the firewall rule was not added, so other machines cannot connect yet
:firewall_ok

echo.
echo [PosRestructure] Server running on port %PORT%  (Ctrl+C to stop)
echo [PosRestructure] Other machines on the LAN open:
REM Only networks with a gateway, so virtual adapters (WSL, Hyper-V, VirtualBox) are left out
powershell -NoProfile -Command "Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | ForEach-Object { '    http://' + $_.IPv4Address[0].IPAddress + ':%PORT%   (' + $_.InterfaceAlias + ')' }"
REM A real network port with an address but no cable shows nothing above, so say so
powershell -NoProfile -Command "Get-NetAdapter | Where-Object { $_.HardwareInterface -and $_.Status -ne 'Up' } | ForEach-Object { $ip = (Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254.*' }).IPAddress; if ($ip) { '[PosRestructure] WARNING: ' + $_.Name + ' (' + ($ip -join ', ') + ') is not connected - plug in the LAN cable to serve that network' } }"
echo [PosRestructure] This machine opens:  http://127.0.0.1:%PORT%  (log in here too)
echo.
REM Binding every interface makes app.serve require a login from everyone, this
REM machine included, and refuse to start while no account exists.
"%PY%" -c "import app, sys; sys.exit(app.serve(host='0.0.0.0', port=app.PORT))"
pause
