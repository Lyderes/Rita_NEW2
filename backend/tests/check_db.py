
import os
import sys
from datetime import datetime, UTC

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.event import Event
from app.models.check_in_analysis import CheckInAnalysis
from sqlalchemy import select

def check_db():
    db = SessionLocal()
    try:
        print("--- Revisando Eventos (últimos 5) ---")
        stmt_events = select(Event).order_by(Event.id.desc()).limit(5)
        events = db.scalars(stmt_events).all()
        for e in events:
            print(f"Event ID: {e.id}, Type: {e.event_type}, Created: {e.created_at}")
            
        print("\n--- Revisando Análisis (últimos 5) ---")
        stmt_analysis = select(CheckInAnalysis).order_by(CheckInAnalysis.id.desc()).limit(5)
        analyses = db.scalars(stmt_analysis).all()
        for a in analyses:
            print(f"Analysis ID: {a.id}, Event ID: {a.event_id}, Risk: {a.risk}, Created: {a.created_at}")
            
        # Time check
        target_date = datetime.now(UTC).date()
        from datetime import time
        start_dt = datetime.combine(target_date, time.min, tzinfo=UTC)
        end_dt = datetime.combine(target_date, time.max, tzinfo=UTC)
        print(f"\nVentana búsqueda (UTC): {start_dt} a {end_dt}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
