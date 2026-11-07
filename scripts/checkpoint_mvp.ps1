# Create a local reviewable source snapshot without altering the normal index,
# branch, worktree, databases, credentials, installed dependencies or uploads.
$ErrorActionPreference = 'Stop'
$mvpRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mvpOldIndex = [Environment]::GetEnvironmentVariable('GIT_INDEX_FILE', 'Process')
$mvpTemporaryIndex = Join-Path ([IO.Path]::GetTempPath()) ('paula-mvp-index-' + [guid]::NewGuid().ToString('N'))
Push-Location $mvpRoot
try {
    $env:GIT_INDEX_FILE = $mvpTemporaryIndex
    & git read-tree --empty
    if ($LASTEXITCODE) { throw 'Cannot prepare isolated Git index.' }
    $mvpPaths = @('chatbot', 'paulibot', 'frontend', 'scripts', 'knowledge_base', 'images', '.github',
                  'AGENTS.md', '.gitignore', '.dockerignore', '.env.example', 'Dockerfile',
                  'docker-compose.yml', 'docker-compose.ci.yml', 'requirements.txt', 'manage.py', 'README.md')
    $mvpPaths += @(Get-ChildItem -LiteralPath $mvpRoot -Filter 'PAULA_*.md' -File | ForEach-Object Name)
    & git -c core.safecrlf=false add -- $mvpPaths 2>$null
    if ($LASTEXITCODE) { throw 'Cannot snapshot the selected source paths.' }
    $mvpTree = (& git write-tree).Trim()
    $mvpParent = 'f2abed9b25467229117b292e70135e32ecd097b6'
    $mvpCommit = (& git commit-tree $mvpTree -p $mvpParent -m 'PAULA MVP stabilization candidate: verified source, tests and operations').Trim()
    if ($LASTEXITCODE) { throw 'Cannot create source checkpoint.' }
    $mvpRef = 'refs/heads/checkpoint/mvp-stabilized-20261108'
    & git update-ref $mvpRef $mvpCommit
    if ($LASTEXITCODE) { throw 'Cannot retain source checkpoint.' }
    $mvpFiles = @(& git ls-tree -r --name-only $mvpCommit)
    $mvpChanges = @(& git diff --name-only --ignore-space-at-eol $mvpParent $mvpCommit)
    $mvpManifest = @{ commit=$mvpCommit; tree=$mvpTree; parent=$mvpParent; ref=$mvpRef; files=$mvpFiles.Count;
        changes=$mvpChanges; created_utc=[DateTimeOffset]::UtcNow.ToString('o');
        includes='Selected application/configuration/test/scripts/public knowledge and assets, including root images for pathfinding.';
        excludes='Credentials, databases, uploads, installed dependencies, runtime caches, generated bundles and JSON/PNG measurement artifacts.';
        published=$false; notes='Local candidate checkpoint only; current branch, normal staging area and working files preserved. Review changes before publishing.' }
    $mvpManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath 'PAULA_MVP_RELEASE.json' -Encoding UTF8
    Write-Output ($mvpManifest | ConvertTo-Json -Depth 5 -Compress)
} finally {
    [Environment]::SetEnvironmentVariable('GIT_INDEX_FILE', $mvpOldIndex, 'Process')
    # Retain the isolated index if present; no deletion or normal-index mutation.
    Pop-Location
}
