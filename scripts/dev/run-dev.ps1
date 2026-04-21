
# NOTA: Este script es el lanzador principal de desarrollo. Algunos modos o rutas pueden estar LEGACY, pero el script debe mantenerse.
param(
    [ValidateSet("setup", "run", "clean", "live")]
    [string]$Mode = "run",
    [string]$BackendPort = "8000",
    [switch]$NoReload = $false,
    [string]$WebHost = "127.0.0.1",
    [int]$WebPort = 5190
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backendRoot = Join-Path -Path $projectRoot -ChildPath "backend"
$mobileRoot = Join-Path -Path $projectRoot -ChildPath "mobile"
$ritaRoot = Join-Path -Path $projectRoot -ChildPath "rita"
$backendScriptPath = Join-Path -Path $backendRoot -ChildPath "scripts\run-backend.ps1"
$llamaScriptPath = Join-Path -Path $ritaRoot -ChildPath "scripts\run-llama-server.ps1"
$ritaScriptPath = Join-Path -Path $ritaRoot -ChildPath "scripts\run-rita.ps1"
$apiHealthUrl = "http://localhost:$BackendPort/health"
$webUrl = "http://${WebHost}:$WebPort"
$backendDbUrl = "postgresql+psycopg://seniorcare:seniorcare_dev_password@127.0.0.1:5433/seniorcare"
$devAllowedOrigins = "*"

function Get-FlutterCommand {
    $flutterCmd = Get-Command flutter -ErrorAction SilentlyContinue
    if ($flutterCmd) {
        return "flutter"
    }

    $fallback = "C:\flutter\bin\flutter.bat"
    if (Test-Path $fallback) {
        return $fallback
    }

    throw "Flutter no esta instalado o no se encuentra en PATH."
}

function Invoke-FlutterStep {
    param(
        [string]$StepName,
        [string[]]$StepArgs
    )

    Write-Host ('[RUN] ' + $StepName) -ForegroundColor Cyan
    & $global:FlutterCommand @StepArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host ('[KO] ' + $StepName) -ForegroundColor Red
        return $false
    }
    Write-Host ('[OK] ' + $StepName) -ForegroundColor Green
    return $true
}

Write-Host ""
Write-Host "=== RITA Development - End-to-End Launcher ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "[CONFIG] Runtime convention before startup" -ForegroundColor Yellow
Write-Host "[CONFIG] Backend and frontend ports are shown below" -ForegroundColor Yellow
Write-Host ('[BACKEND] http://localhost:' + $BackendPort) -ForegroundColor Magenta
Write-Host ('[FRONTEND] http://' + $WebHost + ':' + $WebPort) -ForegroundColor Magenta
Write-Host '[CORS ALLOWED] * (development)' -ForegroundColor Magenta
Write-Host ""

function Test-ApiHealth {
    try {
        $response = Invoke-WebRequest -Uri $apiHealthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $json = $response.Content | ConvertFrom-Json
            Write-Host ('[OK] API Health: ' + $json.status) -ForegroundColor Green
            return $true
        }
    } catch {
        # API no responde aun
    }
    return $false
}

function Ensure-PortFree {
    param(
        [int]$Port,
        [string]$Label
    )

    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        return
    }

    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        Write-Host ("[WARN] " + $Label + " usa puerto " + $Port + " (PID " + $procId + ", " + $proc.ProcessName + "). Cerrando...") -ForegroundColor Yellow
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
}

