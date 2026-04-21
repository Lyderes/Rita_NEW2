
# Script principal para iniciar todo el sistema RITA localmente.
# Orquestra el Backend, el LLM Server, el Dashboard (Flutter) y el CLI interactivo.

$ErrorActionPreference = "Stop"

# Configuracion del proyecto
$PSScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $PSScriptDir "..")
$BackendRoot = Join-Path $ProjectRoot "backend"
$MobileRoot = Join-Path $ProjectRoot "mobile"
$RitaRoot = Join-Path $ProjectRoot "rita"

# Puertos Canonicos
$BackendPort = 8080
$WebPort = 5190
$LlamaPort = 8001
$DBPort = 5434
$MQTTPort = 1883

Write-Host "`n=== Lanzador RITA: Pasivador de Arquitectura y Estabilizador ===" -ForegroundColor Cyan
Write-Host "Configurando entorno y liberando puertos obligatorios...`n" -ForegroundColor Yellow

# 0. Verificaciones de sistema
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Docker no esta instalado o no esta en el PATH. Es necesario para la arquitectura canonica." -ForegroundColor Red
    exit 1
}

# Verificar si el demonio de Docker esta respondiendo
Write-Host "[INFO] Verificando estado del servicio Docker..." -ForegroundColor Gray
$docker_running = $false
try {
    $null = docker info --format '{{.ID}}' 2>$null
    if ($LASTEXITCODE -eq 0) { 
        $docker_running = $true 
    }
} catch { }

if (-not $docker_running) {
    Write-Host "`n[!] ERROR CRITICO: Docker Desktop no esta ejecutandose o no responde." -ForegroundColor Red
    Write-Host "La arquitectura CANONICA requiere PostgreSQL en Docker (puerto 5434)." -ForegroundColor White
    Write-Host "Por favor, inicie Docker Desktop y vuelva a ejecutar este script.`n" -ForegroundColor Cyan
    exit 1
}

if (-not (Test-Path (Join-Path $BackendRoot ".env"))) {
    Write-Host "[INFO] No se encontro backend/.env. Creando uno desde .env.example..." -ForegroundColor Gray
    Copy-Item (Join-Path $BackendRoot ".env.example") (Join-Path $BackendRoot ".env")
}

# Funcion para cerrar procesos que ocupan un puerto (con proteccion para Docker)
function Ensure-PortFree {
    param([int]$Port, [string]$Label)
    Write-Host "[INFO] Verificando puerto $Port ($Label)..." -ForegroundColor Gray
    
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $found_pid = $conn.OwningProcess
            if ($found_pid -and $found_pid -ne 0) {
                try {
                    $proc = Get-Process -Id $found_pid -ErrorAction SilentlyContinue
                    if ($proc) {
                        # PROTECCION: No matar procesos del sistema Docker para evitar crash del motor
                        if ($proc.Name -like "*Docker*" -or $proc.Name -like "com.docker.*") {
                            Write-Host "[SKIP] El puerto $Port esta siendo usado por Docker. No se cerrara." -ForegroundColor Gray
                            continue
                        }
                        
                        Write-Host "[WAIT] Cerrando $Label (PID $found_pid, $($proc.Name))..." -ForegroundColor Magenta
                        Stop-Process -Id $found_pid -Force -ErrorAction SilentlyContinue
                    }
                }
                catch { }
            }
        }
        Start-Sleep -Seconds 1
    }
}

# 1. Limpieza quirurgica de procesos previos en puertos canonicos
Write-Host "[INFO] Realizando limpieza de puertos especificos..." -ForegroundColor Cyan

Ensure-PortFree -Port $LlamaPort -Label "LLM Server (Local)"
Ensure-PortFree -Port $BackendPort -Label "Backend FastAPI (Local)"
Ensure-PortFree -Port $WebPort -Label "Frontend Flutter (Local)"
# Nota: No cerramos Docker forzado en 5434/1883, solo verificamos si hay procesos host conflictivos
Ensure-PortFree -Port $DBPort -Label "PostgreSQL (Host conflict)"
Ensure-PortFree -Port $MQTTPort -Label "MQTT (Host conflict)"

