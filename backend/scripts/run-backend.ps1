param(
    [string]$Port = "8000",
    [switch]$NoReload = $false,
    [switch]$SkipMigrations = $false,
    [string]$DatabaseUrl = "postgresql+psycopg://seniorcare:seniorcare_dev_password@127.0.0.1:5433/seniorcare",
    [string]$AllowedOrigins = "*"
)

$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path -Path $backendRoot -ChildPath ".venv"
$pipExe = Join-Path -Path $venvPath -ChildPath "Scripts\pip.exe"
$pythonExe = Join-Path -Path $venvPath -ChildPath "Scripts\python.exe"
$requirementsFile = Join-Path -Path $backendRoot -ChildPath "requirements.txt"

Write-Host ""
Write-Host "=== RITA Backend - FastAPI Server Launcher ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "[CONFIG] Runtime convention before startup" -ForegroundColor Yellow
Write-Host "[CONFIG] Server and CORS settings shown below" -ForegroundColor Yellow
Write-Host ('[SERVIDOR] http://localhost:' + $Port) -ForegroundColor Magenta
Write-Host ('[DATABASE] ' + $DatabaseUrl) -ForegroundColor Magenta
Write-Host ('[CORS ALLOWED] ' + ($AllowedOrigins -replace ',', ', ')) -ForegroundColor Magenta
Write-Host ""

# 1. Detectar o crear entorno virtual
if (-not (Test-Path $venvPath)) {
    Write-Host '[WARN] .venv no encontrado' -ForegroundColor Yellow
    Write-Host "Creando entorno virtual..." -ForegroundColor Cyan
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Error creando .venv"
    }
    Write-Host "[OK] .venv creado" -ForegroundColor Green
} else {
    Write-Host '[OK] .venv encontrado' -ForegroundColor Green
}

# 2. Instalar dependencias
Write-Host ""
Write-Host "Verificando dependencias..." -ForegroundColor Cyan
& $pipExe install -q -r $requirementsFile
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Reintentando con más verbosidad..." -ForegroundColor Yellow
    & $pipExe install -r $requirementsFile
    if ($LASTEXITCODE -ne 0) {
        throw "Error instalando dependencias"
    }
}
Write-Host '[OK] Dependencias verificadas' -ForegroundColor Green

# 3. Configuración local de entorno
$env:APP_NAME = "RITA Backend"
$env:DATABASE_URL = $DatabaseUrl
$env:ALLOWED_ORIGINS = $AllowedOrigins
if (-not $env:FRONTEND_USERNAME -or [string]::IsNullOrWhiteSpace($env:FRONTEND_USERNAME)) {
    $env:FRONTEND_USERNAME = "admin"
}
if (-not $env:FRONTEND_PASSWORD -or [string]::IsNullOrWhiteSpace($env:FRONTEND_PASSWORD)) {
    $env:FRONTEND_PASSWORD = "admin123"
}

# 4. Aplicar migraciones antes de iniciar API
if (-not $SkipMigrations) {
    Write-Host ""
    Write-Host "Aplicando migraciones (alembic upgrade head)..." -ForegroundColor Cyan
    Push-Location $backendRoot
    try {
        & $pythonExe -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            throw "Error aplicando migraciones"
        }
    }
    finally {
        Pop-Location
    }
    Write-Host '[OK] Migraciones aplicadas' -ForegroundColor Green
}

# 5. Levantar servidor
Write-Host ""
Write-Host "Iniciando servidor FastAPI..." -ForegroundColor Cyan
Write-Host ""

$uvicornArgs = @(
    "app.main:app",
    "--host", "localhost",
    "--port", $Port
)

if (-not $NoReload) {
    $uvicornArgs += "--reload"
}

Push-Location $backendRoot
try {
    & $pythonExe -m uvicorn @uvicornArgs
}
finally {
    Pop-Location
}
