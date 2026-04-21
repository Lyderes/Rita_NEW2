import 'package:rita_mobile/core/services/push_notification_service.dart';
import 'package:rita_mobile/core/storage/secure_storage_service.dart';
import 'package:rita_mobile/features/auth/data/api/auth_api.dart';
import 'package:rita_mobile/features/auth/data/models/login_request.dart';
import 'package:rita_mobile/features/auth/data/models/register_request.dart';
import 'package:rita_mobile/features/auth/data/models/token_response.dart';

class AuthRepository {
  AuthRepository({
    required AuthApi api,
    required SecureStorageService storage,
    required PushNotificationService pushNotifications,
  })  : _api = api,
        _storage = storage,
        _push = pushNotifications;

  final AuthApi _api;
  final SecureStorageService _storage;
  final PushNotificationService _push;

  Future<TokenResponse> login({
    required String username,
    required String password,
  }) async {
    final response = await _api.login(
      LoginRequest(username: username, password: password),
    );
    await _storage.saveAccessToken(response.accessToken);
    _registerPushToken(); // fire-and-forget — token registration is non-critical
    return response;
  }

  Future<bool> hasSession() async {
    final token = await _storage.readAccessToken();
    return token != null && token.isNotEmpty;
  }

  Future<void> logout() async {
    // Clear push token on the server before wiping the local session so the
    // authenticated request can still be made.
    try {
      await _api.updatePushToken(null);
    } catch (_) {
      // Best-effort — don't block logout if this fails.
    }
    await _push.deleteToken();
    return _storage.clearSession();
  }

  Future<TokenResponse> register({
    required String username,
    required String password,
    String? fullName,
  }) async {
    final response = await _api.register(
      RegisterRequest(username: username, password: password, fullName: fullName),
    );
    await _storage.saveAccessToken(response.accessToken);
    _registerPushToken();
    return response;
  }

  /// Requests the FCM token and registers it with the backend.
  /// Failures are silently logged — push is a non-critical feature.
  void _registerPushToken() {
    _push.requestTokenForWeb().then((token) async {
      if (token == null) return;
      try {
        await _api.updatePushToken(token);
      } catch (e) {
        // Ignore — push registration failing must not break login.
      }
    });
  }
}
