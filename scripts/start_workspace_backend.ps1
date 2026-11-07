param(
    [Parameter(Mandatory = $true)]
    [string]$EnvFile,
    [ValidateSet('true', 'false')]
    [string]$DjangoDebug = 'true'
)

# Reuse an existing environment file in place. Never print or copy credentials.
# Only the web service is recreated; the PostgreSQL service/volume is preserved.
$taskPreviousDebug = [Environment]::GetEnvironmentVariable('PAULA_DJANGO_DEBUG', 'Process')
try {
    $env:PAULA_DJANGO_DEBUG = $DjangoDebug
    $taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $taskEnvFile = (Resolve-Path -LiteralPath $EnvFile -ErrorAction Stop).Path
    $taskComposeFile = Join-Path $taskRoot 'docker-compose.yml'
    $taskComposeArgs = @('compose', '--env-file', $taskEnvFile, '--project-name', 'paulibot', '--file', $taskComposeFile)

    $taskConfigText = & docker @taskComposeArgs config --format json 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw 'Cannot resolve Compose configuration using the supplied environment file.'
    }
    $taskConfig = ($taskConfigText -join "`n") | ConvertFrom-Json
    if ($taskConfig.services.web.environment.USE_POSTGRES -ne 'true') {
        throw 'Refusing to start: PostgreSQL must remain enabled.'
    }
    if ($taskConfig.services.web.environment.DEBUG -notmatch '^(true|false)$') {
        throw 'Refusing to start: Django DEBUG must be true or false.'
    }
    $taskCodeMount = $taskConfig.services.web.volumes | Where-Object target -eq '/app'
    if ([IO.Path]::GetFullPath($taskCodeMount.source) -ine [IO.Path]::GetFullPath($taskRoot)) {
        throw 'Refusing to start: the web code mount does not match this workspace.'
    }

    $taskPostgresBefore = & docker inspect paulibot_postgres --format '{{.Id}}'
    if ($LASTEXITCODE -ne 0) {
        throw 'The existing PostgreSQL container must be available; this script does not replace it.'
    }

    Write-Host "Activating web service from $taskRoot"
    & docker @taskComposeArgs up -d --no-deps --no-build web
    if ($LASTEXITCODE -ne 0) {
        throw 'Web service activation failed. PostgreSQL was not recreated.'
    }

    $taskPostgresAfter = & docker inspect paulibot_postgres --format '{{.Id}}'
    if (($taskPostgresBefore -join '') -ne ($taskPostgresAfter -join '')) {
        throw 'Unexpected PostgreSQL container change; inspect runtime before proceeding.'
    }
    $taskMountsText = & docker inspect paulibot_web --format '{{json .Mounts}}'
    $taskMounts = ($taskMountsText -join "`n") | ConvertFrom-Json
    $taskActiveMount = $taskMounts | Where-Object Destination -eq '/app'
    $taskActivePath = $taskActiveMount.Source
    # Docker Desktop may report either a Windows path or its Linux host-mount path.
    if ($taskActivePath -match '^/(?:run/desktop/mnt/host|host_mnt)/([a-zA-Z])/(.*)$') {
        $taskActivePath = "$($Matches[1]):/$($Matches[2])"
    }
    if ($taskActivePath.Replace('\', '/').TrimEnd('/') -ine $taskRoot.Replace('\', '/').TrimEnd('/')) {
        throw 'The running web service does not mount the intended workspace.'
    }
    Write-Host 'Workspace mount verified. PostgreSQL container preserved. Waiting for all semantic workers...'
    $taskReadinessTimer = [Diagnostics.Stopwatch]::StartNew()
    $taskSemanticReady = $false
    while ($taskReadinessTimer.Elapsed.TotalSeconds -lt 240) {
        try {
            $taskHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/health/ready' -TimeoutSec 2
            if ($taskHealth.ready -and $taskHealth.ready_workers -eq $taskHealth.expected_workers) {
                $taskSemanticReady = $true
                break
            }
        }
        catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $taskSemanticReady) {
        throw 'Web service did not reach all-worker semantic readiness. Inspect worker logs; PostgreSQL was preserved.'
    }
    Write-Host "All $($taskHealth.ready_workers) semantic workers ready. Backend: http://127.0.0.1:8080"
}
finally {
    [Environment]::SetEnvironmentVariable('PAULA_DJANGO_DEBUG', $taskPreviousDebug, 'Process')
}
