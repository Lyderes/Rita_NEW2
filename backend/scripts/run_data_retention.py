import logging
from app.db.session import SessionLocal
from app.services.data_retention_service import run_data_retention

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main() -> None:
    logger.info("Starting manual data retention job...")
    db = SessionLocal()
    try:
        result = run_data_retention(db)
        logger.info(f"Data retention result: {result}")
    except Exception as e:
        logger.error(f"Error running data retention: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
