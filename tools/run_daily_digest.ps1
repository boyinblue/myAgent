$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$digestScript = Join-Path $projectRoot 'content-crawler\run_anniversary_digest.py'
$stateDirectory = Join-Path $env:LOCALAPPDATA 'myAgent\daily_digest'
$statePath = Join-Path $stateDirectory 'last_successful_run.txt'
$logPath = Join-Path $stateDirectory 'daily_digest.log'
$today = Get-Date -Format 'yyyy-MM-dd'

if (-not (Test-Path $stateDirectory)) {
    New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
}

if (Test-Path $statePath) {
    $lastSuccessfulRun = (Get-Content -Path $statePath -Raw).Trim()
    if ($lastSuccessfulRun -eq $today) {
        Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Already sent today; skipping."
        exit 0
    }
}

if (-not (Test-Path $pythonPath)) {
    throw "Python virtual environment not found: $pythonPath"
}
if (-not (Test-Path $digestScript)) {
    throw "Digest script not found: $digestScript"
}

Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Starting anniversary digest."
$previousErrorActionPreference = $ErrorActionPreference
$env:PYTHONIOENCODING = 'utf-8'
try {
    $ErrorActionPreference = 'Continue'
    $output = & $pythonPath $digestScript 2>&1
    $pythonExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if ($output) {
    $output | Out-File -FilePath $logPath -Append -Encoding utf8
}

if ($pythonExitCode -ne 0) {
    Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Digest failed with exit code $pythonExitCode."
    exit $pythonExitCode
}

Set-Content -Path $statePath -Value $today -Encoding ascii
Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Digest completed successfully."
