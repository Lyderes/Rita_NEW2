param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Username = "admin",
    [string]$Password = "admin123",
    [switch]$SkipBackendBuild = $false
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$validateScript = Join-Path -Path $projectRoot -ChildPath "backend\scripts\validate_events_flow.ps1"

if (-not (Test-Path $validateScript)) {
    Write-Host "[FAIL] No se encontro validate_events_flow.ps1 en backend/scripts" -ForegroundColor Red
    exit 1
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host "" 
    Write-Host ("[STEP] " + $Name) -ForegroundColor Cyan
    try {
        & $Action
        Write-Host ("[OK] " + $Name) -ForegroundColor Green
    }
    catch {
        Write-Host ("[FAIL] " + $Name) -ForegroundColor Red
        Write-Host $_ -ForegroundColor Red
        throw
    }
}

Push-Location $projectRoot
try {
    Invoke-Step -Name "Levantar Postgres + MQTT" -Action {
        docker compose up -d postgres mqtt | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "docker compose up -d postgres mqtt fallo" }
    }

    Invoke-Step -Name "Levantar Backend Docker" -Action {
        if ($SkipBackendBuild) {
            docker compose up -d backend | Out-Host
        }
        else {
            docker compose up -d --build backend | Out-Host
        }
        if ($LASTEXITCODE -ne 0) { throw "docker compose up backend fallo" }
    }

    Invoke-Step -Name "Aplicar migraciones (alembic upgrade head)" -Action {
        docker compose exec -T backend python -m alembic upgrade head | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "alembic upgrade head fallo" }
    }

    Invoke-Step -Name "Esperar health backend" -Action {
        $maxAttempts = 30
        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            try {
                $resp = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/health" -TimeoutSec 3
                if ([int]$resp.StatusCode -eq 200) {
                    return
                }
            }
            catch {
                Start-Sleep -Seconds 2
                continue
            }
            Start-Sleep -Seconds 2
        }
        throw "Backend no respondio healthy en $BaseUrl/health"
    }

    Invoke-Step -Name "Validacion E2E backend (validate_events_flow)" -Action {
        powershell -ExecutionPolicy Bypass -File $validateScript -BaseUrl $BaseUrl -Username $Username -Password $Password | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "validate_events_flow fallo" }
    }

    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host "RITA backend+infra smoke final: OK" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Red
    Write-Host "RITA backend+infra smoke final: FAIL" -ForegroundColor Red
    Write-Host "==============================================" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
