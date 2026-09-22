# Build the UI once and serve everything (API + UI) from a single process on Windows.
param(
  [int]$Port = 8000,
  [switch]$Rebuild
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VenvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
  $launcher = @("py", "python", "python3") | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
  if (-not $launcher) { throw "Python 3.11+ was not found on PATH." }
  & $launcher -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
}
& $VenvPython -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Fuseline needs Python 3.11 or newer." }
& $VenvPython -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Installing Python dependencies failed." }

if ($Rebuild -or -not (Test-Path ".\frontend\dist\index.html")) {
  Write-Host "Building the UI..."
  Push-Location frontend
  try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "UI build failed." }
  } finally {
    Pop-Location
  }
}

Write-Host "Fuseline is running at http://127.0.0.1:$Port  (Ctrl+C to stop)"
& $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port --app-dir backend
