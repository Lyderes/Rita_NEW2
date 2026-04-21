#!/bin/bash
# Script para preparar el entorno de RITA Edge en Raspberry Pi (Linux).
# Optimiza la inferencia del LLM para arquitectura ARM.

set -e

echo "=== Setup RITA Edge para Raspberry Pi / Linux ==="

# 1. Instalar dependencias del sistema
echo "[STEP 1] Instalando dependencias de compilación y audio..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip python3-venv \
    build-essential cmake \
    libopenblas-dev \
    portaudio19-dev python3-pyaudio \
    libasound2-dev

# 2. Crear Entorno Virtual
VENV_PATH="$HOME/rita-venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "[STEP 2] Creando entorno virtual en $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

# 3. Instalar dependencias de Python
echo "[STEP 3] Instalando dependencias de Python..."
pip install --upgrade pip
pip install -r ../requirements.txt

# 4. Compilar llama-cpp-python optimizado para ARM (NEON + OpenBLAS)
echo "[STEP 4] Compilando llama-cpp-python con aceleración ARM..."
CMAKE_ARGS="-DGGML_OPENBLAS=ON" pip install llama-cpp-python[server] --upgrade --force-reinstall --no-cache-dir

echo "----------------------------------------------------"
echo "[OK] Setup completado."
echo "Para iniciar el servidor LLM en Rpi:"
echo "source $VENV_PATH/bin/activate"
echo "python3 -m llama_cpp.server --model ../models/tiny_model.gguf --n_ctx 1024 --n_threads 4"
echo ""
echo "NOTA: Para Raspberry Pi se recomienda usar modelos pequeños (ej: TinyLlama-1.1B o Phi-3-mini)."
echo "----------------------------------------------------"
