
import sys
import traceback
from pathlib import Path
from datetime import date

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.services.daily_score_service import DailyScoringService

def debug():
    db = SessionLocal()
    try:
        service = DailyScoringService(db)
        print(f"Service: {service}")
        print(f"Method: {service.get_or_compute_daily_score}")
        
        # Try to call it directly
        score = service.get_or_compute_daily_score(1, date.today())
        print(f"Success! Score: {score}")
    except Exception:
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    debug()
