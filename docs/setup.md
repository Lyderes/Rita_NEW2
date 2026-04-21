# Setup & Installation

RITA is designed for a seamless local development experience using a unified orchestration script.

## Prerequisites

- **Docker Desktop**: Required for PostgreSQL and MQTT infrastructure.
- **Python 3.10+**: For the Backend and CLI tools.
- **Flutter SDK**: For the Mobile/Web Dashboard.
- **PowerShell**: Used for the primary startup orchestration.

## One-Command Startup

The quickest way to get RITA running is to use the provided PowerShell script from the root directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-rita.ps1
```

### What this script does:
1. **Infrastructure**: Spins up PostgreSQL and Mosquitto MQTT via Docker Compose.
2. **Database**: Waits for PostgreSQL to be ready and applies all Alembic migrations.
3. **Seed Data**: Populates the database with baseline profiles and demo users.
4. **Backend**: Launches the FastAPI server (Port 8080).
5. **Frontend**: Launches the Flutter Web Dashboard (Port 5190).
6. **CLI**: Initiates the RITA Interactive CLI for testing event ingestion.

## 🧠 AI Environment Setup (Mandatory)

Before running the main script, you must prepare the Local AI environment to avoid dependency issues on Windows (especially with Python 3.14+):

1.  **Create the AI Venv**: Run the specialized setup script to build `llama-cpp-python` in a stable environment:
    ```powershell
    powershell -ExecutionPolicy Bypass -File .\rita\scripts\setup-llama-cpp.ps1
    ```
2.  **Download the Model**: Place a GGUF model (e.g., Mistral-7B or similar) in:
    `rita/models/model.gguf`
    *(The orchestrator will look for exactly this path).*

## Standard Ports

| Component | Port | Interface |
|-----------|------|-----------|
| **Backend API** | `8080` | REST API (FastAPI) |
| **Frontend UI** | `5190` | Flutter Web Dashboard |
| **PostgreSQL** | `5434` | DB Storage |
| **MQTT** | `1883` | Event Ingestion Broker |

## Backend Configuration

The backend looks for a `.env` file in the `backend/` directory. 
1. Copy `backend/.env.example` to `backend/.env`.
2. Update `ANTHROPIC_API_KEY` if you want to use AI-powered analysis.
3. Ensure `DATABASE_URL` points to `postgresql+psycopg://postgres:postgres@localhost:5434/rita`.

## Quick Troubleshooting

### Port Conflicts
If a port is already in use (e.g., `8080` or `5434`):
- **Windows**: Use `netstat -ano | findstr :8080` to find the Process ID (PID) and kill it via Task Manager or `taskkill /F /PID <PID>`.
- **Change Ports**: Update `docker-compose.yml` for infrastructure and the environment variables for services.

### Docker Failures
- Ensure Docker Desktop is running and you have enough resources (RAM/CPU) allocated.
- Run `docker compose down -v` to wipe volumes if the database state becomes corrupted.

### Migration Issues
- If `alembic` fails, ensure your `.env` is correct and PostgreSQL is reachable.
- Run `python -m alembic upgrade head` manually inside the `backend/` folder to debug.

### Flutter Build Errors
- If the dashboard fails to load, try `flutter clean` then `flutter run -d chrome --web-port 5190` inside the `mobile/` directory.
