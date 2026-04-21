import os
import subprocess
from datetime import datetime, UTC
from app.core.config import get_settings

def run_backup() -> None:
    settings = get_settings()
    db_url = settings.database_url
    
    if "sqlite" in db_url:
        print("Skipping physical backup: SQLite is not supported for pg_dump operations.")
        return
        
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    
    backup_dir = os.getenv("DB_BACKUP_DIR", "./backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_file = os.path.join(backup_dir, f"rita_db_backup_{timestamp}.dump")
    
    # Use standard Postgres utilities. The URL safely passes the credentials.
    cmd = ["pg_dump", str(db_url), "-F", "c", "-f", backup_file]
    
    print(f"Starting PostgreSQL backup to {backup_file}...")
    try:
        env = os.environ.copy()
        subprocess.run(cmd, env=env, check=True, capture_output=True)
        print(f"Success! Backup saved at {backup_file}")
    except subprocess.CalledProcessError as e:
        print("Error executing pg_dump. Make sure pg_dump is installed in your system PATH.")
        print(f"pg_dump error output: {e.stderr.decode('utf-8')}")
    except FileNotFoundError:
        print("ERROR: 'pg_dump' utility not found in PATH.")
        print("If using Docker without native clients, run: docker exec postgres pg_dump -U rita_user rita_events > backup.sql")

if __name__ == "__main__":
    run_backup()
