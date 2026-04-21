#!/bin/bash
echo "Configurando arranque automático para Rita_NEW2..."

# Intentar detectar la ruta del proyecto (asumiendo que se ejecuta desde el proyecto)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Asegurar permisos de ejecución
chmod +x "$PROJECT_DIR/scripts/launch_rita_new2.sh"
chmod +x "$PROJECT_DIR/scripts/start-rita.sh"

echo "[INFO] Preparando entorno Python (esto puede tardar unos minutos)..."
# Ejecutamos solo la parte de preparación del script de inicio
# (esto creará el venv e instalará dependencias si no están)
bash "$PROJECT_DIR/scripts/start-rita.sh" --setup-only || true

# 1. Configurar Wayfire (Raspberry Pi OS Bookworm)
if [ -f ~/.config/wayfire.ini ]; then
    if ! grep -q "rita_startup =" ~/.config/wayfire.ini; then
        echo -e "\n[autostart]\nrita_startup = $PROJECT_DIR/scripts/launch_rita_new2.sh" >> ~/.config/wayfire.ini
        echo "¡Autoarranque configurado en Wayfire!"
    else
        echo "El autoarranque ya estaba configurado en Wayfire."
    fi
fi

# 2. Configurar Autostart Universal (X11)
mkdir -p ~/.config/autostart
# Ajustar la ruta en el .desktop dinámicamente
sed "s|Exec=.*|Exec=/bin/bash $PROJECT_DIR/scripts/launch_rita_new2.sh|" "$PROJECT_DIR/scripts/Rita_NEW2.desktop" > ~/.config/autostart/Rita_NEW2.desktop
chmod +x ~/.config/autostart/Rita_NEW2.desktop
echo "¡Archivo .desktop copiado a ~/.config/autostart!"

# 3. Acceso directo en el Escritorio
if [ -d ~/Desktop ]; then
    cp ~/.config/autostart/Rita_NEW2.desktop ~/Desktop/
    chmod +x ~/Desktop/Rita_NEW2.desktop
    echo "Acceso directo creado en el Escritorio."
fi

echo "Proceso de configuración de autoarranque finalizado."
echo "Reinicia la Raspberry Pi para verificar."
