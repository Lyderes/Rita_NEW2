
# LEGACY/DEPRECATED: Script específico para levantar el servidor llama.cpp local (puerto 8001).
# Mantener solo para pruebas LLM locales. No es parte del flujo operativo principal de RITA.
param(
    [string]$ModelPath = ".\models\model.gguf",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8001,
    [int]$CtxSize = 1024,
    [int]$GpuLayers = 0
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvPath = Join-Path $env:LOCALAPPDATA "rita-venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"

Set-Location $ProjectRoot

if (-not (Test-Path $VenvPath)) {
    Write-Host "[INFO] Creando entorno virtual en $VenvPath"
    py -m venv $VenvPath
}

if (-not (Test-Path $PythonExe)) {
    throw "No se encontro Python dentro del entorno virtual: $PythonExe"
}

$ModuleCheck = & $PythonExe -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('llama_cpp') else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Instalando llama-cpp-python"
    & $PythonExe -m pip install llama-cpp-python
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo instalar llama-cpp-python. En Windows instala Build Tools de Visual Studio (Desktop development with C++) y reintenta."
    }

    & $PythonExe -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('llama_cpp') else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "llama_cpp no esta disponible en el entorno virtual."
    }
}

$ResolvedModelPath = $ModelPath
if (-not [System.IO.Path]::IsPathRooted($ResolvedModelPath)) {
    $ResolvedModelPath = Join-Path $ProjectRoot $ResolvedModelPath
}

if (-not (Test-Path $ResolvedModelPath)) {
    throw "No se encontro el modelo GGUF en: $ResolvedModelPath"
}

Write-Host "[INFO] Iniciando llama.cpp server"
Write-Host "[INFO] URL base: http://${BindHost}:$Port"
Write-Host "[INFO] Modelo: $ResolvedModelPath"

& $PythonExe -m llama_cpp.server --host $BindHost --port $Port --model $ResolvedModelPath --n_ctx $CtxSize --n_gpu_layers $GpuLayers
