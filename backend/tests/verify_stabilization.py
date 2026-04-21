import requests
from datetime import date

BASE_URL = "http://127.0.0.1:8080"
USER_ID = 1

def get_auth_headers():
    print("\n--- Testing Auth: Login ---")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        print("Login SUCCESS")
        return {"Authorization": f"Bearer {token}"}
    else:
        print(f"Login failed: {resp.text}")
        return {}

def test_baseline(headers):
    print("\n--- Testing Baseline Profile ---")
    # GET
    resp = requests.get(f"{BASE_URL}/users/{USER_ID}/baseline", headers=headers)
    if resp.status_code == 200:
        print(f"GET Baseline SUCCESS: {resp.json()['usual_mood']}")
    else:
        print(f"GET Baseline FAILED: {resp.text}")
        return

    # PUT
    updated_data = resp.json()
    updated_data["notes"] = "Updated via verify_stabilization.py"
    resp = requests.put(f"{BASE_URL}/users/{USER_ID}/baseline", headers=headers, json=updated_data)
    if resp.status_code == 200:
        print("PUT Baseline SUCCESS")
    else:
        print(f"PUT Baseline FAILED: {resp.text}")

def test_scenario(name, phrases, headers):
    print(f"\n--- Testing Scenario: {name} ---")
    for phrase in phrases:
        print(f"Sending: '{phrase}'")
        resp = requests.post(f"{BASE_URL}/events/checkin", headers=headers, json={
            "user_id": USER_ID,
            "text": phrase
        })
        if resp.status_code != 201:
            print(f"FAILED: {resp.text}")
            return
        
    # Verify latest score
    resp = requests.get(f"{BASE_URL}/users/{USER_ID}/daily-score/latest", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        print(f"Global Score: {data['global_score']}")
        print(f"Narrative: {data['narrative_summary']}")
        print(f"Factors: {data['main_factors']}")
    else:
        print(f"FAILED to get latest score: {resp.text}")

if __name__ == "__main__":
    headers = get_auth_headers()
    if not headers:
        exit(1)

    # 0. Baseline Verification
    test_baseline(headers)

    # 1. Normal Day Persistence
    test_scenario("Normal Day", ["Hoy estoy bien", "He descansado bien"], headers)
    
    # 2. Add pain later - should drop score
    test_scenario("Add Pain", ["Me duele la espalda"], headers)
    
    # 3. Repeated concern - should drop score significantly
    test_scenario("Repeated Concern", ["Me sigue doliendo", "Estoy mareada"], headers)

    # 4. Check history length (should still be 1 entry for today)
    print("\n--- Testing Data Integrity (History) ---")
    resp = requests.get(f"{BASE_URL}/users/{USER_ID}/daily-score/history", headers=headers)
    history = resp.json()
    if isinstance(history, list):
        today_count = sum(1 for s in history if s['date'] == str(date.today()))
        print(f"History entries for today: {today_count} (Expected: 1)")
        
        if today_count == 1:
            print("SUCCESS: Data integrity confirmed (1 score per day).")
        else:
            print("FAILURE: Multiple scores found for today.")
    else:
        print(f"FAILURE: History response is not a list: {history}")
