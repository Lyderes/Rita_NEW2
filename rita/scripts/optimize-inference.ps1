
# Script para optimizar la inferencia del LLM local usando aceleracion por hardware (GPU/Vulkan).
# Este script reinstala llama-cpp-python con los flags de compilacion adecuados.

$ErrorActionPreference = "Stop"

Write-Host "=== Optimizador de Inferencia RITA ===" -ForegroundColor Cyan

# 1. Localizar entorno virtual
$VenvPath = Join-Path $env:LOCALAPPDATA "rita-venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] No se encontro el entorno rita-venv en $VenvPath" -ForegroundColor Red
    Write-Host "Por favor, corre rita/scripts/setup-llama-cpp.ps1 primero."
    exit 1
}

Write-Host "`nSelecciona el tipo de aceleracion para tu hardware:" -ForegroundColor Yellow
Write-Host "1. NVIDIA (CUDA) - Requiere CUDA Toolkit instalado."
Write-Host "2. Universal (Vulkan) - Recomendado para Intel/AMD/NVIDIA modernos."
Write-Host "3. Solo CPU (Sin cambios) - Lento pero compatible."

$choice = Read-Host "`nOpcion [1-3]"

$env:FORCE_CMAKE = "1"
switch ($choice) {
    "1" {
        $env:CMAKE_ARGS = "-DGGML_CUDA=on"
        Write-Host "[INFO] Configurando para NVIDIA CUDA..." -ForegroundColor Gray
    }
    "2" {
        $env:CMAKE_ARGS = "-DGGML_VULKAN=on"
        Write-Host "[INFO] Configurando para Universal Vulkan..." -ForegroundColor Gray
    }
    "3" {
        Write-Host "[INFO] Saliendo sin cambios." -ForegroundColor Gray
        exit 0
    }
    Default {
        Write-Host "[ERROR] Opcion invalida." -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n[STEP] Desarrollando y compilando llama-cpp-python acelerado..." -ForegroundColor Cyan
Write-Host "Este proceso puede tardar varios minutos y requiere 'Visual Studio Build Tools' instalado." -ForegroundColor Gray

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[OK] Optimizacion completada con exito." -ForegroundColor Green
    Write-Host "Ahora puedes reiniciar RITA con 'start-rita.ps1' y notarás una gran mejora en la velocidad." -ForegroundColor White
} else {
    Write-Host "`n[FALLO] La compilacion fallo." -ForegroundColor Red
    Write-Host "Asegurate de tener instalados los 'Visual Studio Build Tools' (C++ workload)." -ForegroundColor Yellow
}
