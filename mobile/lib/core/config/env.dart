class Env {
  /// API base URL (single source of truth for local development).
  /// Backend must run on: http://localhost:8000
  /// - Override via environment: RITA_API_BASE_URL='http://...'
  static String get apiBaseUrl {
    const envOverride = String.fromEnvironment(
      'RITA_API_BASE_URL',
      defaultValue: '',
    );

    if (envOverride.isNotEmpty) {
      return envOverride;
    }

    return 'http://127.0.0.1:8080';
  }

  /// Add custom endpoint paths here as constants if needed
  static const String authLoginEndpoint = '/auth/login';
}
