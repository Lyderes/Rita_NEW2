# API Reference

The RITA API is a RESTful service (FastAPI) built to support real-time caregiver interactions and historical health analysis.

## Base URL
Local: `http://localhost:8080`

## Core Endpoints

### Event Ingestion
- **`POST /events`**: The primary entry point for all health signals (falls, check-ins, emergencies).
- **`POST /events/checkin`**: A simulation endpoint that accepts `user_id` and `text` to trigger the full analysis and scoring flow.

### Daily Scoring & Humanization
- **`GET /users/{user_id}/overview`**: Returns the most recent `DailyScore`, the Humanized Narrative, and recent events.
- **`GET /users/{user_id}/status`**: Returns the current status ("ok", "warning", "critical") for quick UI display.

### Device Connectivity
- **`POST /devices/{device_code}/heartbeat`**: Updates the device's online status.
- **`GET /devices/status`**: Lists all devices and their calculated connection state (`online`, `stale`, `offline`).

### Resource Management
- **`GET /incidents`**: List of all open or closed incidents.
- **`PATCH /incidents/{id}/close`**: Closes an incident with caregiver confirmation.
- **`GET /alerts`**: List of all system alerts.
- **`PATCH /alerts/{id}/acknowledge`**: Marks an alert as acknowledged.

## Request Lifecycle

1.  **Tracing**: Every request is assigned a `X-Request-ID` for cross-service logging.
2.  **Authentication**: Protected endpoints (caregiver functions) require a **Bearer JWT Token**.
3.  **Validation**: Pydantic models ensure all inputs strictly match the backend's expectations.

## Error Handling

Standardized JSON error envelope for all non-2xx responses:
```json
{
  "error": "not_found",
  "message": "User not found",
  "code": 404,
  "request_id": "c4af9b-..."
}
```

## Interactive Documentation
Swagger UI is available at: [http://localhost:8080/docs](http://localhost:8080/docs)
