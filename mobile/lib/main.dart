import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dio/dio.dart';
import 'package:rita_mobile/app/app.dart';
import 'package:rita_mobile/firebase_options.dart';

/// Dev-only: if the URL has ?autologin=1, fetch a token from the backend
/// and store it before the app bootstraps. Ignored in release builds.
Future<void> _maybeAutoLogin() async {
  if (!kIsWeb || kReleaseMode) return;
  final uri = Uri.base;
  if (uri.queryParameters['autologin'] != '1') return;
  try {
    const base = String.fromEnvironment('RITA_API_BASE_URL', defaultValue: 'http://127.0.0.1:8080');
    final dio = Dio();
    final res = await dio.post<Map<String, dynamic>>(
      '$base/auth/login',
      data: {'username': 'admin', 'password': 'admin123'},
    );
    final token = res.data?['access_token'] as String?;
    if (token != null) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('rita_access_token', token);
      debugPrint('[AutoLogin] Token stored OK');
    }
  } catch (e) {
    debugPrint('[AutoLogin] Failed: $e');
  }
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _maybeAutoLogin();

  if (kIsWeb) {
    const apiKey = String.fromEnvironment('FIREBASE_API_KEY');
    if (apiKey.isNotEmpty) {
      try {
        await Firebase.initializeApp(
          options: DefaultFirebaseOptions.currentPlatform,
        );
      } catch (e) {
        debugPrint('[Firebase] Init failed — push notifications disabled: $e');
      }
    } else {
      debugPrint('[Firebase] No config provided — push notifications disabled. '
          'Pass --dart-define=FIREBASE_API_KEY=... to enable.');
    }
  }

  runApp(const ProviderScope(child: RitaApp()));
}
