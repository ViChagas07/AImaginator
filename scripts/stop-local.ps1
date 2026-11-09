[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root 'logs'
$PidFile = Join-Path $LogDir 'local-pids.json'

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "Nada para parar: $PidFile nao existe."
    exit 0
}

try {
    $state = Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json
} catch {
    Write-Warning "PID file invalido: $PidFile"
    exit 1
}

function Stop-RecordedWrapper($Entry, [string]$Label) {
    if ($null -eq $Entry -or -not $Entry.wrapper_pid) {
        return
    }
    $pidToStop = [int]$Entry.wrapper_pid
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pidToStop" -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-Host ("{0}: PID {1} ja nao existe." -f $Label, $pidToStop)
        return
    }
    if ($Entry.wrapper_script -and $proc.CommandLine -notlike "*$($Entry.wrapper_script)*") {
        Write-Warning ("{0}: PID {1} nao corresponde ao script gravado; ignorando." -f $Label, $pidToStop)
        return
    }
    Write-Host ("{0}: encerrando PID {1} e filhos..." -f $Label, $pidToStop)
    & taskkill.exe /PID $pidToStop /T /F 2>&1 | Out-Null
}

Stop-RecordedWrapper $state.worker 'Worker host'
Stop-RecordedWrapper $state.web 'Frontend'

foreach ($wrapper in @($state.worker.wrapper_script, $state.web.wrapper_script)) {
    if ($wrapper -and (Test-Path -LiteralPath $wrapper)) {
        Remove-Item -LiteralPath $wrapper -Force -ErrorAction SilentlyContinue
    }
}
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue

Write-Host "Processos iniciados pelo dev-local.ps1 foram encerrados."
