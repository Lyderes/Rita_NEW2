# RITA — SeniorCare Intelligence Assistant

RITA is an advanced intelligence layer for remote caregiver support. It transforms raw behavioral signals and health check-ins into humanized, actionable daily interpretations, providing peace of mind through technology.

---

## 🏗️ Core Architecture
RITA uses a modern, **request-driven flow with event ingestion**:
- **Backend (FastAPI)**: Core intelligence engine (Scoring, Analysis, Humanization).
- **Frontend (Flutter Web)**: Caregiver dashboard for daily wellness assessments.
- **Infrastructure (Docker)**: Canonical storage via **PostgreSQL** and MQTT event ingestion.
- **AI Layer**: Anthropic Claude or local rule-based fallback for risk detection.

---

## 🚀 One-Command Startup
Get RITA running in under 10 minutes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-rita.ps1
```

**This command orchestrates:**
1.  Docker Infrastructure (PostgreSQL + MQTT).
2.  Database Sync (Alembic Migrations).
3.  Seed Data (Baseline & Demo profiles).
4.  Service Launch (Backend @ 8080, Frontend @ 5190).
5.  Interactive CLI for event simulation.

---

## 📋 Standard Ports & Access

| Component | Port | Credentials |
|-----------|------|-------------|
| **Dashboard** | `5190` | `admin` / `admin123` |
| **Backend API** | `8080` | [Swagger UI](http://localhost:8080/docs) |
| **PostgreSQL** | `5434` | `postgres` / `postgres` |
| **MQTT** | `1883` | N/A |

---

## 📖 Documentation Center
For a detailed deep dive into RITA's internal systems, visit the **[/docs](/docs/index.md)** center:

- **[Mental Model & Architecture](/docs/architecture.md)**: Narrative > Score.
- **[Daily Scoring & Recovery](/docs/scoring-system.md)**: Mixed Day logic.
- **[Humanization Layer](/docs/humanization.md)**: Why we avoid medical tone.
- **[API Reference](/docs/api.md)**: Endpoints and examples.
- **[Decision Log](/docs/decisions.md)**: Trade-offs and design rationales.

---
*Developed for Lyderes / SeniorCare MVP Project.*
