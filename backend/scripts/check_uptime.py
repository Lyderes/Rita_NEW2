import requests
import time
from datetime import datetime
import argparse

def check_uptime(url: str, interval: int) -> None:
    print(f"Starting lightweight uptime monitor for {url} every {interval}s")
    print("Press Ctrl+C to exit")
    try:
        while True:
            try:
                start = time.time()
                resp = requests.get(url, timeout=5)
                ms = int((time.time() - start) * 1000)
                
                try:
                    data = resp.json()
                    status = data.get("status", "unknown")
                    db_status = data.get("database", "unknown")
                except ValueError:
                    status = "invalid_json"
                    db_status = "unknown"
                
                if resp.status_code == 200 and status == "ok":
                    print(f"[{datetime.now().strftime('%FT%T')}] OK | {ms}ms | DB: {db_status}")
                else:
                    print(f"[{datetime.now().strftime('%FT%T')}] DEGRADED ({resp.status_code}) | DB: {db_status}")
                    
            except requests.RequestException as e:
                print(f"[{datetime.now().strftime('%FT%T')}] DOWN | Error: {e}")
                
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nUptime monitor stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RITA MVP Lightweight Uptime Monitor")
    parser.add_argument("--url", default="http://localhost:8000/health", help="API Health endpoint URL")
    parser.add_argument("--interval", type=int, default=10, help="Check interval in seconds")
    args = parser.parse_args()
    
    check_uptime(args.url, args.interval)
