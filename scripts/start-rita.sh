#!/bin/bash

# Script principal para iniciar RITA en Linux / Raspberry Pi.
# Orquestra Docker (Postgres/MQTT) y los componentes locales.

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_ROOT="$PROJECT_ROOT/backend"
RITA_ROOT="$PROJECT_ROOT/rita"

# Procesar argumentos
SETUP_ONLY=false
if [ "$1" == "--setup-only" ]; then
    SETUP_ONLY=true
fi

echo -e "\n=== Lanzador RITA: Edición Raspberry Pi (Edge) ==="
echo "--------------------------------------------------------"

# 1. Verificar configuración remota
if [ -f "rita/.env" ]; then
    source rita/.env
else
    echo "[!] Advertencia: No se encontró rita/.env. Usando valores por defecto."
fi

# Intentar ping al Docker Central para estado visual
MQTT_HOST=${MQTT_HOST:-"10.7.21.13"}
if ping -c 1 -W 1 "$MQTT_HOST" &> /dev/null; then
    echo -e "ESTADO: [\033[0;32m INTERNET / ONLINE \033[0m] -> Conectado a $MQTT_HOST"
else
    echo -e "ESTADO: [\033[0;31m PI / OFFLINE \033[0m] -> Guardando en Buffer Local"
fi
echo "--------------------------------------------------------"

# 2. Sincronizar Base de Datos y Entorno Virtual
echo "[STEP 2] Configurando entorno Python y sincronizando base de datos..."
cd "$PROJECT_ROOT"

# Crear venv si no existe
if [ ! -d ".venv" ]; then
    echo "[INFO] Creando entorno virtual .venv..."
    python3 -m venv .venv
fi

# Activar entorno
source .venv/bin/activate

# Instalar/Actualizar dependencias
echo "[INFO] Asegurando dependencias..."
pip install -q --upgrade pip
pip install -q -r backend/requirements.txt
pip install -q -r rita/requirements.txt

cd "$BACKEND_ROOT"
if [ -f ".env.example" ] && [ ! -f ".env" ]; then
    cp .env.example .env
fi

export PYTHONPATH="."
python3 -m alembic upgrade head
python3 scripts/seed_db.py

if [ "$SETUP_ONLY" = true ]; then
    echo "[OK] Configuración finalizada. Saliendo."
    exit 0
fi

# 5. Iniciar Backend (en segundo plano usando el venv)
echo "[STEP 3] Iniciando Backend FastAPI..."
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > backend.log 2>&1 &
echo "[OK] Backend corriendo en puerto 8080 (ver backend.log)"

# 6. Iniciar MQTT Consumer
echo "[STEP 4] Iniciando MQTT Consumer..."
nohup python3 scripts/run_mqtt_consumer.py > mqtt_consumer.log 2>&1 &
echo "[OK] MQTT Consumer corriendo en segundo plano."

# 7. Iniciar RITA Edge (Asistente de Voz y Sensores)
echo "[STEP 5] Iniciando RITA Edge Assistant..."
cd "$RITA_ROOT"
export PYTHONPATH="$RITA_ROOT/edge"
# Ejecutamos el nuevo main_edge.py que unifica todo
python3 edge/src/main_edge.py
