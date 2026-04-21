import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

/// Handles FCM token lifecycle and foreground message routing.
///
/// Background messages are handled by the service worker
/// (web/firebase-messaging-sw.js) and do not go through this class.
class PushNotificationService {
  PushNotificationService._();

  static final PushNotificationService instance = PushNotificationService._();

  /// VAPID key for web push. Provided at build time via --dart-define.
  static const String _vapidKey = String.fromEnvironment('FIREBASE_VAPID_KEY');

  /// Request notification permission and return the FCM registration token,
  /// or null if permission was denied, FCM is not configured, or an error occurred.
  ///
  /// Web push requires a VAPID key passed via --dart-define=FIREBASE_VAPID_KEY=...
  /// Without it FCM token requests fail silently and this method returns null.
  Future<String?> requestTokenForWeb() async {
    if (!kIsWeb) return null;
    if (_vapidKey.isEmpty) {
      debugPrint('[FCM] No VAPID key — push tokens disabled. '
          'Pass --dart-define=FIREBASE_VAPID_KEY=... to enable.');
      return null;
    }

    try {
      final messaging = FirebaseMessaging.instance;

      final settings = await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );

      if (settings.authorizationStatus != AuthorizationStatus.authorized &&
          settings.authorizationStatus != AuthorizationStatus.provisional) {
        debugPrint('[FCM] Push permission denied: ${settings.authorizationStatus}');
        return null;
      }

      final token = await messaging.getToken(vapidKey: _vapidKey);
      debugPrint('[FCM] Token obtained: ${token != null ? "yes" : "no"}');
      return token;
    } catch (e) {
      debugPrint('[FCM] Failed to get token: $e');
      return null;
    }
  }

  /// Delete the local FCM token (best-effort; does not call the backend).
  Future<void> deleteToken() async {
    if (!kIsWeb || _vapidKey.isEmpty) return;
    try {
      await FirebaseMessaging.instance.deleteToken();
    } catch (e) {
      debugPrint('[FCM] Failed to delete token: $e');
    }
  }

  /// Subscribe to foreground messages and pass them to [onMessage].
  void listenForeground(void Function(RemoteMessage) onMessage) {
    FirebaseMessaging.onMessage.listen(onMessage);
  }
}
