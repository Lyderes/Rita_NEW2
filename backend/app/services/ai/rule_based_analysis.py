from typing import List

def normalize_analysis(raw_output: dict) -> dict:
    """
    Normalizes any analysis output (AI or rule-based) to the strict contract:
    {
        "summary": str,
        "mood": "positive" | "neutral" | "low" | "unknown",
        "signals": List[str],
        "risk": "low" | "medium" | "high"
    }
    """
    # 1. Summary (Default to "Sin resumen")
    summary = str(raw_output.get("summary", "Sin resumen")).strip()
    
    # 2. Mood Normalization
    mood_raw = str(raw_output.get("mood", raw_output.get("sentiment", "unknown"))).lower()
    allowed_moods = ["positive", "neutral", "low", "unknown"]
    mood = "unknown"
    for m in allowed_moods:
        if m in mood_raw:
            mood = m
            break
    if mood == "unknown" and ("bien" in mood_raw or "bueno" in mood_raw):
        mood = "positive"
    elif mood == "unknown" and ("mal" in mood_raw or "triste" in mood_raw or "cansad" in mood_raw):
        mood = "low"

    # 3. Signals Normalization (Dict[str, bool] -> List[str])
    raw_signals = raw_output.get("signals", [])
    signals: List[str] = []
    
    if isinstance(raw_signals, dict):
        for key, detected in raw_signals.items():
            if detected:
                # Clean key: lowercase, snake_case
                clean_key = key.lower().replace(" ", "_").strip()
                signals.append(clean_key)
    elif isinstance(raw_signals, list):
        for signal in raw_signals:
            if isinstance(signal, str):
                signals.append(signal.lower().replace(" ", "_").strip())

    # 4. Risk Normalization (risk only)
    risk_raw = str(raw_output.get("risk", "low")).lower()
    risk = "low"
    if any(k in risk_raw for k in ["high", "alto", "crítico", "critical", "urgente"]):
        risk = "high"
    elif any(k in risk_raw for k in ["medium", "medio", "moderado", "alerta"]):
        risk = "medium"
    
    return {
        "summary": summary,
        "mood": mood,
        "signals": sorted(list(set(signals))),
        "risk": risk
    }

def run_rule_based_analysis(text: str) -> dict:
    """Centralized keyword-based analysis logic."""
    text_lower = text.lower().strip()
    
    if not text_lower or text_lower in ["...", "."]:
        return {
            "summary": "Sin contenido relevante para analizar.",
            "mood": "unknown",
            "signals": [],
            "risk": "low"
        }

    # Keyword mapping
    rules = {
        "pain": ["dolor", "duele", "daño", "espalda", "pierna", "brazo", "pecho", "cabeza"],
        "dizziness": ["mareada", "mareo", "vueltas", "desorientada"],
        "lonely": ["solo", "sola", "nadie", "triste", "ganas de hablar", "extraño"],
        "hunger": ["hambre", "comer", "cena", "desayuno", "comida"],
        "fall": ["caido", "suelo", "piso", "me cai", "golpe"],
        "urgency": ["ayuda", "socorro", "urgente", "hospital", "respirar", "asfixia"],
        "low_energy": ["cansada", "agotada", "sueño", "sin fuerzas"]
    }
    
    detected: List[str] = []
    for signal, keywords in rules.items():
        if any(k in text_lower for k in keywords):
            detected.append(signal)

    # Risk Logic
    risk = "low"
    if "urgency" in detected or "fall" in detected or "dizziness" in detected:
        risk = "high"
    elif "pain" in detected or "lonely" in detected:
        risk = "medium"
    
    # Mood Logic
    mood = "neutral"
    if risk == "high":
        mood = "low"
    elif any(k in text_lower for k in ["bien", "contenta", "alegre", "genial", "ok"]):
        mood = "positive"
    elif any(k in text_lower for k in ["mal", "triste", "cansada", "peor", "aburrida"]):
        mood = "low"

    # Map detected signals to Spanish for the summary
    translations = {
        "pain": "dolor",
        "dizziness": "mareo",
        "lonely": "soledad",
        "hunger": "hambre",
        "fall": "posible caída",
        "urgency": "urgencia",
        "low_energy": "bajo cansancio/energía"
    }
    translated_detected = [translations.get(s, s) for s in detected]

    # Summary Generation
    if not detected:
        summary = "Check-in rutinario sin señales de alerta detectadas."
    else:
        summary = f"Se detectaron señales de {', '.join(translated_detected)}."
        if risk == "high":
            summary = "ALERTA: " + summary
            
    return {
        "summary": summary,
        "mood": mood,
        "signals": detected,
        "risk": risk
    }
