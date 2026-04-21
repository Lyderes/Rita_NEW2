
param(
    [string]$Python = ".venv\\Scripts\\python.exe"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $backendDir
$pythonPath = Join-Path $repoRoot $Python

if (-not (Test-Path $pythonPath)) {
    Write-Error "No se encontro Python en '$pythonPath'. Crea o ajusta la venv antes de ejecutar este script."
}

Push-Location $backendDir
try {
    $env:PYTHONPATH = $backendDir

    Write-Host "[1/3] Ruff: comprobando estilo basico en backend/app y backend/tests..." -ForegroundColor Cyan
    & $pythonPath -m ruff check app tests
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    Write-Host "[2/3] Pytest: ejecutando la suite del backend..." -ForegroundColor Cyan
    & $pythonPath -m pytest tests -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    Write-Host "[3/3] Alembic: verificando que no haya migraciones pendientes..." -ForegroundColor Cyan
    & $pythonPath -m alembic check
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    Write-Host "Checks locales completados correctamente." -ForegroundColor Green
}
finally {
    Pop-Location
}