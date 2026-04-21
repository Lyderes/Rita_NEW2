
# LEGACY/DEPRECATED: Script wrapper para Flutter. Usar comandos estándar de Flutter directamente.
param(
    [ValidateSet("web", "android", "test", "doctor", "get", "clean")]
    [string]$Mode = "web",
    [string]$WebHost = "127.0.0.1",
    [int]$WebPort = 5173
)

$ErrorActionPreference = "Stop"

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

$flutter = Get-FlutterCommand
$mobileRoot = Split-Path -Parent $PSScriptRoot
$pubspecPath = Join-Path -Path $mobileRoot -ChildPath "pubspec.yaml"

if (-not (Test-Path $pubspecPath)) {
    throw "No se encontro pubspec.yaml en: $mobileRoot"
}

function Invoke-FlutterStep {
    param(
        [string]$StepName,
        [string[]]$Arguments
    )

    Write-Host ('[RUN] ' + $StepName) -ForegroundColor Cyan
    & $flutter @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ('Fallo en: ' + $StepName)
    }
    Write-Host ('[OK] ' + $StepName) -ForegroundColor Green
}

Push-Location $mobileRoot
try {
    switch ($Mode) {
        "doctor" {
            Invoke-FlutterStep -StepName "flutter doctor" -Arguments @("doctor")
        }
        "get" {
            Invoke-FlutterStep -StepName "flutter pub get" -Arguments @("pub", "get")
        }
        "clean" {
            Invoke-FlutterStep -StepName "flutter clean" -Arguments @("clean")
            Invoke-FlutterStep -StepName "flutter pub get" -Arguments @("pub", "get")
        }
        "test" {
            Invoke-FlutterStep -StepName "flutter test" -Arguments @("test")
        }
        "android" {
            Invoke-FlutterStep -StepName "flutter pub get" -Arguments @("pub", "get")
            Write-Host "[RUN] flutter run (android/default device)" -ForegroundColor Cyan
            & $flutter run
            if ($LASTEXITCODE -ne 0) {
                throw "Fallo en flutter run (android/default device)"
            }
        }
        "web" {
            Invoke-FlutterStep -StepName "flutter pub get" -Arguments @("pub", "get")
            Write-Host ''
            Write-Host '╔════════════════════════════════════════════════════════╗' -ForegroundColor Yellow
            Write-Host '║ CONVENCIÓN ACTUAL - VALIDAR ANTES DE ARRANCAR       ║' -ForegroundColor Yellow
            Write-Host '╚════════════════════════════════════════════════════════╝' -ForegroundColor Yellow
            Write-Host '[FRONTEND] http://$WebHost`:$WebPort' -ForegroundColor Magenta
            Write-Host '[BACKEND] http://localhost:8000 (esperado)' -ForegroundColor Magenta
            Write-Host '[CORS ALLOWED] 5173 + 5180' -ForegroundColor Magenta
            Write-Host ''
            Write-Host '[INFO] URL esperada: http://$WebHost`:$WebPort' -ForegroundColor Yellow
            Write-Host '[RUN] flutter run -d chrome' -ForegroundColor Cyan
            & $flutter run -d chrome --web-hostname $WebHost --web-port $WebPort --dart-define-from-file=.env.firebase
            if ($LASTEXITCODE -ne 0) {
                throw "Fallo en flutter run -d chrome"
            }
        }
        default {
            throw "Modo no soportado: $Mode"
        }
    }
}
finally {
    Pop-Location
}
