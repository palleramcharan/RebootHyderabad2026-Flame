Write-Host "============================================"
Write-Host "  Generate Static Audit Dashboard"
Write-Host "============================================"
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

.\.venv\Scripts\python 08-Dashboard/generate_report.py

Write-Host ""
Write-Host "Open 08-Dashboard/dashboard.html in your browser."
