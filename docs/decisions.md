# Architecture Decisions

This document outlines key technical decisions and the trade-offs considered during the development of RITA.

## 1. PostgreSQL Migration (from SQLite)
- **Decision**: Move the canonical database from SQLite to PostgreSQL.
- **Rationale**: Ensure data integrity, support concurrent access, and align with production environments.
- **Trade-offs**: 
    - **Pros**: Robustness, better transaction handling, ready for multi-tenant growth.
    - **Cons**: Requires Docker infrastructure during local development, slightly more complex setup.

## 2. AI Fallback Strategy (Rule-Based)
- **Decision**: Implement a rule-based matching system when the primary AI (Anthropic) fails or is disabled.
- **Rationale**: Maintain basic health monitoring even in offline or low-connectivity scenarios.
- **Trade-offs**:
    - **Pros**: Continuous reliability, 0% failure rate for basic detection.
    - **Cons**: Less semantic understanding in complex check-ins; relies on high-quality keyword mapping.

## 3. Narrative-First Narrative Design
- **Decision**: Prioritize the **Humanized Narrative** over the numeric score in the UI.
- **Rationale**: Reduce caregiver anxiety and provide context for mixed or recovering health states.
- **Trade-offs**:
    - **Pros**: Better user experience for non-technical caregivers, fewer "False Alarms."
    - **Cons**: Requires more sophisticated backend logic to keep the narrative and score in perfect sync.

## 4. One-Command Setup (start-rita.ps1)
- **Decision**: Automate all service initialization through a single PowerShell script.
- **Rationale**: Ensure team reproducibility and a 10-minute "cloning to running" time.
- **Trade-offs**:
    - **Pros**: Fast onboarding, lower barrier to entry for new developers.
    - **Cons**: Maintenance cost for the setup script as architecture evolves.

## 5. Event Ingestion vs Task Queue
- **Decision**: Use a request-driven flow for Phase 1.0/3.5 instead of a complex Celery/Redis queue.
- **Rationale**: Keep the MVP architecture simple and local-first.
- **Trade-offs**:
    - **Pros**: Lower infrastructure footprint, easier debugging.
    - **Cons**: Limited scalability for thousands of concurrent check-ins (can be evolved to a queue later).
