param([switch]$Verbose = $false)

Write-Host "=== RITA Development - Setup Verification ===" -ForegroundColor Cyan
Write-Host ""

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# 1. Flutter
Write-Host "[CHECK] Flutter..." -ForegroundColor Yellow
try {
    $flutter = & flutter --version 2>&1 | Select-Object -First 1
    Write-Host "   [OK] $flutter" -ForegroundColor Green
} catch {
    Write-Host "   [FAIL] Flutter no instalado" -ForegroundColor Red
}

# 2. Backend venv
Write-Host "[CHECK] Backend .venv..." -ForegroundColor Yellow
$backendRoot = Join-Path $projectRoot "backend"
$venvPath = Join-Path $backendRoot ".venv"
$pythonExe = Join-Path -Path $venvPath -ChildPath "Scripts\python.exe"
if (Test-Path $pythonExe) {
    Write-Host "   [OK] .venv encontrado" -ForegroundColor Green
} else {
    Write-Host "   [WARN] .venv no existe (se creara automaticamente)" -ForegroundColor Yellow
}

# 3. Backend dependencies
Write-Host "[CHECK] Backend requirements.txt..." -ForegroundColor Yellow
$requirementsFile = Join-Path -Path $backendRoot -ChildPath "requirements.txt"
if (Test-Path $requirementsFile) {
    Write-Host "   [OK] requirements.txt encontrado" -ForegroundColor Green
} else {
    Write-Host "   [FAIL] requirements.txt no encontrado" -ForegroundColor Red
}

# 4. Mobile pubspec
Write-Host "[CHECK] Mobile pubspec.yaml..." -ForegroundColor Yellow
$mobileRoot = Join-Path $projectRoot "mobile"
$pubspecFile = Join-Path -Path $mobileRoot -ChildPath "pubspec.yaml"
if (Test-Path $pubspecFile) {
    Write-Host "   [OK] pubspec.yaml encontrado" -ForegroundColor Green
} else {
    Write-Host "   [FAIL] pubspec.yaml no encontrado" -ForegroundColor Red
}

# 5. Scripts
Write-Host "[CHECK] Scripts..." -ForegroundColor Yellow
$runDevScript = Join-Path -Path $projectRoot -ChildPath "scripts\run-dev.ps1"
$runBackendScript = Join-Path -Path $backendRoot -ChildPath "scripts\run-backend.ps1"
$runMobileScript = Join-Path -Path $mobileRoot -ChildPath "scripts\run-mobile.ps1"

@($runDevScript, $runBackendScript, $runMobileScript) | ForEach-Object {
    if (Test-Path $_) {
        Write-Host "   [OK] $(Split-Path -Leaf $_)" -ForegroundColor Green
    } else {
        Write-Host "   [FAIL] $(Split-Path -Leaf $_)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== RESUMEN ===" -ForegroundColor Cyan
Write-Host "Puedes ejecutar:" -ForegroundColor Green
Write-Host ""
Write-Host "powershell -ExecutionPolicy Bypass -File .\scripts\run-dev.ps1 -Mode run" -ForegroundColor Cyan
Write-Host ""
