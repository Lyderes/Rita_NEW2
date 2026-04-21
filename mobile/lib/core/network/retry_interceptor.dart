import 'dart:async';
import 'package:dio/dio.dart';
import 'dart:io';

class RetryInterceptor extends Interceptor {
  RetryInterceptor({
    required this.dio,
    this.maxRetries = 3,
    this.retryDelay = const Duration(milliseconds: 500),
  });

  final Dio dio;
  final int maxRetries;
  final Duration retryDelay;

  @override
  Future<void> onError(DioException err, ErrorInterceptorHandler handler) async {
    var extra = err.requestOptions.extra;
    var retryCount = extra['retry_count'] as int? ?? 0;

    // Special case for 401: retry UP TO 2 TIMES (to avoid infinite loops)
    final is401 = err.response?.statusCode == 401;
    final maxForThisError = is401 ? 2 : maxRetries;
    
    if (_shouldRetry(err) && retryCount < maxForThisError) {
      retryCount++;
      extra['retry_count'] = retryCount;

      // Wait before retry (longer for 401 to let backend settle more)
      final delay = is401 ? const Duration(milliseconds: 1500) : retryDelay * retryCount;
      await Future<void>.delayed(delay);

      try {
        final optionsHeaders = Map<String, dynamic>.from(err.requestOptions.headers);
        // FORCE refetch of token by removing the old potentially invalid one
        optionsHeaders.remove('Authorization');

        final response = await dio.request<dynamic>(
          err.requestOptions.path,
          data: err.requestOptions.data,
          queryParameters: err.requestOptions.queryParameters,
          options: Options(
            method: err.requestOptions.method,
            headers: optionsHeaders,
            extra: extra,
          ),
        );
        return handler.resolve(response);
      } catch (retryError) {
        // If the retry itself throws, pass the ORIGINAL error up the chain 
        // unless we want to propagate the new one. Usually, we want the first trigger.
        return handler.next(err);
      }
    }

    return super.onError(err, handler);
  }

  bool _shouldRetry(DioException err) {
    if (err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.sendTimeout ||
        err.type == DioExceptionType.receiveTimeout ||
        err.type == DioExceptionType.connectionError) {
      return true;
    }

    if (err.error is SocketException) {
      return true;
    }

    final statusCode = err.response?.statusCode;
    if (statusCode != null && (statusCode >= 500 || statusCode == 408 || statusCode == 401)) {
      return true;
    }

    return false;
  }
}
