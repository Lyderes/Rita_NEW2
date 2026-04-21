# Humanization Logic (Phase 3.5)

RITA's primary goal is to provide **peace of mind** to caregivers. Raw data can be anxiety-inducing; humanization provides the context needed for calmness.

## Why Humanization?

### 1. No Medical Tone
RITA is a companion and assistant, not a medical diagnostic tool. We avoid clinical jargon and focus on **functional well-being** and **comparative state**. 
- Instead of: *"User exhibits Tachycardia and level 4 Dizziness,"*
- We say: *"Se ha sentido con algo de mareo, pero parece haberse recuperado."*

### 2. Narrative Overrides Score Perception
A numeric score (e.g., 68/100) might look scary without context. The **Narrative Summary** is designed to override that perception by explaining the story behind the number. 
- In a "Recovery Case," the score might be low due to earlier events, but the narrative says "Everything is fine NOW." This prevents unnecessary caregiver anxiety.

### 3. Last State Priority
The most recent interaction carries the highest weight in the humanized interpretation. RITA prioritizes "How are they at this exact moment?" while keeping the historical context as a secondary reference.

## Interpretation Layer

The `DailyScoringService` applies several rules to generate the final narrative strings:

- **Stable Recovery**: When a bad start is followed by a good end.
- **Ongoing Malestar**: When the latest check-in is still problematic.
- **Normal Stability**: When all signals align with the baseline.
- **Sudden Change**: When a normal day is interrupted by a negative signal at the end.

## Tone Rules
- **Calmness**: Always look for signs of improvement.
- **Actionability**: If a situation is truly concerning, provide a clear next step (e.g., "Consider a follow-up call").
- **Clarity**: Use simple, direct Spanish (the system is optimized for Spanish caregivers).
