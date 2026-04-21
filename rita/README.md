# RITA - Asistente de Voz Conversacional (MVP)

RITA es un asistente conversacional por voz en Python con proveedor LLM local llama.cpp server.

Arquitectura principal: RITA.
El stack de voz reutiliza componentes heredados ya adaptados al naming de RITA.

## Estructura

- `edge/src/audio`: captura de audio desde microfono
- `edge/src/stt`: transcripcion (Vosk local)
- `edge/src/tts`: sintesis de voz (pyttsx3)
- `edge/src/conversation`: orquestacion conversacional y cliente LLM
- `edge/src/safety`: deteccion de frases de riesgo
- `edge/src/integrations`: catalogo de adaptadores internos de RITA
- `cloud/src/*`: base para futuras capacidades cloud
- `shared/schemas`: contratos compartidos
- `scripts`: scripts de ejecucion en Windows

## Flujo MVP local

1. Microfono -> `audio/recorder.py`
2. WAV -> `stt/vosk_transcriber.py`
3. Prompt + memoria corta -> `conversation/prompts.py` + `conversation/session.py`
4. LLM local -> `conversation/llm_client.py` (llama.cpp server)
5. Respuesta por voz -> `tts/engine.py`

## Seguridad minima

`edge/src/safety/keyword_detector.py` detecta frases de riesgo:

- me he caido
- ayuda
- me encuentro mal
- llama a alguien

Cuando detecta riesgo, RITA devuelve una respuesta especial sin consultar LLM.

## Configuracion

1. Copia `config.yaml.example` a `config.yaml`
2. Ajusta proveedor LLM, modelo y ruta Vosk
3. Variables opcionales de entorno:
   - `LLM_BASE_URL`
   - `LLM_CHAT_ENDPOINT`
   - `LLM_MODEL`
   - `RITA_DEBUG_TIMING` (true/false para imprimir tiempos por etapa)

### Configuracion recomendada para llama.cpp server

En `config.yaml`:

```yaml
llm_base_url: "http://127.0.0.1:8001"
llm_chat_endpoint: "/v1/chat/completions"
llm_model: "model"
llm_timeout_s: 20
llm_temperature: 0.2
llm_max_tokens: 64
```

## Ejecucion en Windows (PowerShell)

### Modo texto (recomendado para primera prueba)

```powershell
cd rita
.\scripts\run-rita.ps1 -Mode text
```

### Modo voz

```powershell
cd rita
.\scripts\run-rita.ps1 -Mode voice
```

El script crea el entorno virtual en `%LOCALAPPDATA%\\rita-venv` para no dejar `.venv` dentro del codigo fuente.

## Requisitos previos

- Python 3.11+
- Modelo Vosk en `../models/vosk-model-small-es-0.42`

### Opcion A (recomendada): llama.cpp server

1. Preparar entorno e instalar dependencias:

```powershell
cd rita
.\scripts\setup-llama-cpp.ps1
```

2. Colocar modelo GGUF en:

`./models/model.gguf`

3. Arrancar servidor llama.cpp:

```powershell
cd rita
.\scripts\run-llama-server.ps1 -ModelPath .\models\model.gguf
```

4. Arrancar RITA:

```powershell
cd rita
.\scripts\run-rita.ps1 -Mode text
```

## Reutilizacion real del stack de voz

RITA reutiliza logica heredada de forma adaptada, no una arquitectura externa completa:

- `audio/recorder.py`: captura por bloques y parada por silencio (inspirado en `checkin/audio_recorder.py`)
- `tts/engine.py`: inicializacion lazy y seleccion robusta de voz (inspirado en `checkin/tts_engine.py`)
- `safety/keyword_detector.py`: deteccion regex por patrones (inspirado en `processing/keyword_detector.py`)

No se reutiliza directamente `processing/stt_engine.py` porque usa faster-whisper y el MVP de RITA requiere Vosk local, ya validado en tus pruebas previas.

## Entradas de salida

Comandos de salida soportados:

- salir
- adios
- terminar

## Alcance actual

Incluye solo el MVP conversacional local. No incluye app movil, panel web, scoring completo, sensores avanzados ni despliegue cloud final.

## Tests MVP

Ejecuta validaciones basicas desde `rita/`:

```powershell
python -m pytest tests -q
```
