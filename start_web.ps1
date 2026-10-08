$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $Root "frontend")

if (-not (Test-Path "web")) {
    python tool\bootstrap_platforms.py
}

flutter run -d chrome --web-port 5173 --dart-define=API_BASE_URL=http://127.0.0.1:8000