function Start-Backend {
    Write-Host '[PASO 1] Iniciando Backend FastAPI...' -ForegroundColor Cyan
    Write-Host ""

    $psArgs = @("-NoExit", "-Command")
    $backendCommand = "cd '$backendRoot'; powershell -ExecutionPolicy Bypass -File '$backendScriptPath' -Port $BackendPort -DatabaseUrl '$backendDbUrl' -AllowedOrigins '$devAllowedOrigins'"
    if ($NoReload) {
        $backendCommand += " -NoReload"
    }
    $backendCommand += "; Read-Host 'Presiona Enter para cerrar'"
    $psArgs += $backendCommand

    $proc = Start-Process -FilePath "powershell" -ArgumentList $psArgs -PassThru
    $global:BackendPID = $proc.Id

    Write-Host ('[OK] Backend iniciado (PID: ' + $proc.Id + ')') -ForegroundColor Green
    Write-Host ""
    Write-Host ("Esperando respuesta en " + $apiHealthUrl + "...") -ForegroundColor Yellow

    $maxAttempts = 30
    $attempt = 0
    while ($attempt -lt $maxAttempts) {
        if (Test-ApiHealth) {
            Write-Host '[OK] Backend listo!' -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 1
        $attempt++
        Write-Host ("  Intento " + $attempt + "/" + $maxAttempts + "...") -ForegroundColor Gray
    }

    Write-Host '[FAIL] Backend no responde (timeout 30s)' -ForegroundColor Red
    return $false
}

function Start-Flutter {
    Write-Host ""
    Write-Host '[PASO 2] Verificando dependencias Flutter...' -ForegroundColor Cyan
    Write-Host ""

    Ensure-PortFree -Port $WebPort -Label "Flutter web"

    Push-Location $mobileRoot
    try {
        if (-not (Invoke-FlutterStep -StepName "flutter pub get" -StepArgs @("pub", "get"))) {
            return $false
        }
    }
    finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host '[PASO 3] Ejecutando App en Chrome...' -ForegroundColor Cyan
    Write-Host ("[INFO] URL objetivo: " + $webUrl) -ForegroundColor Yellow
    Write-Host ""

    Push-Location $mobileRoot
    try {
        & $global:FlutterCommand run -d chrome --web-hostname $WebHost --web-port $WebPort
        if ($LASTEXITCODE -ne 0) {
            Write-Host '[KO] Flutter web no pudo arrancar' -ForegroundColor Red
            return $false
        }
        Write-Host '[OK] Flutter web finalizo correctamente' -ForegroundColor Green
        return $true
    }
    finally {
        Pop-Location
    }
}

function Cleanup-Backend {
    if ($global:BackendPID) {
        Write-Host ("Cerrando backend (PID: " + $global:BackendPID + ")...") -ForegroundColor Yellow
        try {
            Stop-Process -Id $global:BackendPID -Force -ErrorAction SilentlyContinue
            Write-Host '[OK] Backend cerrado' -ForegroundColor Green
        } catch {
            Write-Host '[WARN] No se pudo cerrar backend' -ForegroundColor Yellow
        }
    }
}

function Start-DetachedPowerShell {
    param(
        [string]$WorkingDirectory,
        [string]$Command,
        [string]$Label
    )

    $psArgs = @("-NoExit", "-Command", $Command)
    $proc = Start-Process -FilePath "powershell" -WorkingDirectory $WorkingDirectory -ArgumentList $psArgs -PassThru
    Write-Host ("[OK] " + $Label + " (PID: " + $proc.Id + ")") -ForegroundColor Green
    return $proc.Id
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$MaxAttempts = 40,
        [int]$DelaySeconds = 1
    )

    for ($i = 0; $i -lt $MaxAttempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
            if ($resp -and $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                return $true
            }
        } catch {
            # waiting
        }
        Start-Sleep -Seconds $DelaySeconds
    }
    return $false
}

