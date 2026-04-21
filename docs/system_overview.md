# RITA: Technical System Documentation
**Date:** March 27, 2026
**Version:** 1.0 (Current Implementation)
**Status:** Source of Truth for Hardware Integration

---

## 1. System Overview
RITA is a professional, warm, and proactive AI companion designed for the elderly and their caregivers. 

*   **Purpose:** To provide emotional support, routine monitoring, and emergency detection through natural voice interaction.
*   **Positioning:** **Non-medical**. RITA facilitates companionship and monitoring but does not provide medical diagnoses or prescriptions.
*   **Target Users:** 
    *   **Elderly:** Primary users interacting via voice/text on an edge device.
    *   **Caregivers:** Secondary users monitoring wellbeing via a digital dashboard.

---

## 2. Current Architecture
The system follows a distributed topology with local and containerized services.

### 2.1 Topology
*   **PostgreSQL:** Database engine running in Docker. Accessed via `localhost:5434`.
*   **MQTT (Mosquitto):** Messaging broker for edge-to-backend communication. Accessed via `localhost:1883`.
*   **Backend (FastAPI):** Core business logic and API. Running locally on `http://localhost:8080`.
*   **Frontend (Flutter Web):** Caregiver dashboard. Running locally on `http://localhost:5190`.
*   **LLM Server (llama.cpp):** Local inference engine for natural language. Accessed via `http://localhost:8001`.
*   **Edge (RITA CLI):** Interactive client for user communication.

### 2.2 Communication & Dependencies
*   **Edge → Backend:** Communicates via REST API (`/events`) and MQTT for telemetry.
*   **Backend → DB:** Uses SQLAlchemy ORM to manage state in PostgreSQL.
*   **Edge → LLM Server:** Communicates via OpenAI-compatible API for complex conversation turns.
*   **Frontend → Backend:** Consumes REST endpoints for real-time dashboard updates.

---

## 3. Startup Flow
The system is orchestrated via `scripts/start-rita.ps1`.

### 3.1 Startup Sequence
1.  **Environment Check:** Verifies Docker and Python virtual environments.
2.  **Port Cleanup:** Force-kills processes on 8080, 5190, 8001, 5434, and 1883 (excluding Docker system processes).
3.  **Infrastructure Launch:** `docker compose up -d postgres mqtt`.
4.  **DB Alignment:** Runs `alembic upgrade head` and `scripts/seed_db.py`.
5.  **Backend Launch:** Starts FastAPI via `uvicorn`.
6.  **LLM Launch:** Starts `llama-cpp-python` server with the local GGUF model.
7.  **Readiness Validation:** 
    *   Backend `/health` check.
    *   LLM `/v1/models` check.
    *   **Anti-Mock Verification:** Executes a real test completion to ensure the LLM is initialized and not returning simulated responses.
8.  **MQTT Consumer:** Starts the background worker for edge telemetry.
9.  **Frontend Launch:** Starts Flutter Web in Chrome.
10. **CLI Launch:** Launches the interactive text-mode assistant.

---

## 4. Backend (Detailed)
Built with **Python 3.12+, FastAPI, SQLAlchemy, and Alembic**.

### 4.1 Key Modules
*   **Events:** Central hub for all system activity.
*   **Incidents:** Manages emergency states (e.g., falls).
*   **Alerts:** Notifications triggered by critical events or scoring deviations.
*   **Daily Score:** Logic for calculating the user's wellbeing status.
*   **Reminders:** Scheduling and triggering routine alerts.

### 4.2 Database Logic
*   **Idempotency:** All events require a `trace_id` (UUID) to prevent duplication during retransmission.
*   **Persistence:** PostgreSQL provides the source of truth; SQLite is no longer used for production-grade runs.
*   **Deduplication:** The backend enforces uniqueness on `trace_id` at the database level.

### 4.3 Core Enums
*   `EventTypeEnum`: `checkin`, `emergency`, `fall`, `reminder_triggered`, `wellbeing_check_failed`, etc.
*   `SeverityEnum`: `low`, `medium`, `high`, `critical`.

---

## 5. Daily Score System
A numeric representation (0–100) of the user's daily status.

### 5.1 Calculation Logic
The score starts at 100 and applies penalties based on:
*   **Check-in Analysis:** Detected signals like `pain`, `dizziness`, `confusion`, or `tiredness`.
*   **Routine Adherence:** Penalties for missed or late reminders.
*   **Tone & Stability:** Lower scores for persistent negative signals; recovery detection for improved mood.

### 5.2 Inputs & Outputs
*   **Inputs:** `CheckInAnalysis` (from conversation), `ScheduledReminder` adherence, `UserBaseline`.
*   **Outputs:** 
    *   `global_score`: Main percentage.
    *   `observed_routines`: List of completed tasks.
    *   `missed_or_late_routines`: List of deviations.
    *   `narrative_summary`: Natural language explanation for caregivers.

