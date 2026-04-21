
# LEGACY/DEPRECATED: Script para pruebas locales de RITA (modo texto/voz). No es parte del flujo operativo principal.
param(
    [ValidateSet("voice", "text")]
    [string]$Mode = "voice"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvPath = Join-Path $env:LOCALAPPDATA "rita-venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"

Set-Location $ProjectRoot

$NeedsSetup = $false

if (-not (Test-Path $VenvPath)) {
    py -m venv $VenvPath
    $NeedsSetup = $true
}

if (-not (Test-Path $PythonExe)) {
    throw "No se encontró Python dentro del entorno virtual: $PythonExe"
}

if ($NeedsSetup -or -not (Test-Path ".venv_ready")) {
    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -r requirements.txt
    "ok" | Set-Content ".venv_ready"
}

if (-not (Test-Path "config.yaml") -and (Test-Path "config.yaml.example")) {
    Copy-Item "config.yaml.example" "config.yaml"
}

if (-not (Test-Path "recordings")) {
    New-Item -Path "recordings" -ItemType Directory | Out-Null
}

$env:PYTHONPATH = (Join-Path $ProjectRoot "edge")

if ($Mode -eq "text") {
    & $PythonExe -m src.conversation.text_cli
} else {
    & $PythonExe -m src.conversation.cli
}
