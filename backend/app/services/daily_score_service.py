
from __future__ import annotations

from datetime import date, datetime, time, UTC, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_score import DailyScore
from app.models.event import Event
from app.models.check_in_analysis import CheckInAnalysis
from app.models.user import User
from app.models.user_interpretation_settings import UserInterpretationSettings
from app.models.scheduled_reminder import ScheduledReminder

class DailyScoringService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_compute_daily_score(self, user_id: int, target_date: date) -> DailyScore | None:
        """
        Returns the score for the given date. 
        Actually, let's recompute if it's today to stay fresh.
        """
        stmt = select(DailyScore).where(
            DailyScore.user_id == user_id,
            DailyScore.date == target_date
        )
        existing = self.db.scalar(stmt)
        
        # If it's today, we always want to recompute to reflect the latest activity (Phase 3.5)
        if existing and target_date < date.today():
            return existing
        
        return self.compute_daily_score(user_id, target_date)

    def compute_daily_score(self, user_id: int, target_date: date) -> DailyScore | None:
        user = self.db.get(User, user_id)
        if not user:
            return None
            
        baseline = user.baseline
        if not baseline:
            # We need a baseline to compute a meaningful score
            return None

        # Fetch today's check-ins with analysis
        # Using aware UTC for range check to match PostgreSQL TIMESTAMP WITH TIME ZONE.
        # Force UTC to match database timestamps if they are aware (Requirement 7)
        start_dt = datetime.combine(target_date, time.min, tzinfo=UTC)
        end_dt = datetime.combine(target_date, time.max, tzinfo=UTC)

        stmt = (
            select(CheckInAnalysis)
            .join(Event, CheckInAnalysis.event_id == Event.id)
            .where(
                Event.user_id == user_id,
                Event.created_at >= start_dt,
                Event.created_at <= end_dt
            ).order_by(Event.created_at.asc())
        )
        analyses = self.db.scalars(stmt).all()
        n_checkins = len(analyses)
        
        # Fetch all events for the day for routine check (Phase 6)
        stmt_events = (
            select(Event)
            .where(
                Event.user_id == user_id,
                Event.created_at >= start_dt,
                Event.created_at <= end_dt
            ).order_by(Event.created_at.asc())
        )
        all_day_events = self.db.scalars(stmt_events).all()

        # If no activity, persist a 0-score so the schema validator has id/timestamps
        if n_checkins == 0:
            existing_zero = self.db.scalar(
                select(DailyScore).where(
                    DailyScore.user_id == user_id,
                    DailyScore.date == target_date,
                )
            )
            if existing_zero:
                return existing_zero
            zero_score = DailyScore(
                user_id=user_id,
                date=target_date,
                global_score=0,
                mood_score=0,
                activity_score=0,
                routine_score=0,
                autonomy_score=0,
                baseline_similarity=0,
                main_factors=["RITA no ha tenido contacto con el usuario hoy."],
                narrative_summary="No se ha registrado actividad este día.",
                interpretation="RITA no tiene datos suficientes para generar un informe.",
                observed_routines=[],
                missed_or_late_routines=[],
            )
            self.db.add(zero_score)
            self.db.commit()
            self.db.refresh(zero_score)
            return zero_score

        # --- Temporal Awareness (Requirement 1 & 2) ---
        # Identify the latest state vs previous signals
        latest_analysis = analyses[-1]
        previous_analyses = analyses[:-1]
        
        has_earlier_negatives = any(a.risk in ["medium", "high"] for a in previous_analyses)
        is_latest_positive = latest_analysis.risk == "low"
        
        # Recovery detection: bad start -> good end
        is_recovery = has_earlier_negatives and is_latest_positive
        
        # Current state tone
        current_state_is_stable = is_latest_positive

        # --- Scoring Logic (Baseline 75 + Consistency Bonus - Phase 17.5) ---
        # Starts at 75 for the first checkin, grows by 5 for each extra checkin up to 100
        base_val = min(100, 75 + ((n_checkins - 1) * 5))
        
        global_score = base_val
        mood_score = base_val
        activity_score = base_val
        routine_score = base_val
        autonomy_score = base_val
        baseline_similarity = base_val
        
        concerning_signals = []
        n_concerning = sum(1 for a in analyses if a.risk in ["medium", "high"])
        
        signal_counts = {}
        for analysis in analyses:
            for signal in analysis.signals:
                concerning_signals.append(signal)
                signal_counts[signal] = signal_counts.get(signal, 0) + 1

        # --- Personalization Settings (Phase 4) ---
        settings = user.interpretation_settings
        if not settings:
            settings = UserInterpretationSettings(user_id=user_id) # Uses defaults: balanced, all False

        # Sensitivity Factors
        sensitivity = settings.sensitivity_mode
        rep_extra_penalty = 5
        if sensitivity == "sensitive":
            rep_extra_penalty = 8
        elif sensitivity == "calm":
            rep_extra_penalty = 2

        # Penalties: base values
        # contextual flags adjust these
        base_penalties = {
            "pain": 10, "dolor": 10,
            "dizziness": 15, "mareo": 15, "mareada": 15,
            "confusion": 15, "confusión": 15,
            "tiredness": 5, "cansancio": 5, "fatiga": 5
        }

        # Contextual Reinterpretation (Refined Requirement 1 & 4)
        if settings.has_chronic_pain:
            # Reduce base penalty but increase repetition weight
            base_penalties["pain"] = 4
            base_penalties["dolor"] = 4
            if signal_counts.get("pain", 0) > 1 or signal_counts.get("dolor", 0) > 1:
                rep_extra_penalty += 4 # Chronic pain worsening is MORE alarming

        if settings.low_energy_baseline:
            base_penalties["tiredness"] = 2
            base_penalties["cansancio"] = 2
            base_penalties["fatiga"] = 2

        unique_signals = set(concerning_signals)
        for s in unique_signals:
            s_lower = s.lower()
            p = base_penalties.get(s_lower, 8) 
            count = signal_counts[s]
            
            penalty_val = p * count
            if sensitivity == "sensitive":
                penalty_val *= 1.2 # Lose more points in sensitive mode
            
            # Accumulate but cap penalty impact on global score
            global_score -= min(35, penalty_val)
            
            if count > 1:
                global_score -= rep_extra_penalty

        # Baseline alignment
        mood_impact = 25
        if settings.mood_variability:
            mood_impact = 12 # Reduce volatility penalty
            
        if baseline.usual_mood == "positive" and n_concerning > 0:
            mood_score -= (mood_impact * n_concerning)
            baseline_similarity -= 20

        # Routine Score
        min_expected_checkins = 2
        if settings.low_communication:
            min_expected_checkins = 1 # Lower expectation for quiet users
            
        if n_checkins < min_expected_checkins:
            routine_score -= 10
        elif n_concerning > 1:
            routine_score -= 30

        # --- Routine Awareness (Phase 6) ---
        routine_signals = []
        observed_routines = [] # Phase 6.5
        routine_penalty_acc = 0
        miss_count = 0
        
        # Define window sizes per type (Requirement 3)
        WINDOW_MINS = {
            "medication": 60,
            "meal": 90,
            "hydration": 120,
            "checkin": 90
        }
        
        # Define base penalties (Requirement 2)
        base_miss_penalty = 4
        if sensitivity == "sensitive":
            base_miss_penalty = 6
        elif sensitivity == "calm":
            base_miss_penalty = 2
            
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        target_day_name = day_names[target_date.weekday()]
        
        stmt_reminders = select(ScheduledReminder).where(
            ScheduledReminder.user_id == user_id,
            ScheduledReminder.is_active == True
        )
        reminders = self.db.scalars(stmt_reminders).all()
        
        for r in reminders:
            if target_day_name not in r.days_of_week:
                continue
                
            # Parse time_of_day (HH:mm)
            try:
                h, m = map(int, r.time_of_day.split(':'))
                reminder_time = datetime.combine(target_date, time(h, m), tzinfo=UTC)
            except:
                continue
                
            win_size = WINDOW_MINS.get(r.reminder_type, 90)
            win_start = reminder_time - timedelta(minutes=win_size)
            win_end = reminder_time + timedelta(minutes=win_size)
            late_threshold = win_end + timedelta(minutes=120) # 2h late window (Requirement 5)
            
            # Don't check if the window hasn't passed yet (unless we have activity)
            now_utc = datetime.now(UTC)
            if now_utc < win_start:
                continue

            # Check for valid activity (Requirement 4)
            # Rule: checkin or interaction counts for most. 
            # missed_checkin specifically requires a 'checkin' event.
            has_activity = False
            is_late = False
            
            for event in all_day_events:
                # Force awareness if missing (fix for SQLite/naive envs)
                ev_dt = event.created_at
                if ev_dt.tzinfo is None:
                    ev_dt = ev_dt.replace(tzinfo=UTC)
                    
                # Basic rule: any checkin/interaction in window
                is_in_window = win_start <= ev_dt <= win_end
                is_in_late_window = win_end < ev_dt <= late_threshold
                
                valid_for_type = False
                if r.reminder_type == "checkin":
                    valid_for_type = (event.event_type == "checkin")
                else:
                    valid_for_type = (event.event_type in ["checkin", "interaction"])
                
                if valid_for_type:
                    if is_in_window:
                        has_activity = True
                        fallback_titles = {
                            "medication": "Toma de medicación",
                            "meal": "Comida / Alimentación",
                            "hydration": "Hidratación",
                            "checkin": "Contacto de bienestar"
                        }
                        display_title = r.title or fallback_titles.get(r.reminder_type, r.reminder_type.capitalize())
                        observed_routines.append(display_title)
                        break
                    elif is_in_late_window:
                        is_late = True
            
            if not has_activity:
                # If window hasn't fully passed, we don't penalize yet
                if now_utc < win_end:
                    continue
                
                # Full miss or Late?
                miss_signal = f"missed_{r.reminder_type}"
                if is_late:
                    # Late routine (Requirement 5) - half penalty
                    penalty = (base_miss_penalty + (miss_count * 2)) / 2
                    routine_signals.append(f"{miss_signal}_late")
                else:
                    # Total miss
                    penalty = base_miss_penalty + (miss_count * 2)
                    routine_signals.append(miss_signal)
                    miss_count += 1
                
                routine_penalty_acc += penalty
        
        global_score -= routine_penalty_acc
        routine_score -= (routine_penalty_acc * 2) 

        # --- Final score adjustments ---
        global_score = max(0, min(100, global_score))
        mood_score = max(0, min(100, mood_score))
        activity_score = max(0, min(100, activity_score))
        routine_score = max(0, min(100, routine_score))
        autonomy_score = max(0, min(100, autonomy_score))
        baseline_similarity = max(0, min(100, baseline_similarity))

        # --- Humanization and Narrative (Phase 3.5) ---
        
        # 1. Map signals to human phrases
        HUMAN_FACTORS = {
            "pain": "Ha mencionado malestar o dolor",
            "dolor": "Ha mencionado malestar o dolor",
            "dizziness": "Se ha sentido con algo de mareo",
            "mareo": "Se ha sentido con algo de mareo",
            "mareada": "Se ha sentido con algo de mareo",
            "confusion": "Se ha mostrado con algo de confusión",
            "confusión": "Se ha mostrado con algo de confusión",
            "tiredness": "Se ha mostrado más cansada de lo habitual",
            "cansancio": "Se ha mostrado más cansada de lo habitual",
            "fatiga": "Se ha mostrado más cansada de lo habitual",
            "mood_low": "El ánimo ha estado un poco más bajo",
            "repetition": "Se han repetido algunas señales de malestar",
            "low_activity": "Ha habido menos actividad de la acostumbrada"
        }

        human_factors_list = []
        seen_human = set()
        
        for s in unique_signals:
            phrase = HUMAN_FACTORS.get(s.lower(), f"Se ha detectado {s}")
            if phrase not in seen_human:
                human_factors_list.append(phrase)
                seen_human.add(phrase)
        
        if n_checkins < 2:
            human_factors_list.append(HUMAN_FACTORS["low_activity"])
        if any(count > 1 for count in signal_counts.values()):
            if HUMAN_FACTORS["repetition"] not in seen_human:
                human_factors_list.append(HUMAN_FACTORS["repetition"])
        if mood_score < 75:
            if HUMAN_FACTORS["mood_low"] not in seen_human:
                human_factors_list.append(HUMAN_FACTORS["mood_low"])

        # Mapping routine misses to human readable (Requirement 6)
        # Full miss → neutral-observational. Late → softer, non-judgmental.
        ROUTINE_HUMAN = {
            "missed_medication": "No se observa actividad en su horario de medicación",
            "missed_medication_late": "Hoy parece haber tomado la medicación con algo de retraso",
            "missed_meal": "No se observa actividad en su horario habitual de comidas",
            "missed_meal_late": "Hoy ha comido algo más tarde de lo acostumbrado",
            "missed_hydration": "Hoy ha habido menos actividad en su horario de hidratación",
            "missed_hydration_late": "La hidratación parece haberse producido fuera del horario habitual",
            "missed_checkin": "El contacto de bienestar programado no se ha registrado hoy",
            "missed_checkin_late": "El contacto de bienestar se ha producido algo más tarde de lo habitual",
        }
        
        # Cap: max 2 routine observations in main_factors to avoid UI overflow
        routine_factor_count = 0
        for sig in routine_signals:
            if routine_factor_count >= 2:
                break
            phrase = ROUTINE_HUMAN.get(sig, f"Se observa un cambio en la rutina de {sig.replace('missed_', '').replace('_late', '')}")
            if phrase not in seen_human:
                human_factors_list.append(phrase)
                seen_human.add(phrase)
                routine_factor_count += 1

        narrative = ""
        interpretation = ""

        # --- Narrative Logic (Refined Sensitivity Tiers - Phase 4) ---
        
        threshold_stable = 85
        threshold_deviation = 60
        threshold_critical = 40 # Phase 17.5
        
        if sensitivity == "sensitive":
            threshold_stable = 92
            threshold_deviation = 75
            threshold_critical = 55
        elif sensitivity == "calm":
            threshold_stable = 75
            threshold_deviation = 50
            threshold_critical = 30

        # OVERRIDE recovery if the score is actually CRITICAL (Phase 17.5)
        # Even if the last moment is stable, a 27 means a fall/missed meds occurred.
        # We must NOT be overly optimistic.
        if is_recovery and global_score < threshold_critical:
            is_recovery = False

        if is_recovery:
            # High priority: Recovery case (Mixed Day)
            if global_score > threshold_deviation:
                narrative = "Tras un momento de malestar inicial, el día ha mejorado notablemente y ahora se encuentra bien."
                interpretation = "Parece que fue algo pasajero. No requiere acción, pero es una buena señal que el último contacto haya sido positivo."
            else:
                narrative = "Aunque ha tenido varios momentos de malestar hoy, en el último contacto parece encontrarse algo mejor."
                interpretation = "Es buena señal que la situación se haya aliviado. Conviene confirmar si necesita algo para descansar mejor esta noche."
        
        elif not current_state_is_stable:
            # Current state is negative (Latest check-in is medium/high risk)
            if global_score > threshold_deviation:
                narrative = "El día transcurría con normalidad, pero en el último contacto ha mencionado encontrarse algo peor."
                interpretation = "Puede ser un cansancio puntual de última hora, pero vigile si el malestar persiste en el próximo contacto."
            else:
                narrative = "Se han registrado varias señales de malestar y el último contacto sigue mostrando síntomas que requieren atención."
                interpretation = "Lo más recomendable es realizar una llamada de seguimiento ahora para valorar su estado de forma directa."
        
        else:
            # Stable State logic
            if global_score >= threshold_stable:
                narrative = "Hoy se ha encontrado dentro de lo habitual y no se observan cambios importantes."
                interpretation = "No se observan señales que requieran atención especial en este momento."
            elif global_score >= threshold_deviation:
                narrative = "Aunque ha mencionado algún malestar leve, el día transcurre de forma bastante tranquila."
                interpretation = "Parece una desviación menor de su rutina. Una breve llamada al final del día sería suficiente."
            else:
                # Low score but stable now (and not classified as recovery above)
                narrative = "Se han detectado varios avisos de malestar hoy que conviene tener en cuenta."
                interpretation = "Aunque ahora parece estar tranquila, el acumulado del día sugiere que hoy ha sido un día más difícil de lo habitual."

        # Smart factor cap: max 2 health signals + max 2 routine observations
        # This prevents overloading the UI when a user has many reminders configured.
        routine_phrases = {ROUTINE_HUMAN.get(s, "") for s in routine_signals}
        health_factors = [f for f in human_factors_list if f not in routine_phrases][:2]
        routine_factors = [f for f in human_factors_list if f in routine_phrases][:2]
        unique_factors = health_factors + routine_factors

        # Routine summary lists (Phase 6.5)
        missed_or_late_routines = [ROUTINE_HUMAN.get(s, s) for s in routine_signals]

        # Save or Update
        existing = self.db.scalar(
            select(DailyScore).where(
                DailyScore.user_id == user_id,
                DailyScore.date == target_date
            )
        )
        
        if existing:
            existing.global_score = global_score
            existing.mood_score = mood_score
            existing.activity_score = activity_score
            existing.routine_score = routine_score
            existing.autonomy_score = autonomy_score
            existing.baseline_similarity = baseline_similarity
            existing.main_factors = unique_factors
            existing.narrative_summary = narrative
            existing.interpretation = interpretation
            existing.observed_routines = observed_routines
            existing.missed_or_late_routines = missed_or_late_routines
            existing.updated_at = datetime.now(UTC)
            self.db.commit()
            return existing
        else:
            new_score = DailyScore(
                user_id=user_id,
                date=target_date,
                global_score=global_score,
                mood_score=mood_score,
                activity_score=activity_score,
                routine_score=routine_score,
                autonomy_score=autonomy_score,
                baseline_similarity=baseline_similarity,
                main_factors=unique_factors,
                narrative_summary=narrative,
                interpretation=interpretation,
                observed_routines=observed_routines,
                missed_or_late_routines=missed_or_late_routines
            )
            self.db.add(new_score)
            self.db.commit()
            self.db.refresh(new_score)
            return new_score
