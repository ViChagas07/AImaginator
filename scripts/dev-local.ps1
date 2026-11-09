[CmdletBinding()]
param(
    [switch]$Dev,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$LogDir = Join-Path $Root 'logs'
$PidFile = Join-Path $LogDir 'local-pids.json'
$ComposeFile = Join-Path $Root 'infra\docker\docker-compose.yml'
$EnvFile = Join-Path $Root '.env.development'
$WorkerEnv = Join-Path $Root '.env.worker'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$WebDir = Join-Path $Root 'apps\web'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Get-ComposeArgs {
    return @('-f', $ComposeFile, '--env-file', $EnvFile)
}

function Get-FreeRamGb {
    if (Test-Path -LiteralPath $Python) {
        try {
            $bytes = & $Python -c "import psutil; print(psutil.virtual_memory().available)" 2>$null
            if ($bytes) {
                return [math]::Round(([int64]$bytes) / 1GB, 2)
            }
        } catch {
            # fallback abaixo
        }
    }
    $os = Get-CimInstance Win32_OperatingSystem
    return [math]::Round(($os.FreePhysicalMemory * 1KB) / 1GB, 2)
}

function Test-PortFree([int]$Port) {
    return -not (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Test-ExistingInstance {
    if (-not (Test-Path -LiteralPath $PidFile)) {
        return $false
    }
    try {
        $prev = Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json
    } catch {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        return $false
    }
    foreach ($entry in @($prev.worker, $prev.web)) {
        if ($null -eq $entry -or -not $entry.wrapper_pid) {
            continue
        }
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.wrapper_pid)" -ErrorAction SilentlyContinue
        if ($proc -and $entry.wrapper_script -and $proc.CommandLine -like "*$($entry.wrapper_script)*") {
            return $true
        }
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    return $false
}

if (Test-ExistingInstance) {
    throw "Ja existe uma instancia local rodando. Rode scripts\stop-local.ps1 primeiro."
}

if (-not (Test-Path -LiteralPath $WorkerEnv)) {
    throw "Arquivo .env.worker nao encontrado. Copie .env.development e configure IMAGE_ENGINE=sdcpp e SDCPP_*."
}
$workerEnvText = Get-Content -LiteralPath $WorkerEnv -Raw
if ($workerEnvText -notmatch '(?m)^IMAGE_ENGINE=sdcpp\s*$') {
    throw ".env.worker nao tem IMAGE_ENGINE=sdcpp."
}
$guardMb = 6000
if ($workerEnvText -match '(?m)^MIN_FREE_RAM_MB=(\d+)\s*$') {
    $guardMb = [int]$Matches[1]
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python do .venv nao encontrado: $Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $WebDir 'node_modules'))) {
    throw "apps/web/node_modules nao encontrado. Rode npm install em apps/web."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm nao encontrado no PATH."
}

$ramGb = Get-FreeRamGb
Write-Host ("RAM livre: {0} GB (guard do worker: {1} MB)" -f $ramGb, $guardMb)
if (($ramGb * 1024) -lt $guardMb) {
    Write-Warning ("RAM livre abaixo de {0} MB. O worker vai recusar geracoes; feche apps pesados. A guarda NAO sera alterada." -f $guardMb)
    if (-not $Force) {
        $answer = Read-Host "Continuar mesmo assim? [s/N]"
        if ($answer -notmatch '^[sS]') {
            throw "Cancelado pelo usuario."
        }
    }
}

$composeArgs = Get-ComposeArgs
foreach ($svc in @('api', 'postgres', 'redis', 'rabbitmq', 'minio')) {
    $id = & docker compose @composeArgs ps -q $svc 2>$null
    if (-not $id) {
        throw "Servico '$svc' sem container. Suba a stack com: docker compose -f infra/docker/docker-compose.yml --env-file .env.development up -d"
    }
    $id = ($id | Select-Object -First 1).Trim()
    $status = (& docker inspect -f '{{.State.Status}}' $id 2>$null).Trim()
    $health = (& docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $id 2>$null).Trim()
    if ($status -ne 'running' -or $health -ne 'healthy') {
        throw "Servico '$svc' nao esta healthy (status=$status, health=$health)."
    }
    Write-Host ("{0}: {1}/{2}" -f $svc, $status, $health)
}

$workerContainerId = & docker compose @composeArgs ps -q worker 2>$null
if ($workerContainerId) {
    $workerContainerId = ($workerContainerId | Select-Object -First 1).Trim()
    $running = (& docker inspect -f '{{.State.Running}}' $workerContainerId 2>$null).Trim()
    if ($running -eq 'true') {
        Write-Host "Parando aimaginator-worker-1 para evitar dois consumidores..."
        & docker compose @composeArgs stop worker | Out-Null
    }
}
Write-Host "Container worker: parado."

$port = $null
foreach ($candidate in @(3000, 3001)) {
    if (Test-PortFree $candidate) {
        $port = $candidate
        break
    }
}
if (-not $port) {
    throw "Portas 3000 e 3001 ocupadas. O CORS de dev so permite essas portas; libere uma delas."
}

$runId = [guid]::NewGuid().ToString('N').Substring(0, 8)
$workerWrapper = Join-Path $LogDir ("run-worker-$runId.ps1")
$webWrapper = Join-Path $LogDir ("run-web-$runId.ps1")
$workerLog = Join-Path $LogDir 'worker.log'
$webLog = Join-Path $LogDir 'web.log'

$rootQ = $Root.Replace("'", "''")
$pythonQ = $Python.Replace("'", "''")
$workerLogQ = $workerLog.Replace("'", "''")
$webDirQ = $WebDir.Replace("'", "''")
$webLogQ = $webLog.Replace("'", "''")
$portText = [string]$port

$workerScript = @"
`$ErrorActionPreference = 'Continue'
`$Host.UI.RawUI.WindowTitle = 'AImaginator Worker (host)'
Set-Location -LiteralPath '$rootQ'
`$env:ENV_FILE = '.env.worker'
& '$pythonQ' -m celery -A workers.celery_app.celery:celery_app worker --loglevel=info --queues=generation.standard --pool=solo --concurrency=1 --max-tasks-per-child=1 *>> '$workerLogQ'
"@
Set-Content -LiteralPath $workerWrapper -Value $workerScript -Encoding ASCII

if ($Dev) {
    $webScript = @"
`$ErrorActionPreference = 'Continue'
`$Host.UI.RawUI.WindowTitle = 'AImaginator Web ($portText)'
Set-Location -LiteralPath '$webDirQ'
`$env:NEXT_TELEMETRY_DISABLED = '1'
npm run dev -- -p $portText *>> '$webLogQ'
"@
    $mode = 'dev'
} else {
    $webScript = @"
`$ErrorActionPreference = 'Continue'
`$Host.UI.RawUI.WindowTitle = 'AImaginator Web ($portText)'
Set-Location -LiteralPath '$webDirQ'
`$env:NEXT_TELEMETRY_DISABLED = '1'
npm run build *>> '$webLogQ'
if (`$LASTEXITCODE -ne 0) { Write-Host 'Build falhou. Veja logs\web.log ou rode com -Dev.'; return }
npm run start -- -p $portText *>> '$webLogQ'
"@
    $mode = 'build+start'
}
Set-Content -LiteralPath $webWrapper -Value $webScript -Encoding ASCII

$workerProc = Start-Process -FilePath 'powershell.exe' -ArgumentList "-NoProfile -NoExit -ExecutionPolicy Bypass -File `"$workerWrapper`"" -WorkingDirectory $Root -PassThru
$webProc = Start-Process -FilePath 'powershell.exe' -ArgumentList "-NoProfile -NoExit -ExecutionPolicy Bypass -File `"$webWrapper`"" -WorkingDirectory $Root -PassThru

$state = [ordered]@{
    run_id = $runId
    started_at = (Get-Date).ToString('o')
    worker = [ordered]@{
        wrapper_pid = $workerProc.Id
        wrapper_script = $workerWrapper
        log = $workerLog
    }
    web = [ordered]@{
        wrapper_pid = $webProc.Id
        wrapper_script = $webWrapper
        log = $webLog
        port = $port
        mode = $mode
    }
}
$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $PidFile -Encoding UTF8

Write-Host ""
Write-Host ("Worker host: PID {0} (log: {1})" -f $workerProc.Id, $workerLog)
Write-Host ("Frontend: http://localhost:{0} [{1}] PID {2} (log: {3})" -f $port, $mode, $webProc.Id, $webLog)
Write-Host "Para parar: .\scripts\stop-local.ps1"
