param([Parameter(Mandatory=$true)][string]$Step)
$outDir = Join-Path $PSScriptRoot '..\artifacts\stage3'
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
& docker exec -e HF_HUB_DISABLE_PROGRESS_BARS=1 -e TQDM_DISABLE=1 paulibot_web python -B manage.py test chatbot --keepdb --noinput --verbosity 0 2>&1 | Out-File (Join-Path $outDir "$Step-backend.log") -Encoding utf8
$backendExit = $LASTEXITCODE
& npm.cmd test --prefix (Join-Path $PSScriptRoot '..\frontend') 2>&1 | Out-File (Join-Path $outDir "$Step-frontend.log") -Encoding utf8
$frontendExit = $LASTEXITCODE
$backendText = Get-Content (Join-Path $outDir "$Step-backend.log") -Raw
$frontendText = Get-Content (Join-Path $outDir "$Step-frontend.log") -Raw
$record = [ordered]@{ step=$Step; revision=(git rev-parse HEAD).Trim(); backend_exit=$backendExit; frontend_exit=$frontendExit;
    backend_tests=[regex]::Match($backendText,'Ran (\d+) tests').Groups[1].Value;
    frontend_tests=[regex]::Match($frontendText,'tests (\d+)').Groups[1].Value }
$record | ConvertTo-Json | Set-Content (Join-Path $outDir "$Step-checks.json") -Encoding utf8
$record | ConvertTo-Json
if ($backendExit -ne 0) { Get-Content (Join-Path $outDir "$Step-backend.log") -Tail 65 }
if ($frontendExit -ne 0) { Get-Content (Join-Path $outDir "$Step-frontend.log") -Tail 30 }
if ($backendExit -ne 0 -or $frontendExit -ne 0) { exit 1 }
