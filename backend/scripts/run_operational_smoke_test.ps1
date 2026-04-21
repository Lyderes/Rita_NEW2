param(
    [string]$BaseUrl = "",
    [int]$Port = 8011,
    [string]$Username = "",
    [string]$Password = "",
    [string]$DatabaseUrl = "",
    [switch]$StartServer,
    [string]$DeviceCode = "",
    [string]$DeviceToken = "",
    [string]$Python = ".venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Import-EnvFile {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }

        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($key) {
            $values[$key] = $value
        }
    }

    return $values
}

function Get-FirstValue {
    param(
        [string[]]$Candidates,
        [string]$Fallback = ""
    )

    foreach ($candidate in $Candidates) {
        if ($null -ne $candidate -and $candidate -ne "") {
            return $candidate
        }
    }

    return $Fallback
}

function Test-BackendHealth {
    param([string]$Url)

    try {
        $response = Invoke-RestMethod -Method Get -Uri ($Url.TrimEnd('/') + "/health") -TimeoutSec 3
        return $response.status -eq "ok"
    }
    catch {
        return $false
    }
}

function Wait-BackendReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-BackendHealth -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Test-LocalLikeUrl {
    param([string]$Url)

    try {
        $uri = [System.Uri]$Url
        return $uri.Host -in @("127.0.0.1", "localhost")
    }
    catch {
        return $false
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $backendDir
$pythonPath = Join-Path $repoRoot $Python
$flowScript = Join-Path $scriptDir "run_operational_flow_check.py"
$envFile = Join-Path $backendDir ".env"

if (-not (Test-Path $backendDir)) {
    Write-Error "No se encontro backendDir '$backendDir'."
}
if (-not (Test-Path $pythonPath)) {
    Write-Error "No se encontro Python en '$pythonPath'. Crea o ajusta la venv antes de ejecutar este script."
}
if (-not (Test-Path $flowScript)) {
    Write-Error "No se encontro el smoke test operativo base en '$flowScript'."
}
if ($DeviceCode -and -not $DeviceToken) {
    Write-Error "Si pasas -DeviceCode debes pasar tambien -DeviceToken."
}

$envValues = Import-EnvFile -Path $envFile
$resolvedUsername = Get-FirstValue -Candidates @($Username, $env:FRONTEND_USERNAME, $envValues["FRONTEND_USERNAME"]) -Fallback "admin"
$resolvedPassword = Get-FirstValue -Candidates @($Password, $env:FRONTEND_PASSWORD, $envValues["FRONTEND_PASSWORD"]) -Fallback "admin123"
$configuredDatabaseUrl = Get-FirstValue -Candidates @($DatabaseUrl, $env:DATABASE_URL, $envValues["DATABASE_URL"])

# Modo reproducible local: si la config activa apunta al servicio docker "postgres"
# (hostname interno de Compose), usamos el equivalente accesible desde el host.
$defaultManagedLocalDatabaseUrl = "postgresql+psycopg://seniorcare:seniorcare_dev_password@127.0.0.1:5433/seniorcare"
$smokeBaseUrl = if ($BaseUrl) { $BaseUrl.TrimEnd('/') } else { "http://127.0.0.1:$Port" }
$effectiveDatabaseUrl = $configuredDatabaseUrl
if (-not $BaseUrl -and (-not $effectiveDatabaseUrl -or $effectiveDatabaseUrl -match "@postgres[:/]") ) {
    $effectiveDatabaseUrl = $defaultManagedLocalDatabaseUrl
}

Write-Host "=== RITA Operational Smoke Test Wrapper ===" -ForegroundColor Green
Write-Host "backend_dir=$backendDir"
Write-Host "base_url=$smokeBaseUrl"
Write-Host "username=$resolvedUsername"
if ($effectiveDatabaseUrl) {
    Write-Host "database_url=$effectiveDatabaseUrl"
}
else {
    Write-Host "database_url=<usar entorno activo del proceso>"
}

Write-Step "[1/5] Verificando entorno minimo y dependencia requests..."
Push-Location $backendDir

$startedProcess = $null
$stdoutLog = $null
$stderrLog = $null
$previousDatabaseUrl = $env:DATABASE_URL

try {
    & $pythonPath -c "import requests" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Falta el paquete 'requests' en la venv. Instala con: $pythonPath -m pip install requests"
    }

    if ($effectiveDatabaseUrl) {
        $env:DATABASE_URL = $effectiveDatabaseUrl
    }

    $backendHealthy = Test-BackendHealth -Url $smokeBaseUrl
    $canManageLocal = (-not $BaseUrl) -or $StartServer

    if ($backendHealthy) {
        Write-Step "[2/5] Backend ya disponible en $smokeBaseUrl; se reutiliza la instancia existente."
    }
    elseif ($canManageLocal) {
        Write-Step "[2/5] Aplicando migraciones locales reproducibles antes de arrancar backend temporal..."
        & $pythonPath -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        $localBaseUrl = "http://127.0.0.1:$Port"
        $smokeBaseUrl = $localBaseUrl
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $stdoutLog = Join-Path $env:TEMP "rita-operational-smoke-$stamp.out.log"
        $stderrLog = Join-Path $env:TEMP "rita-operational-smoke-$stamp.err.log"

        Write-Step "[3/5] Levantando backend temporal en $smokeBaseUrl ..."
        $startedProcess = Start-Process `
            -FilePath $pythonPath `
            -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") `
            -WorkingDirectory $backendDir `
            -PassThru `
            -RedirectStandardOutput $stdoutLog `
            -RedirectStandardError $stderrLog

        if (-not (Wait-BackendReady -Url $smokeBaseUrl -TimeoutSeconds 30)) {
            Write-Host "No se pudo levantar el backend temporal. Logs:" -ForegroundColor Yellow
            if ($stdoutLog -and (Test-Path $stdoutLog)) {
                Write-Host "stdout: $stdoutLog"
            }
            if ($stderrLog -and (Test-Path $stderrLog)) {
                Write-Host "stderr: $stderrLog"
            }
            throw "Backend temporal no disponible en $smokeBaseUrl"
        }

        Write-Host "Backend temporal levantado por este wrapper." -ForegroundColor Green
    }
    else {
        throw "No hay backend respondiendo en $smokeBaseUrl. Reintenta con -StartServer o usa una URL valida."
    }

    Write-Step "[4/5] Ejecutando smoke test operativo reutilizando run_operational_flow_check.py ..."
    $flowArgs = @(
        "scripts/run_operational_flow_check.py",
        "--base-url", $smokeBaseUrl,
        "--username", $resolvedUsername,
        "--password", $resolvedPassword
    )
    if ($DeviceCode) {
        $flowArgs += @("--device-code", $DeviceCode)
    }
    if ($DeviceToken) {
        $flowArgs += @("--device-token", $DeviceToken)
    }

    & $pythonPath @flowArgs
    $flowExitCode = $LASTEXITCODE

    Write-Step "[5/5] Smoke test finalizado."
    if ($flowExitCode -eq 0) {
        Write-Host "Operational smoke test completado correctamente." -ForegroundColor Green
    }
    else {
        Write-Host "Operational smoke test fallo con exit code $flowExitCode." -ForegroundColor Red
    }

    exit $flowExitCode
}
finally {
    if ($startedProcess -and -not $startedProcess.HasExited) {
        Write-Host "Deteniendo backend temporal (PID=$($startedProcess.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $startedProcess.Id -Force
    }

    if ($null -ne $previousDatabaseUrl) {
        $env:DATABASE_URL = $previousDatabaseUrl
    }
    else {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    }

    Pop-Location
}