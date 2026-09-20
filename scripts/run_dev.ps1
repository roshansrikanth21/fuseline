# Start Fuseline API + Vite UI (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "Creating venv..."
  python -m venv .venv
  .\.venv\Scripts\pip install -r requirements.txt
}

if (-not (Test-Path ".\samples\demo_case\app_usage.db")) {
  .\.venv\Scripts\python .\scripts\seed_demo.py
}

if (-not (Test-Path ".\frontend\node_modules")) {
  Push-Location frontend
  npm install
  Pop-Location
}

Write-Host "Starting API on :8000 and UI on :5173 ..."
$api = Start-Process -PassThru -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" -ArgumentList @(
  "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000", "--app-dir", "backend"
)
Push-Location frontend
try {
  npm run dev -- --host 127.0.0.1 --port 5173
} finally {
  if ($api -and -not $api.HasExited) {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
  }
  Pop-Location
}