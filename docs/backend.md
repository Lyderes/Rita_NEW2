# Backend Overview

The RITA Backend is a FastAPI-powered intelligence layer that orchestrates event processing, AI-driven analysis, and daily health scoring.

## Core Services

### 1. DailyScoringService
Responsible for computing the `DailyScore` and the humanized narrative for each user. It takes into account:
- Historical events for the current day.
- Risk signals from `CheckInAnalysis`.
- Baseline profiles for deviation detection.

### 2. CheckInAnalysisService
Orchestrates the analysis of incoming check-in text. It:
- Normalizes input transcripts.
- Calls the **ClaudeClient** (Anthropic) for semantic analysis.
- Supports **Rule-Based Fallback** if the AI is unavailable.
- Persists risk signals (pain, dizziness, etc.) for the scoring engine.

### 3. Base & Database layer
- **PostgreSQL**: The ONLY database for RITA. SQLite is deprecated for all operational flows.
- **SQLAlchemy 2.0+**: Used for modern, typed database interactions.
- **Alembic**: Manages schema migrations and ensuring the database is always in sync with models.

## Main Activity Flows

### Event Ingestion (Request-driven)
Events arrive via `POST /events` or from the MQTT bridge.
1. `EventService` validates and persists the raw event.
2. If `event_type == "checkin"`, `CheckInAnalysisService` is triggered.
3. Once analysis is complete, `DailyScoringService` recomputes the score and narrative for that user/day.

### Dashboard Polling
The frontend polls aggregate endpoints like `/users/{id}/overview` or `/dashboard`.
- These endpoints rely on pre-computed indices (or fast recomputation for the current day) to provide sub-second responses.

## Code Structure
```text
backend/
├── app/
│   ├── api/          # REST Endpoints (Dependencies, Routers)
│   ├── core/         # Config, Security, Middleware
│   ├── db/           # Session management, Base models
│   ├── models/       # SQLAlchemy models (User, Event, DailyScore, etc.)
│   ├── schemas/      # Pydantic models for validation
│   ├── services/     # Core Business Logic (Scoring, Analysis)
├── tests/            # High-coverage test suite (Pytest)
├── alembic/          # Database migration scripts
```
