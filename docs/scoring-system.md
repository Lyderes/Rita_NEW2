# Scoring System

The RITA Scoring System converts raw signals into a meaningful wellness metric (0-100).

## Core Concepts

- **Global Score (100-0)**: An accumulative but capped score.
- **Baseline Alignment**: Penalties are heavier if the signal contradicts the user's normal state (e.g., a "Positive" person suddenly exhibiting "Low Mood").
- **Sub-scores**:
    - **Mood**: Based on sentiment analysis of check-ins.
    - **Activity**: Frequency of interactions vs. expected routine.
    - **Routine**: Consistency of check-in timing.
    - **Autonomy**: Ability to handle the day without excessive requests for help.

## Mixed Day Logic (Recovery Detection)

This is a critical feature that prevents "False Alarms." 
If a user had a "high risk" signal early in the day (e.g., dizziness) but their **latest** check-in is "low risk" (positive), the scoring system detects a **Recovery**. 
- The narrative will reflect that they are now stable, even if the numeric score is still recovering from the earlier penalty.

## Concrete Examples

### 1. Normal Day (High Score) 🟢
- **Signals**: "Everything is fine," "I'm going for a walk."
- **Scores**: 95-100.
- **Narrative**: *"Hoy se ha encontrado dentro de lo habitual y no se observan cambios importantes."*

### 2. Slight Deviation (Warning) 🟡
- **Signals**: One mention of "tiredness" or "pain," but otherwise stable.
- **Scores**: 70-85.
- **Narrative**: *"Aunque ha mencionado algún malestar leve, el día transcurre de forma bastante tranquila."*

### 3. Concerning Day (Alert) 🟠
- **Signals**: Persistent "confusion" or "pain."
- **Scores**: <60.
- **Narrative**: *"Se han detectado varios avisos de malestar hoy que conviene tener en cuenta."*

### 4. Mixed Day / Recovery Case 🔵
- **Signals**: 10:00 AM "Dizziness" (High Risk), 2:00 PM "I feel better now" (Low Risk).
- **Scores**: Global score might be 75, but **Narrative** prioritizes the recovery.
- **Narrative**: *"Tras un momento de malestar inicial, el día ha mejorado notablemente y ahora se encuentra bien."*

---

## Routine Awareness (Phase 6)

When caregivers configure scheduled reminders, the scoring system can detect when expected activity does **not** occur within the configured time window.

### Activity Windows by Type

| Reminder Type | Window | Valid Activity |
|---|---|---|
| `medication` | ±60 min | `checkin`, `interaction` |
| `meal` | ±90 min | `checkin`, `interaction` |
| `hydration` | ±120 min | `checkin`, `interaction` |
| `checkin` | ±90 min | `checkin` only |

### Late-Activity Detection

If activity occurs **after** the window closes but within **2 hours** of the window end, it is treated as a *late* event — not a full miss. The penalty is halved and the narrative uses softer, non-judgmental phrasing.

| Signal Type | Example Narrative |
|---|---|
| Full miss | "No se observa actividad en su horario de medicación" |
| Late activity | "Hoy parece haber tomado la medicación con algo de retraso" |

### Penalty Table

| Sensitivity | Per miss | Per late | Scaling |
|---|---|---|---|
| `calm` | 2 pts | 1 pt | +2 pts/miss |
| `balanced` | 4 pts | 2 pts | +2 pts/miss |
| `sensitive` | 6 pts | 3 pts | +2 pts/miss |

### Factor Display Cap

To avoid UI overflow, `main_factors` is capped at:
- **max 2 health signals** (from check-in analysis)
- **max 2 routine observations** (from missed/late routines)

This ensures readability regardless of how many routines a user has configured.

### Design Principles
- All routine signals are **soft and observational** — never alarmist or medical in tone.
- Recovery logic (Phase 3.5) always takes priority over routine observations.
- A check-in that falls within a routine window counts as valid activity.
