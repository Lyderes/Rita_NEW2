
# LEGACY/DEPRECATED: Script para preparar entorno llama.cpp (LLM local). No es parte del flujo operativo principal de RITA.
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvPath = Join-Path $env:LOCALAPPDATA "rita-venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$ReadyFlag = Join-Path $ProjectRoot ".llama_setup_ready"
$ModelsDir = Join-Path $ProjectRoot "models"

Set-Location $ProjectRoot

$NeedsSetup = $false
if (-not (Test-Path $VenvPath)) {
    Write-Host "[INFO] Creando entorno virtual en $VenvPath"
    py -m venv $VenvPath
    $NeedsSetup = $true
}

if (-not (Test-Path $PythonExe)) {
    throw "No se encontro Python dentro del entorno virtual: $PythonExe"
}

if ($Force -or $NeedsSetup -or -not (Test-Path $ReadyFlag)) {
    Write-Host "[INFO] Instalando dependencias de RITA"
    & $PythonExe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo al actualizar pip en el entorno virtual."
    }
    & $PythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo al instalar requirements.txt."
    }

    Write-Host "[INFO] Instalando llama-cpp-python"
    & $PythonExe -m pip install llama-cpp-python
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo instalar llama-cpp-python. En Windows instala Build Tools de Visual Studio (Desktop development with C++) y reintenta."
    }

    "ok" | Set-Content $ReadyFlag
    Write-Host "[OK] Setup de llama.cpp completado"
} else {
    Write-Host "[INFO] Setup ya completado. Usa -Force para reinstalar."
}

if (-not (Test-Path $ModelsDir)) {
    New-Item -Path $ModelsDir -ItemType Directory | Out-Null
}

Write-Host "[INFO] Coloca tu modelo GGUF en: $ModelsDir\model.gguf"
