import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SecureStorageService {
  SecureStorageService();

  FlutterSecureStorage? _secureStorage;

  FlutterSecureStorage get _ioStorage {
    return _secureStorage ??= const FlutterSecureStorage();
  }

  static const String _accessTokenKey = 'rita_access_token';

  Future<void> saveAccessToken(String token) async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_accessTokenKey, token);
      return;
    }

    await _ioStorage.write(key: _accessTokenKey, value: token);
  }

  Future<String?> readAccessToken() async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(_accessTokenKey);
    }

    return _ioStorage.read(key: _accessTokenKey);
  }

  Future<void> clearSession() async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_accessTokenKey);
      return;
    }

    await _ioStorage.delete(key: _accessTokenKey);
  }
}
