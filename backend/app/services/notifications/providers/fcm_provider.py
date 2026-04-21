from __future__ import annotations
import logging

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import get_settings
from app.services.notifications.providers.base import NotificationProvider

logger = logging.getLogger(__name__)

class FCMProvider(NotificationProvider):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._initialize_app()
    
    def _initialize_app(self) -> None:
        if not firebase_admin._apps:
            if not self.settings.fcm_credentials_path:
                logger.warning("FCM_CREDENTIALS_PATH not set. FCM will fail.")
                return
            try:
                cred = credentials.Certificate(self.settings.fcm_credentials_path)
                firebase_admin.initialize_app(cred)
                logger.info("FCM App initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize FCM: {e}")

    def send_push(self, title: str, body: str, data: dict, target_token: str) -> str:
        if not firebase_admin._apps:
            raise RuntimeError("FCM Provider is not properly initialized with credentials.")

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data={str(k): str(v) for k, v in data.items()},
            token=target_token,
        )

        # Returns the message ID
        return messaging.send(message)
