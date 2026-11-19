$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path $PSScriptRoot -Parent
$runnerScript = Join-Path $PSScriptRoot 'run_daily_digest.ps1'
if (-not (Test-Path $runnerScript)) {
    throw "Daily digest runner not found: $runnerScript"
}

$taskName = 'myAgent_DailyDigest'
$userName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runnerScript`"" `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userName
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal `
    -UserId $userName `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Description 'myAgent anniversary digest once per local calendar day after login' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "Registered $taskName. It runs at the next login, at most once per day."
Write-Host "To run it now: Start-ScheduledTask -TaskName '$taskName'"
Write-Host "To remove it: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
