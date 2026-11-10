# Stop every copy of the app still listening on the app port, so a new start
# is the only one answering. Werkzeug lets several servers bind the same port on
# Windows, and the browser then gets whichever old copy answers first.
# Only Python processes are stopped; the .venv python.exe is a launcher, so its
# parent is stopped too. A copy that is still starting may not be listening yet,
# so the port is checked again until no Python process holds it.
param([int]$Port = 5020)

for ($pass = 0; $pass -lt 5; $pass++) {
    $owners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    $stopped = 0
    foreach ($id in $owners) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$id"
        if (-not $proc -or $proc.Name -notlike 'python*') { continue }
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)"
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        if ($parent -and $parent.Name -like 'python*') {
            Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Write-Host "[PosRestructure] stopped an old copy of the app (PID $id)"
        $stopped++
    }
    if ($stopped -eq 0) { break }
    Start-Sleep -Milliseconds 500
}
