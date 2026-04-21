#!/bin/bash
# Script interno de lanzamiento para autoarranque de Rita_NEW2
# Inicia la infraestructura, el backend y abre el dashboard en modo Kiosko.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$PROJECT_DIR/.venv/bin/activate"

# 1. Iniciar todo el sistema (Docker + Backend + Edge)
# Usamos el script que ya creamos
bash "$PROJECT_DIR/scripts/start-rita.sh" &

# 2. Esperar a que el Dashboard Flutter Web esté listo (puerto 5190)
echo "[AUTOSTART] Esperando al Dashboard..."
until curl -s http://localhost:5190 > /dev/null; do
    sleep 2
done

# 3. Abrir Chromium en modo Kiosko apuntando al Dashboard
# Usamos autologin para que no pida clave al arrancar en la Pi
URL="http://localhost:5190/#/autologin"

if command -v chromium-browser &> /dev/null; then
    chromium-browser --noerrdialogs --disable-infobars --kiosk "$URL"
else
    chromium --noerrdialogs --disable-infobars --kiosk "$URL"
fi