function Start-LiveStack {
    Write-Host "" 
    Write-Host "[LIVE] Levantando stack en paralelo (backend + llama + dashboard + RITA texto)..." -ForegroundColor Cyan
    Write-Host ""

    if (-not (Test-Path $backendScriptPath)) {
        throw "Backend script no encontrado: $backendScriptPath"
    }
    if (-not (Test-Path $llamaScriptPath)) {
        throw "Llama script no encontrado: $llamaScriptPath"
    }
    if (-not (Test-Path $ritaScriptPath)) {
        throw "RITA script no encontrado: $ritaScriptPath"
    }

    $backendCommand = "Set-Location '$backendRoot'; powershell -ExecutionPolicy Bypass -File '$backendScriptPath' -Port $BackendPort -DatabaseUrl '$backendDbUrl' -AllowedOrigins '$devAllowedOrigins'"
    if ($NoReload) {
        $backendCommand += " -NoReload"
    }
    $backendPid = Start-DetachedPowerShell -WorkingDirectory $backendRoot -Command $backendCommand -Label "Backend"

    $llamaCommand = "Set-Location '$ritaRoot'; powershell -ExecutionPolicy Bypass -File '$llamaScriptPath' -Port 8001"
    $llamaPid = Start-DetachedPowerShell -WorkingDirectory $ritaRoot -Command $llamaCommand -Label "llama.cpp server"

    Ensure-PortFree -Port $WebPort -Label "Dashboard"
    $flutterCommand = "Set-Location '$mobileRoot'; & '$($global:FlutterCommand)' run -d chrome --web-hostname $WebHost --web-port $WebPort"
    $flutterPid = Start-DetachedPowerShell -WorkingDirectory $mobileRoot -Command $flutterCommand -Label "Dashboard Flutter"

    $ritaCommand = "Set-Location '$ritaRoot'; powershell -ExecutionPolicy Bypass -File '$ritaScriptPath' -Mode text"
    $ritaPid = Start-DetachedPowerShell -WorkingDirectory $ritaRoot -Command $ritaCommand -Label "RITA texto"

    if (Wait-HttpReady -Url $webUrl -MaxAttempts 45 -DelaySeconds 1) {
        Write-Host ("[OK] Dashboard disponible en " + $webUrl) -ForegroundColor Green
    } else {
        Write-Host ("[WARN] Dashboard no respondio a tiempo en " + $webUrl) -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "[LIVE] Servicios lanzados:" -ForegroundColor Yellow
    Write-Host ("  - Backend PID: " + $backendPid)
    Write-Host ("  - llama.cpp PID: " + $llamaPid)
    Write-Host ("  - Dashboard PID: " + $flutterPid)
    Write-Host ("  - RITA texto PID: " + $ritaPid)
    Write-Host ""
    Write-Host ("[LIVE] Dashboard: " + $webUrl) -ForegroundColor Magenta
    Write-Host ("[LIVE] API: " + $apiHealthUrl) -ForegroundColor Magenta
    Write-Host ""
    Write-Host "Si ya habia procesos viejos en los mismos puertos, cierralos antes de usar -Mode live." -ForegroundColor Yellow
}

# Main
try {
    $global:FlutterCommand = Get-FlutterCommand

    switch ($Mode) {
        "setup" {
            Write-Host "Modo SETUP" -ForegroundColor Cyan
            Write-Host ""

            if (-not (Test-Path $backendScriptPath)) {
                throw "Backend script no encontrado: $backendScriptPath"
            }
            Write-Host '[OK] Backend script' -ForegroundColor Green

            Write-Host '[OK] Mobile pubspec' -ForegroundColor Green
            Write-Host ""
            Write-Host "Ejecutando flutter doctor..." -ForegroundColor Cyan
            Push-Location $mobileRoot
            try {
                & $global:FlutterCommand doctor
            }
            finally {
                Pop-Location
            }
        }
        "run" {
            Write-Host "Login demo:" -ForegroundColor Yellow
            Write-Host "  usuario: admin" -ForegroundColor White
            Write-Host "  password: admin123" -ForegroundColor White
            Write-Host ""

            if (-not (Start-Backend)) {
                throw "No se pudo conectar al backend"
            }

            Write-Host ""
            Write-Host '[OK] Backend respondiendo' -ForegroundColor Green
            Write-Host ""

            if (-not (Start-Flutter)) {
                throw "Flutter web no pudo arrancar correctamente"
            }
        }
        "clean" {
            Write-Host ""
            Write-Host "[CLEAN] Limpieza exhaustiva de cache y build" -ForegroundColor Yellow
            Write-Host ""

            Write-Host "Limpiando backend..." -ForegroundColor Cyan
            Cleanup-Backend

            Write-Host "Limpiando Flutter..." -ForegroundColor Cyan
            Push-Location $mobileRoot
            try {
                Write-Host "  - flutter clean" -ForegroundColor Gray
                & $global:FlutterCommand clean

                Write-Host "  - removing .dart_tool/" -ForegroundColor Gray
                if (Test-Path ".dart_tool") {
                    Remove-Item -Path ".dart_tool" -Recurse -Force -ErrorAction SilentlyContinue
                }

                Write-Host "  - removing build/" -ForegroundColor Gray
                if (Test-Path "build") {
                    Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
                }

                Write-Host "  - flutter pub get" -ForegroundColor Gray
                & $global:FlutterCommand pub get
            }
            finally {
                Pop-Location
            }

            Write-Host ""
            Write-Host '[OK] Limpieza completa' -ForegroundColor Green
            Write-Host ""
            Write-Host "Proximo paso: ejecutar con -Mode run" -ForegroundColor Yellow
            Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\run-dev.ps1 -Mode run" -ForegroundColor Cyan
        }
        "live" {
            Start-LiveStack
        }
    }
}
catch {
    Write-Host ""
    Write-Host ("[FAIL] Error: " + $_) -ForegroundColor Red
    Cleanup-Backend
    exit 1
}
finally {
    if ($Mode -eq "run") {
        Write-Host ""
        Write-Host "Cerrando..." -ForegroundColor Yellow
        Cleanup-Backend
    }
}
