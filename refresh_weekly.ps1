$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $Root "backend")

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created backend\.env. Put your SECTORS_API_KEY inside it first." -ForegroundColor Yellow
    exit 1
}

python -m app.refresh
