from __future__ import annotations

class NotificationProvider:
    """Base interface for notification providers."""

    def send_push(self, title: str, body: str, data: dict, target_token: str) -> str:
        """Sends push notification and returns a provider message ID."""
        raise NotImplementedError("Push not supported by this provider")

    def send_sms(self, text: str, to_number: str) -> str:
        """Sends SMS and returns a provider message ID."""
        raise NotImplementedError("SMS not supported by this provider")
