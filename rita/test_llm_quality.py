import requests
import json
import time

url = "http://127.0.0.1:8001/v1/chat/completions"
payload = {
    "model": "model",
    "messages": [{"role": "user", "content": "Me recomiendas un libro para leer?"}],
    "max_tokens": 50,
    "temperature": 0.2
}

print(f"Enviando solicitud a {url}...")
start = time.perf_counter()
try:
    response = requests.post(url, json=payload, timeout=90)
    response.raise_for_status()
    data = response.json()
    content = data['choices'][0]['message']['content']
    latency = time.perf_counter() - start
    print(f"\nRespuesta (Latencia {latency:.2f}s):")
    print(f"---")
    print(content)
    print(f"---")
except Exception as e:
    print(f"Error: {e}")
