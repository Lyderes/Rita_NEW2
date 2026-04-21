import 'package:rita_mobile/core/network/api_client.dart';
import 'package:rita_mobile/features/auth/data/models/login_request.dart';
import 'package:rita_mobile/features/auth/data/models/register_request.dart';
import 'package:rita_mobile/features/auth/data/models/token_response.dart';

class AuthApi {
  AuthApi(this._client);

  final ApiClient _client;

  /// Registers or clears the FCM push token for the authenticated user.
  /// Pass null to unregister (e.g. on logout).
  Future<void> updatePushToken(String? token) async {
    await _client.put('/auth/me/push-token', data: {'token': token});
  }

  Future<TokenResponse> login(LoginRequest request) async {
    final response = await _client.post('/auth/login', data: request.toJson());
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid response payload for login');
    }
    return TokenResponse.fromJson(response);
  }

  Future<TokenResponse> register(RegisterRequest request) async {
    final response = await _client.post('/auth/register', data: request.toJson());
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid response payload for register');
    }
    return TokenResponse.fromJson(response);
  }
}
