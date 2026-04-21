# Frontend & Dashboard

RITA's Frontend is a Flutter Web Dashboard designed for professional caregivers.

## Caregiver Home
The home screen provides a high-level overview of all supervised seniors:
- **Daily Score**: A color-coded metric (0-100) indicating current wellness.
- **Humanized Narrative**: A one-line summary of the "evolving story" for that person today.
- **Device Connectivity**: Real-time status based on heartbeat signals.

## Daily Score Display Hierarchy
When a caregiver views a user's details, the information is presented in order of importance:

1.  **The Narrative Summary**: (e.g., *"Aunque ha tenido momentos de malestar, parece encontrarse mejor ahora"*). This is the absolute source of truth.
2.  **The Professional Interpretation**: (e.g., *"Es buena señal que la situación se haya aliviado. Conviene confirmar si necesita algo..."*). Actionable advice.
3.  **The Global Score**: A numeric trend (e.g., 85/100).
4.  **Sub-Scores & Factors**: Breakdowns (Mood, Activity, Routine) and specific contributing signals (Pain, Dizziness).

## Data Consumption Protocol

The frontend is built to be resilient and responsive:
- **Polling**: Updates are fetched every 5-15 seconds depending on the criticality of the data.
- **Status Mapping**:
    - `critical`: High risk incident open.
    - `alert`: Medium risk incident or significant score drop.
    - `ok`: Everything within normal baseline parameters.

## Integration Rules
- **No Manual Calculation**: The frontend should NEVER compute scores or interpretations; it simply displays what the Backend provides.
- **Last State Priority**: UI elements should always highlight the most recent interaction, especially if it indicates a "Recovery" or a new "Deviation."
