param([switch]$Live)
$ErrorActionPreference = 'Stop'
$mvpRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
function Invoke-MvpCheck([string]$Program, [string[]]$CheckArguments) {
    & $Program @CheckArguments
    if ($LASTEXITCODE -ne 0) { throw "Verification failed: $Program $($CheckArguments -join ' ')" }
}
Push-Location $mvpRoot
try {
    Invoke-MvpCheck docker @('exec', 'paulibot_web', 'python', '-B', 'manage.py', 'check')
    Invoke-MvpCheck docker @('exec', 'paulibot_web', 'python', '-B', 'manage.py', 'makemigrations', '--check', '--dry-run')
    Invoke-MvpCheck docker @('exec', 'paulibot_web', 'python', '-B', 'manage.py', 'migrate', '--check')
    Invoke-MvpCheck docker @('exec', 'paulibot_web', 'python', '-B', 'manage.py', 'test', 'chatbot', '--keepdb', '--verbosity', '0')
    Invoke-MvpCheck docker @('exec', 'paulibot_web', 'python', '-B', 'manage.py', 'audit_knowledge', '--strict')
    Invoke-MvpCheck docker @('exec', 'paulibot_web', 'python', '-B', 'manage.py', 'prepare_embedding_model')
    Invoke-MvpCheck docker @('exec', 'paulibot_web', 'python', '-m', 'pip', 'check')
    Push-Location (Join-Path $mvpRoot 'frontend')
    try {
        Invoke-MvpCheck npm.cmd @('test')
        Invoke-MvpCheck npm.cmd @('run', 'build')
    } finally { Pop-Location }
    if ($Live) {
        $mvpState = Invoke-RestMethod 'http://127.0.0.1:8080/api/health/ready' -TimeoutSec 5
        if (-not $mvpState.ready -or -not $mvpState.index_complete) { throw 'Service/knowledge is not ready.' }
        Invoke-MvpCheck docker @('exec', 'paulibot_web', 'python', '-B', 'scripts/benchmark_mvp.py', '--phase', 'after')
    }
} finally { Pop-Location }
