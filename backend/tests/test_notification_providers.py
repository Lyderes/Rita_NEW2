from unittest.mock import MagicMock, patch

from app.services.notifications.providers.fcm_provider import FCMProvider
from app.services.notifications.providers.twilio_provider import TwilioProvider

@patch("app.services.notifications.providers.fcm_provider.messaging.send")
def test_fcm_provider_send_push_success(mock_send, monkeypatch):
    mock_send.return_value = "projects/my-project/messages/12345"
    
    # Mock firebase_admin._apps so provider thinks it's initialized
    import firebase_admin
    monkeypatch.setattr(firebase_admin, "_apps", {"[DEFAULT]": True})
    
    provider = FCMProvider()
    result = provider.send_push(
        title="Test",
        body="Body",
        data={"key": "val"},
        target_token="token_123"
    )
    
    assert result == "projects/my-project/messages/12345"
    mock_send.assert_called_once()
    
    # Check the args passed to firebase's send method
    message_arg = mock_send.call_args[0][0]
    assert message_arg.notification.title == "Test"
    assert message_arg.notification.body == "Body"
    assert message_arg.data == {"key": "val"}
    assert message_arg.token == "token_123"

@patch("app.services.notifications.providers.twilio_provider.Client")
def test_twilio_provider_send_sms_success(mock_client_class, monkeypatch):
    mock_client_instance = MagicMock()
    mock_client_class.return_value = mock_client_instance
    mock_message_result = MagicMock()
    mock_message_result.sid = "SM12345abcde"
    mock_client_instance.messages.create.return_value = mock_message_result
    
    # Force settings so the TwilioProvider initializes
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth123")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+1234567890")
    
    # Re-import get_settings to clear its cache maybe? Not strictly needed if settings are mocked inside Provider
    from app.core.config import get_settings
    settings = get_settings()
    settings.twilio_account_sid = "AC123"
    settings.twilio_auth_token = "auth123"
    settings.twilio_phone_number = "+1234567890"

    provider = TwilioProvider()
    
    result = provider.send_sms("Test Alert", "+0987654321")
    
    assert result == "SM12345abcde"
    mock_client_instance.messages.create.assert_called_once_with(
        body="ALERTA RITA: Test Alert",
        from_="+1234567890",
        to="+0987654321"
    )