Write-Host "[INFO] Limpiando procesos de depuracion relacionados con el puerto $WebPort..." -ForegroundColor Gray
$debug_procs = Get-NetTCPConnection -LocalPort $WebPort -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $debug_procs) {
    if ($pid -gt 0) {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "[INFO] Limpiando procesos de Python persistentes..." -ForegroundColor Gray
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*uvicorn*" -or $_.CommandLine -like "*app.main*" } | Stop-Process -Force -ErrorAction SilentlyContinue

# 2. Iniciar Infraestructura (PostgreSQL y MQTT) via Docker
Write-Host "[STEP 1] Asegurando que la infraestructura este corriendo..." -ForegroundColor Cyan
docker compose up -d postgres mqtt

Write-Host "[WAIT] Esperando a que PostgreSQL este listo..." -ForegroundColor Yellow
$retries = 20
while ($retries -gt 0) {
    try {
        $status = docker inspect --format='{{.State.Health.Status}}' rita_db 2>$null
        if ($status -eq "healthy") {
            Write-Host "[OK] PostgreSQL esta listo y saludable." -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "[!] Error de comunicacion con Docker." -ForegroundColor Red
        exit 1
    }
    Write-Host "[WAIT] PostgreSQL aun iniciando... ($retries intentos restantes)" -ForegroundColor Gray
    Start-Sleep -Seconds 3
    $retries--
}

if ($retries -eq 0) {
    Write-Host "[ERROR] PostgreSQL no se inicio a tiempo. Revise 'docker logs rita_db'." -ForegroundColor Red
    exit 1
}

# 3. Migraciones y Semilla
Write-Host "[STEP 2] Sincronizando base de datos (Postgres)..." -ForegroundColor Cyan
Set-Location $BackendRoot
python -m alembic upgrade head
$env:PYTHONPATH = "."
python scripts/seed_db.py
# Semilla de datos de demo (puntuaciones semanales realistas)
if (Test-Path (Join-Path $BackendRoot "seed_week_scores.py")) {
    Write-Host "[INFO] Cargando datos de demo semanales..." -ForegroundColor Gray
    python seed_week_scores.py
}
Set-Location $ProjectRoot

# 4. Iniciar Backend FastAPI (Local)
Write-Host "[STEP 3] Iniciando Backend FastAPI (Puerto $BackendPort)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$BackendRoot'; python -m uvicorn app.main:app --host 0.0.0.0 --port $BackendPort --no-access-log" -WindowStyle Minimized

# 5. Iniciar REAL LLM Server (Llama.cpp) - OPCIONAL
Write-Host "[STEP 4] Verificando LLM Server (Puerto $LlamaPort)..." -ForegroundColor Cyan
$LlmEnabled = $false
$ModelPath = Join-Path $RitaRoot "models/model.gguf"
$LlamaVenvPython = Join-Path $env:LOCALAPPDATA "rita-venv\Scripts\python.exe"

if (-Not (Test-Path $ModelPath)) {
    Write-Host "[SKIP] Modelo LLM no encontrado en $ModelPath" -ForegroundColor Yellow
    Write-Host "       El motor de conversacion de voz estara deshabilitado." -ForegroundColor Yellow
    Write-Host "       Para habilitarlo: descarga el modelo y colocalo en rita/models/model.gguf" -ForegroundColor Gray
    Write-Host "       Para configurar el entorno: ejecuta rita/scripts/setup-llama-cpp.ps1" -ForegroundColor Gray
} elseif (-Not (Test-Path $LlamaVenvPython)) {
    Write-Host "[SKIP] Entorno rita-venv no encontrado en $LlamaVenvPython" -ForegroundColor Yellow
    Write-Host "       El motor de conversacion de voz estara deshabilitado." -ForegroundColor Yellow
    Write-Host "       Para habilitarlo: ejecuta rita/scripts/setup-llama-cpp.ps1" -ForegroundColor Gray
} else {
    $LlmEnabled = $true
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$RitaRoot'; & '$LlamaVenvPython' -m llama_cpp.server --model '$ModelPath' --port $LlamaPort --n_ctx 2048 --n_threads 4" -WindowStyle Minimized
    Write-Host "[OK] LLM Server iniciado en puerto $LlamaPort." -ForegroundColor Green
}

# Esperar a que el backend responda
Write-Host "[WAIT] Esperando al backend..." -ForegroundColor Yellow
for ($i=1; $i -le 20; $i++) {
    try {
        $status = (Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -UseBasicParsing -ErrorAction SilentlyContinue).StatusCode
        if ($status -eq 200) {
            Write-Host "[OK] Backend FastAPI respondiendo." -ForegroundColor Green
            break
        }
    } catch { }
    Write-Host "[WAIT] Backend iniciando... ($i/20)" -ForegroundColor Gray
    Start-Sleep -Seconds 3
}

# 6. Iniciar MQTT Consumer (Background)
Write-Host "[STEP 5] Iniciando MQTT Ingest Consumer..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$BackendRoot'; `$env:PYTHONPATH='.'; python scripts/run_mqtt_consumer.py" -WindowStyle Minimized

# 7. Iniciar Frontend Flutter (Web Local)
Write-Host "[STEP 6] Iniciando Dashboard Flutter Web (Puerto $WebPort)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$MobileRoot'; flutter run -d chrome --web-hostname 127.0.0.1 --web-port $WebPort --dart-define=RITA_API_BASE_URL=http://127.0.0.1:$BackendPort"

# 7. Verificacion de Salud y Topologia Final
Write-Host "`n=== Verificacion Final de Topologia y Salud ===" -ForegroundColor Cyan

function Wait-ForPort {
    param([int]$Port, [string]$Label, [int]$MaxRetries = 10)
    Write-Host "[CHECK] Verificando $Label en puerto $Port..." -NoNewline -ForegroundColor Gray
    for ($i = 0; $i -lt $MaxRetries; $i++) {
        $connection = Test-NetConnection -ComputerName "127.0.0.1" -Port $Port -InformationLevel Quiet
        if ($connection) {
            Write-Host " [OK]" -ForegroundColor Green
            return $true
        }
        Write-Host "." -NoNewline -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
    Write-Host " [FALLO]" -ForegroundColor Red
    return $false
}

$all_ok = $true
$all_ok = (Wait-ForPort -Port $DBPort -Label "PostgreSQL (Docker)") -and $all_ok
$all_ok = (Wait-ForPort -Port $MQTTPort -Label "MQTT (Docker)") -and $all_ok
$all_ok = (Wait-ForPort -Port $BackendPort -Label "Backend FastAPI (Local)") -and $all_ok
$all_ok = (Wait-ForPort -Port $WebPort -Label "Frontend Flutter (Local)") -and $all_ok
if ($LlmEnabled) {
    $all_ok = (Wait-ForPort -Port $LlamaPort -Label "LLM Server (Local)") -and $all_ok
}

if (-not $all_ok) {
    Write-Host "`n[!] ADVERTENCIA: Algunos servicios no parecen estar respondiendo correctamente." -ForegroundColor Yellow
} else {
    Write-Host "`n=== Todo el sistema RITA esta en linea ===" -ForegroundColor Green
}

Write-Host "`nResumen de Topologia:" -ForegroundColor White
Write-Host "- Postgres (Docker):   localhost:$DBPort" -ForegroundColor Gray
Write-Host "- MQTT (Docker):       localhost:$MQTTPort" -ForegroundColor Gray
Write-Host "- Backend (Local):     http://localhost:$BackendPort" -ForegroundColor Gray
Write-Host "- API Docs:            http://localhost:$BackendPort/docs" -ForegroundColor Gray
Write-Host "- Dashboard (Local):   http://localhost:$WebPort" -ForegroundColor Gray
if ($LlmEnabled) {
    Write-Host "- LLM Engine (Local):  http://localhost:$LlamaPort" -ForegroundColor Gray
} else {
    Write-Host "- LLM Engine:          [DESHABILITADO - modelo no encontrado]" -ForegroundColor DarkGray
}
Write-Host "--------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "ACCESO RAPIDO (demo):" -ForegroundColor White
Write-Host "  http://localhost:$WebPort/#/autologin   (login automatico, solo dev)" -ForegroundColor Cyan
Write-Host "  Usuario: admin  |  Password: admin123" -ForegroundColor Cyan
Write-Host "--------------------------------------------------------`n" -ForegroundColor Cyan

# 8. Iniciar RITA Modo Texto de forma interactiva
Write-Host "`n[STEP 7] Iniciando RITA Modo Texto CLI interactivo:`n" -ForegroundColor Cyan
Write-Host "--------------------------------------------------------" -ForegroundColor White

$env:PYTHONPATH = Join-Path $RitaRoot "edge"
Set-Location $RitaRoot
python -m src.conversation.text_cli

