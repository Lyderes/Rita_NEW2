from __future__ import annotations
import logging

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.core.config import get_settings
from app.services.notifications.providers.base import NotificationProvider

logger = logging.getLogger(__name__)

class TwilioProvider(NotificationProvider):
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        if self.settings.twilio_account_sid and self.settings.twilio_auth_token:
            self.client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        else:
            logger.warning("Twilio credentials missing. Twilio SMS will fail.")

    def send_sms(self, text: str, to_number: str) -> str:
        if not self.client or not self.settings.twilio_phone_number:
            raise RuntimeError("Twilio Provider is not properly initialized with credentials.")

        formatted_text = f"ALERTA RITA: {text}"
        
        try:
            message = self.client.messages.create(
                body=formatted_text,
                from_=self.settings.twilio_phone_number,
                to=to_number
            )
            return message.sid
        except TwilioRestException as e:
            logger.error(f"Twilio API Error: {e.msg}")
            raise
