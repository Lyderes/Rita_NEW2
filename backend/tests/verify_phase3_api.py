
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import require_frontend_auth
from app.db.session import SessionLocal
from app.models.user import User

# Bypass Auth
app.dependency_overrides[require_frontend_auth] = lambda: "test-frontend"

def verify_api():
    client = TestClient(app)
    db = SessionLocal()
    try:
        # Get the test user we created in verify_phase3.py
        user = db.query(User).filter(User.full_name == "Test User Phase 3").first()
        if not user:
            print("Error: Run verify_phase3.py first to seed data.")
            return
            
        user_id = user.id
        
        print(f"--- Testing GET /users/{user_id}/daily-score/latest ---")
        response = client.get(f"/users/{user_id}/daily-score/latest")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Score: {data['global_score']}")
            print(f"Narrative: {data['narrative_summary']}")
        else:
            print(f"Error: {response.text}")

        print(f"\n--- Testing GET /users/{user_id}/daily-score/history ---")
        response = client.get(f"/users/{user_id}/daily-score/history")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            history = response.json()
            print(f"History items: {len(history)}")
            for item in history:
                print(f"- {item['date']}: {item['global_score']}")

    finally:
        db.close()
        app.dependency_overrides.clear()

if __name__ == "__main__":
    verify_api()
