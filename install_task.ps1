# Registers a Windows scheduled task that runs the monitor every N minutes.
# NOT needed during the development phase - run it once the script works manually.
# Usage (PowerShell):  .\install_task.ps1            -> install / update
#                      .\install_task.ps1 -Remove    -> uninstall
param(
    [int]$IntervalMinutes = 5,
    [string]$TaskName = "PP-UT-Livestream-Notification",
    [switch]$Remove
)

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $projectDir "ut_livestream_monitor.py"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task '$TaskName' removed."
    return
}

# pythonw.exe runs without a console window
$python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command python.exe).Source }

$action   = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $projectDir
$trigger  = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
            -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Task '$TaskName' registered: every $IntervalMinutes minute(s) using $python"
