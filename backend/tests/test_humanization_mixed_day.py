
import requests

# Configuración
BASE_URL = "http://127.0.0.1:8080"
USER_ID = 1  # Asumimos que existe tras seed_db.py

def login():
    print("--- Autenticando ---")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    resp.raise_for_status()
    return resp.json()["access_token"]

def simulate_checkin(token, text):
    print(f"Simulando check-in: '{text}'")
    resp = requests.post(
        f"{BASE_URL}/events/checkin",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": USER_ID, "text": text}
    )
    resp.raise_for_status()
    return resp.json()

def get_daily_score(token):
    resp = requests.get(
        f"{BASE_URL}/users/{USER_ID}/daily-score/latest",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()

def run_mixed_day_test():
    try:
        token = login()
        print("\n--- ESCENARIO: Acumulación Negativa + Recuperación Final ---")
        
        # 1. Simular 10 mensajes de malestar (debería hundir el score a 0)
        for i in range(10):
            print(f"Simulando malestar {i+1}...")
            simulate_checkin(token, "Me duele mucho la cabeza y me siento fatal.")
            
        # 2. Simular recuperación final
        print("Simulando RECUPERACIÓN final...")
        simulate_checkin(token, "Ya me he tomado la pastilla y me encuentro mucho mejor, gracias RITA.")
        
        # Obtener resultado
        score_data = get_daily_score(token)
        
        narrative = score_data.get('narrative_summary', "")
        interpretation = score_data.get('interpretation', "")
        factors = score_data.get('main_factors', [])
        score = score_data.get('global_score')

        print("\n--- RESULTADOS BACKEND ---")
        print(f"Global Score: {score} (esperado: < 45)")
        print(f"Narrativa: {narrative}")
        print(f"Interpretación: {interpretation}")
        print(f"Factores: {factors}")
        
        # Validaciones Phase 3.5
        # La narrativa debe mencionar mejoría/estabilización a pesar del score bajo
        if "parece encontrarse mucho mejor" in narrative.lower() or "situación se ha aliviado" in narrative.lower():
            print("✅ TEST PASSED: Mejora detectada a pesar de acumulación negativa.")
        else:
            print("❌ TEST FAILED: La narrativa no refleja la mejoría final.")
            
        if "confirmar si necesita ayuda para descansar" in interpretation.lower() or "buena señal" in interpretation.lower():
            print("✅ TEST PASSED: Interpretación equilibrada detectada.")
        else:
            print("❌ TEST FAILED: Interpretación no balanceada.")

    except Exception as e:
        print(f"ERROR en el test: {e}")

if __name__ == "__main__":
    run_mixed_day_test()