---

## 6. Reminder System
Manages recurring tasks (medication, hydration, meals).

*   **Model:** `ScheduledReminder` includes `time_of_day`, `days_of_week`, and `reminder_type`.
*   **Trigger Service:** `ReminderTriggerService` evaluates active reminders every minute.
*   **Idempotency:** Uses `last_triggered_at` to ensure a reminder only fires once per day.
*   **Event Generation:** Triggers a `reminder_triggered` event sent to the edge for delivery.

---

## 7. Conversation System
The heart of RITA's interaction logic, found in `rita/edge/src/conversation/`.

### 7.1 The Turn Pipeline (`VoiceAssistant.run_turn()`)
1.  **Exit Detection:** Matches "adios", "terminar", etc., to close the session.
2.  **Risk Detection:** Uses `KeywordDetector` to find immediate emergency signals.
3.  **Intent Routing (Fast Paths):** Uses `intent_router.py` for instant empathetic responses without LLM latency.
4.  **LLM Fallback:** If no fast path matches, calls the local llama.cpp server.

### 7.2 Fast Paths
Covers 25+ common scenarios including:
*   Physical symptoms (headache, dizziness, back pain).
*   Emotional states (sadness, loneliness, boredom).
*   Identity ("Who are you?") and gratitude ("Thank you").
*   Humor/Joke requests.

### 7.3 LLM Configuration & Rules
*   **Context:** System prompt enforces a warm, 1-2 sentence response.
*   **Constraints:** Max 1 question per turn, non-technical language.
*   **Human Fallback:** If the LLM times out or errors, RITA says: *"Ahora mismo me cuesta un poco concentrarme, pero sigo aquí contigo. ¿Me lo puedes repetir de otra forma, por favor?"*

---

## 8. Event System
Every interaction is captured as a structured event.

*   **Generation:** Triggered by user speech, assistant responses, or system timers.
*   **Storage:** Persisted in the `events` table with full `user_text` and `rita_text`.
*   **Human Description:** The `Event` model features a `human_description` property that converts raw data into phrases like *"Mencionó mareo"* or *"No respondió al contacto de RITA"*.

---

## 9. Frontend (Flutter)
The Caregiver Dashboard provides a "narrative-first" view.

*   **WellnessScoreCard:** Displays the global score and primary factors.
*   **RoutineStatusCard:** Summarizes completed and missed routines.
*   **Narrative Focus:** Prioritizes the `narrative_summary` and `interpretation` fields from the `DailyScore` to reduce cognitive load for caregivers.

---

## 10. Current Limitations
*   **Latency:** Local CPU-based LLM inference takes 1–3 seconds per turn.
*   **Hardware:** Still running on PC/Mac; Raspberry Pi GPIO and specific audio hardware support are pending.
*   **Audio Pipeline:** STT (Vosk) and TTS (pyttsx3) are implemented but not yet optimized for streaming or noisy environments.

---

## 11. Edge (CLI & Preparation)
The edge component currently lives in `rita/edge/`. It operates in both text-only (CLI) and voice-enabled modes. The Raspberry Pi integration will inherit the `VoiceAssistant` logic, replacing the text input/output with the physical audio stack.

---

## 12. End-to-End Data Flow Example
**Scenario: User says *"Me duele la cabeza"* (I have a headache)**

1.  **Edge:** `VoiceAssistant` detects intent via `intent_router`.
2.  **Fast Path:** Returns an empathetic response instantly: *"Siento que te duela la cabeza. Descansa en un lugar tranquilo..."*
3.  **Persistence:** Edge sends a `checkin` event with `user_text` and `rita_text` to Backend `/events`.
4.  **Backend:** Event is saved; `DailyScore` is recomputed for today.
5.  **Dashboard:** Caregiver sees a score drop and a narrative: *"Aunque ha mencionado algún malestar leve, el día transcurre de forma bastante tranquila."*

---

## 13. Configuration & Ports
| Service | Port | Protocol | Path |
| :--- | :--- | :--- | :--- |
| Backend | 8080 | HTTP | `backend/` |
| Frontend | 5190 | HTTP | `mobile/` |
| LLM Server | 8001 | HTTP | `rita/models/` |
| PostgreSQL | 5434 | TCP | `docker-compose.yml` |
| MQTT | 1883 | TCP | `docker-compose.yml` |

---

## 14. Repository Structure
*   `backend/`: FastAPI application, migrations, and services.
*   `mobile/`: Flutter web application for caregivers.
*   `rita/edge/`: Python source for the local assistant (conversation, STT, TTS).
*   `scripts/`: PowerShell orchestration and DB utilities.
*   `models/`: Storage for the GGUF LLM model (ignored by git).
