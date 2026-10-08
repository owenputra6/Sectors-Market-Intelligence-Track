$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $Root "backend")

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created backend\.env. Add SECTORS_API_KEY only when you later want a refresh." -ForegroundColor Yellow
}

# Never start the weekly scheduler or make provider requests in this process.
$env:WEEKLY_REFRESH_ENABLED = "false"
$env:CACHE_ONLY_MODE = "true"

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
