from __future__ import annotations

import logging
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.base import register_models
from app.models.user import User
from app.models.frontend_user import FrontendUser
from app.models.device import Device
from app.models.user_baseline_profile import UserBaselineProfile
from app.core.security import hash_password, hash_device_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Registrar modelos para resolver relaciones
register_models()

def seed_data():
    db = SessionLocal()
    try:
        # 1. Admin Frontend User (Caregiver)
        username = "admin"
        stmt = select(FrontendUser).where(FrontendUser.username == username)
        admin = db.execute(stmt).scalar_one_or_none()
        
        if not admin:
            logger.info("Creating admin frontend user...")
            admin = FrontendUser(
                username=username,
                password_hash=hash_password("admin123"),
                full_name="System Administrator"
            )
            db.add(admin)
            db.flush() # Get ID
            logger.info("Admin frontend user created.")
        else:
            logger.info("Admin frontend user already exists.")

        # 2. Demo Monitored User (Senior)
        demo_name = "Demo Senior"
        stmt = select(User).where(User.full_name == demo_name)
        senior = db.execute(stmt).scalar_one_or_none()
        
        if not senior:
            logger.info("Creating demo senior user...")
            senior = User(
                full_name=demo_name,
                notes="Usuario de demostración para pruebas de sistema."
            )
            db.add(senior)
            db.flush()
            logger.info(f"Demo senior created with ID {senior.id}.")
        else:
            logger.info(f"Demo senior already exists (ID {senior.id}).")

        # 3. Device for Senior
        device_code = "rita-edge-001"
        stmt = select(Device).where(Device.device_code == device_code)
        device = db.execute(stmt).scalar_one_or_none()
        
        if not device:
            logger.info(f"Creating device {device_code}...")
            device = Device(
                user_id=senior.id,
                device_code=device_code,
                device_name="RITA Edge Demo",
                location_name="Salón",
                device_token_hash=hash_device_token("dev-token-123"),
                is_active=True
            )
            db.add(device)
            logger.info("Device created.")
        else:
            logger.info("Device already exists. Updating token hash...")
            device.device_token_hash = hash_device_token("dev-token-123")
            db.add(device)

        # 4. Baseline Profile
        stmt = select(UserBaselineProfile).where(UserBaselineProfile.user_id == senior.id)
        baseline = db.execute(stmt).scalar_one_or_none()
        
        if not baseline:
            logger.info(f"Creating baseline for senior {senior.id}...")
            baseline = UserBaselineProfile(
                user_id=senior.id,
                usual_mood="neutral",
                usual_activity_level="medium",
                usual_energy_level="medium",
                lives_alone=True,
                meals_per_day=3,
                usual_sleep_hours=8.0,
                social_interaction_level="medium",
                notes="Perfil de línea base por defecto."
            )
            db.add(baseline)
            logger.info("Baseline profile created.")
        else:
            logger.info("Baseline profile already exists.")

        db.commit()
        logger.info("Seeding completed successfully.")
        
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
