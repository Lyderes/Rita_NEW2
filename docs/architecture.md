# Architecture

RITA follows a **request-driven architecture with event ingestion**, optimized for local development and high-fidelity health monitoring.

## Mental Model: How to Think About RITA

To understand RITA, keep these core principles in mind:

1.  **Baseline as Reference**: RITA doesn't evaluate users against universal constants. Instead, it compares current activity against a **Baseline Profile** (usual mood, energy levels, routine). A "low" score for one person might be a "normal" day for another.
2.  **Deviations, Not Absolute Values**: We look for changes. A sudden drop in mood or a missed check-in is more significant than a consistently low but stable state.
3.  **The Day as an Evolving Story**: Activity is not just a sum of points. We treat the day as a narrative that can change. An early morning fall followed by a positive afternoon check-in is a "Mixed Day" or "Recovery Case," not just a "Bad Day."
4.  **Narrative > Score**: Technical scores (0-100) are internal metrics. The **Humanized Narrative** found in the dashboard is the primary source of truth for caregivers, providing the context that a raw number cannot.

## System Components

### 1. Infrastructure (Docker)
- **PostgreSQL (Port 5434)**: The canonical source of truth. Stores events, baseline profiles, daily scores, and audit logs.
- **Mosquitto MQTT (Port 1883)**: Handles incoming event ingestion from edge devices with at-least-once delivery guarantees.

### 2. Backend (FastAPI - Port 8080)
The "Brain" of the system.
- **Event Service**: Processes incoming signals (check-ins, falls, requests).
- **Analysis Service**: Uses LLMs (Anthropic Claude or Local fallback) to extract risk signals from text/speech.
- **Scoring Service**: Computes the `DailyScore` based on events and baseline deviations.

### 3. Frontend (Flutter Web - Port 5190)
The "Interface" for caregivers.
- **Dashboard**: High-level view of all supervised users.
- **User Detail**: Deep dive into the narrative, scoring trends, and recent activity.

### 4. AI Analysis Layer
- **Cloud AI (Anthropic)**: Primary engine for high-quality sentiment and risk analysis.
- **Local Fallback**: Rule-based logic ensures the system remains functional even without internet connectivity or API access.

## Event Flow

1.  **Ingestion**: An edge device or simulation tool sends an event via MQTT or REST (`POST /events`).
2.  **Analysis**: If the event contains text (check-in), it is analyzed for signals (pain, dizziness, etc.).
3.  **Hardening**: Signals are normalized and persisted as `CheckInAnalysis`.
4.  **Scoring**: The `DailyScoringService` is triggered, recomputing the score and narrative based on the latest context.
5.  **Visualization**: The Dashboard pulls the updated narrative and score for the caregiver.
