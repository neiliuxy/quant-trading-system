# Verify the critical bug: $_.CommandLine on Get-Process objects

Write-Host "=== Start a fake 'uvicorn-like' process to test filter ==="

# Launch a sleep that has 'uvicorn' in its name to simulate
$fake = Start-Process -FilePath "powershell" -ArgumentList "-NoProfile", "-Command", "Start-Sleep -Seconds 30; Write-Host 'fake uvicorn worker'" -PassThru -WindowStyle Hidden
Write-Host "Spawned fake process PID=$($fake.Id)"

Start-Sleep -Seconds 1

Write-Host ""
Write-Host "=== Now apply the exact filter from stop-servers.ps1 line 10 ==="
$matched = Get-Process | Where-Object { $_.CommandLine -like "*uvicorn*" }
Write-Host "  Filter result count: $($matched.Count)"
Write-Host "  (Expected 1 if filter works, 0 if CommandLine is null)"

Write-Host ""
Write-Host "=== Inspect a known process's actual members ==="
$p = Get-Process -Id $fake.Id
$members = $p | Get-Member | Select-Object -ExpandProperty Name
Write-Host "  Has 'CommandLine'? $(($members -contains 'CommandLine'))"
Write-Host "  Has 'Id'? $(($members -contains 'Id'))"
Write-Host "  Has 'ProcessName'? $(($members -contains 'ProcessName'))"

Write-Host ""
Write-Host "=== Try the only way to actually get CommandLine in PowerShell ==="
$cim = Get-CimInstance Win32_Process -Filter "ProcessId = $($fake.Id)"
Write-Host "  CIM CommandLine: $($cim.CommandLine)"

Write-Host ""
Write-Host "=== Cleanup ==="
Stop-Process -Id $fake.Id -Force -ErrorAction SilentlyContinue
Get-Process powershell | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "Done"
