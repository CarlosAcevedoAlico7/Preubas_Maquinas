$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "iniciar_dashboard.cmd"
$taskName = "Dashboard Energia Varex"
$user = "$env:USERDOMAIN\$env:USERNAME"
$commandPrompt = Join-Path $env:SystemRoot "System32\cmd.exe"

if (-not (Test-Path (Join-Path $projectRoot ".venv\Scripts\python.exe"))) {
    throw "No se encontró .venv. Cree el entorno e instale requirements.txt antes de continuar."
}

$action = New-ScheduledTaskAction `
    -Execute $commandPrompt `
    -Argument ('/d /c ""' + $launcher + '""') `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Dashboard Streamlit energético disponible en la red local." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $taskName
Write-Output "Tarea '$taskName' instalada e iniciada."
Write-Output "Panel local: http://localhost:8501"
