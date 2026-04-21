import 'package:dio/dio.dart';
import 'package:rita_mobile/core/storage/secure_storage_service.dart';

class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required SecureStorageService secureStorage,
    this.onUnauthorized,
  }) : _secureStorage = secureStorage;

  final SecureStorageService _secureStorage;
  final void Function()? onUnauthorized;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await _secureStorage.readAccessToken();
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (err.response?.statusCode == 401) {
      // Diagnostic: only trigger logout if the RetryInterceptor has given up
      // Or if there is no retry logic involved.
      final retryCount = err.requestOptions.extra['retry_count'] as int? ?? 0;
      final maxRetries = 2; // Matching RetryInterceptor's special 401 limit
      
      if (retryCount >= maxRetries) {
        onUnauthorized?.call();
      }
    }
    handler.next(err);
  }
}
