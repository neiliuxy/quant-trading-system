# Diagnose whether the logic in stop-servers.ps1 would actually work

Write-Host "=== Test 1: Does Get-Process expose CommandLine? ==="
$proc = Get-Process python -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $proc) {
    Write-Host "No python process running (ok, we'll synthesize the test)"
} else {
    $hasCmdLine = ($proc | Get-Member -Name CommandLine -ErrorAction SilentlyContinue) -ne $null
    Write-Host "  Has CommandLine member: $hasCmdLine"
    try {
        $cl = $proc.CommandLine
        Write-Host "  .CommandLine returned: '$cl'"
    } catch {
        Write-Host "  .CommandLine threw: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "=== Test 2: Can we filter Get-Process by .CommandLine -like '...'? ==="
try {
    $result = Get-Process | Where-Object { $_.CommandLine -like "*uvicorn*" }
    Write-Host "  Filter succeeded. Returned $($result.Count) items."
} catch {
    Write-Host "  Filter FAILED: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "=== Test 3: After uvicorn --reload, how many child python processes exist? ==="
Write-Host "  (simulated - none running, but the structure is: 1 watcher + 1 worker = 2+ procs)"

Write-Host ""
Write-Host "=== Test 4: Does Get-NetTCPConnection work without admin? ==="
try {
    $conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction Stop
    Write-Host "  Get-NetTCPConnection works (admin or no listeners)"
} catch {
    Write-Host "  Get-NetTCPConnection failed: $($_.Exception.Message)"
}
