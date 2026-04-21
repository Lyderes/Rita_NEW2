#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 1. LIMPIEZA: Matamos cualquier proceso viejo de Rita para liberar los sensores
echo "[AUTOSTART] Limpiando procesos antiguos..."
sudo pkill -9 python3
sudo pkill -9 chromium
sleep 2

# 2. Iniciar Servidor de Imagen (La pantalla negra)
echo "[AUTOSTART] Iniciando servidor de imagen..."
source "$PROJECT_DIR/.venv/bin/activate"
python3 "$PROJECT_DIR/rita/edge/src/ui_server.py" &
sleep 3

# 3. Iniciar el Cerebro de Rita (Voz y Sensores)
echo "[AUTOSTART] Iniciando voz y sensores..."
bash "$PROJECT_DIR/scripts/start-rita.sh" &
sleep 5

# 4. Abrir la Pantalla en modo Kiosko (Comando corregido para tu Pi)
URL="http://localhost:5000"
echo "[AUTOSTART] Abriendo interfaz local..."

# Intentamos primero con 'chromium' y si falla con 'chromium-browser'
if command -v chromium &> /dev/null; then
    chromium --noerrdialogs --disable-infobars --kiosk "$URL"
else
    chromium-browser --noerrdialogs --disable-infobars --kiosk "$URL"
fi
